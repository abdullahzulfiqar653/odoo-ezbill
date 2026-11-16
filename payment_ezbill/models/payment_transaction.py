import logging

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_ezbill import const

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    ezbill_qr_string = fields.Char(string="EZBILL QR Payload", readonly=True, copy=False)
    ezbill_expires_at = fields.Char(string="EZBILL QR Expiry", readonly=True, copy=False)

    def _ezbill_amount_minor(self):
        self.ensure_one()
        return payment_utils.to_minor_currency_units(self.amount, self.currency_id, 2)

    def _get_specific_rendering_values(self, processing_values):
        """Create the Raast QR on EZBILL and point the redirect form at our pay page."""
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'ezbill':
            return res

        if self.currency_id.name not in const.SUPPORTED_CURRENCIES:
            raise ValidationError(_("EZBILL accepts payments in PKR only."))

        if not self.ezbill_qr_string:
            qr = self.provider_id._ezbill_make_request('POST', '/v1/qr', {
                'amount_minor': self._ezbill_amount_minor(),
                'reference': self.reference[:64],
                'expiry_minutes': self.provider_id.ezbill_expiry_minutes or 30,
            })
            self.write({
                'provider_reference': qr.get('id'),
                'ezbill_qr_string': qr.get('qr_string'),
                'ezbill_expires_at': qr.get('expires_at'),
            })
            _logger.info("EZBILL: created QR %s for transaction %s", qr.get('id'), self.reference)
            self._set_pending()

        return {
            'api_url': const.PAY_ROUTE,
            'reference': self.reference,
            'access_token': payment_utils.generate_access_token(self.reference),
        }

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'ezbill' or len(tx) == 1:
            return tx

        reference = notification_data.get('reference')
        payment_id = notification_data.get('id')
        if not reference and not payment_id:
            raise ValidationError("EZBILL: " + _("Received data with missing reference."))
        domain = [('provider_code', '=', 'ezbill')]
        if payment_id:
            tx = self.search(domain + [('provider_reference', '=', payment_id)], limit=1)
        if not tx and reference:
            tx = self.search(domain + [('reference', '=', reference)], limit=1)
        if not tx:
            raise ValidationError(
                "EZBILL: " + _("No transaction found matching reference %s.", reference or payment_id)
            )
        return tx

    def _process_notification_data(self, notification_data):
        super()._process_notification_data(notification_data)
        if self.provider_code != 'ezbill':
            return

        payment_id = notification_data.get('id')
        if payment_id and self.provider_reference and payment_id != self.provider_reference:
            raise ValidationError("EZBILL: " + _("Payment id does not match the transaction."))
        if payment_id and not self.provider_reference:
            self.provider_reference = payment_id

        status = (notification_data.get('status') or '').upper()
        if status in const.STATUS_MAPPING['done']:
            received = notification_data.get('amount_minor')
            expected = self._ezbill_amount_minor()
            if received is not None and int(received) != expected:
                _logger.error(
                    "EZBILL: amount mismatch for %s: expected %s, received %s",
                    self.reference, expected, received,
                )
                self._set_error(_("EZBILL: the paid amount does not match the order amount."))
                return
            self._set_done()
        elif status in const.STATUS_MAPPING['pending']:
            self._set_pending()
        elif status in const.STATUS_MAPPING['cancel']:
            self._set_canceled(_("EZBILL: the payment was %s.", status.lower()))
        else:
            _logger.warning("EZBILL: unknown status %r for transaction %s", status, self.reference)
            self._set_error(_("EZBILL: received an unknown payment status (%s).", status))

    def _ezbill_refresh_status(self):
        """Ask EZBILL for the current status and apply it (used by the pay page polling)."""
        self.ensure_one()
        if self.state not in ('draft', 'pending') or not self.provider_reference:
            return
        data = self.provider_id._ezbill_make_request('GET', f'/v1/rtp/{self.provider_reference}')
        self._handle_notification_data('ezbill', data)
