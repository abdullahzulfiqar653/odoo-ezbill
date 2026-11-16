import json
import logging
from urllib.parse import quote

from werkzeug.exceptions import Forbidden, NotFound

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_ezbill import const

_logger = logging.getLogger(__name__)


class EzbillController(http.Controller):

    def _ezbill_get_tx(self, reference, access_token):
        if not reference or not access_token or not payment_utils.check_access_token(access_token, reference):
            raise Forbidden()
        tx = request.env['payment.transaction'].sudo().search(
            [('reference', '=', reference), ('provider_code', '=', 'ezbill')], limit=1
        )
        if not tx:
            raise NotFound()
        return tx

    @http.route(const.PAY_ROUTE, type='http', auth='public', methods=['GET'], sitemap=False)
    def ezbill_pay(self, reference=None, access_token=None, **kwargs):
        """Show the Raast QR to the customer and poll until it is paid."""
        tx = self._ezbill_get_tx(reference, access_token)
        if tx.state == 'done':
            return request.redirect('/payment/status')
        qr_image_url = '/report/barcode?barcode_type=QR&width=280&height=280&value=' + quote(
            tx.ezbill_qr_string or '', safe=''
        )
        return request.render('payment_ezbill.ezbill_pay_page', {
            'tx': tx,
            'qr_image_url': qr_image_url,
            'poll_url': f'{const.POLL_ROUTE}?reference={quote(tx.reference)}&access_token={quote(access_token)}',
            'amount_display': f"Rs {tx.amount:,.2f}",
        })

    @http.route(const.POLL_ROUTE, type='http', auth='public', methods=['GET'], sitemap=False)
    def ezbill_poll(self, reference=None, access_token=None, **kwargs):
        """Return the transaction state; refreshes it from EZBILL while still open."""
        tx = self._ezbill_get_tx(reference, access_token)
        try:
            tx._ezbill_refresh_status()
        except ValidationError as error:
            _logger.warning("EZBILL: status refresh failed for %s: %s", tx.reference, error)
        return request.make_json_response({
            'state': tx.state,
            'message': tx.state_message or '',
            'redirect': '/payment/status',
        }, headers={'Cache-Control': 'no-store'})

    @http.route([const.WEBHOOK_ROUTE, const.WEBHOOK_ROUTE + '/onego-notification'], type='http', auth='public', methods=['POST'], csrf=False, save_session=False)
    def ezbill_webhook(self, **kwargs):
        """Signed event from EZBILL: verify on the raw body, then update the transaction."""
        raw_body = request.httprequest.get_data()
        headers = request.httprequest.headers
        timestamp = headers.get('X-EZBILL-Timestamp')
        signature = headers.get('X-EZBILL-Signature')

        providers = request.env['payment.provider'].sudo().search([
            ('code', '=', 'ezbill'), ('state', 'in', ('enabled', 'test')),
        ])
        provider = next(
            (p for p in providers if p._ezbill_verify_signature(raw_body, timestamp, signature)), None
        )
        if provider is None:
            _logger.warning(
                "EZBILL: rejected webhook with invalid signature [correlation_id=%s]",
                headers.get('X-Correlation-Id'),
            )
            return request.make_json_response({'error': 'invalid signature'}, status=400)

        try:
            event = json.loads(raw_body.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            return request.make_json_response({'error': 'invalid json'}, status=400)
        _logger.info(
            "EZBILL: webhook %s for %s (status %s) [correlation_id=%s]",
            event.get('event'), event.get('reference'), event.get('status'), event.get('correlation_id'),
        )

        try:
            tx = request.env['payment.transaction'].sudo()._get_tx_from_notification_data('ezbill', event)
            if tx.provider_id != provider:
                _logger.warning("EZBILL: webhook signed by provider %s for tx of provider %s", provider.id, tx.provider_id.id)
                return request.make_json_response({'error': 'provider mismatch'}, status=400)
            # State changes are idempotent: a replayed event (same event + correlation_id) is a no-op.
            tx._handle_notification_data('ezbill', event)
        except ValidationError:
            # Unknown reference etc.: acknowledge so EZBILL stops retrying, but keep a trace.
            _logger.exception("EZBILL: unable to handle webhook %s", event.get('correlation_id'))
        return request.make_json_response({'received': True})
