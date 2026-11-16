import hashlib
import hmac
import json
import logging
import time

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment_ezbill import const

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('ezbill', "EZBILL")], ondelete={'ezbill': 'set default'}
    )
    ezbill_api_key = fields.Char(
        string="EZBILL API Key",
        help="ez_test_… in Test Mode (sandbox), ez_live_… when Enabled. "
             "Create keys in the EZBILL merchant console.",
        required_if_provider='ezbill',
        groups='base.group_system',
    )
    ezbill_webhook_secret = fields.Char(
        string="EZBILL Webhook Secret",
        help="Used to verify the X-EZBILL-Signature header of webhooks.",
        required_if_provider='ezbill',
        groups='base.group_system',
    )
    ezbill_expiry_minutes = fields.Integer(
        string="QR Validity (minutes)",
        default=30,
        help="How long the customer has to scan and pay (1 to 1440).",
    )
    ezbill_webhook_url = fields.Char(
        string="Webhook URL", compute='_compute_ezbill_webhook_url',
        help="Paste this as the endpoint base URL in the EZBILL merchant console. "
             "EZBILL adds /onego-notification to it; both paths are accepted.",
    )

    # === COMPUTE / CONSTRAINTS === #

    def _compute_ezbill_webhook_url(self):
        for provider in self:
            provider.ezbill_webhook_url = provider.get_base_url().rstrip('/') + const.WEBHOOK_ROUTE

    @api.constrains('ezbill_expiry_minutes')
    def _check_ezbill_expiry_minutes(self):
        for provider in self.filtered(lambda p: p.code == 'ezbill'):
            if not 1 <= provider.ezbill_expiry_minutes <= 1440:
                raise ValidationError(_("EZBILL: QR validity must be between 1 and 1440 minutes."))

    @api.constrains('state', 'ezbill_api_key')
    def _check_ezbill_key_matches_state(self):
        for provider in self.sudo().filtered(lambda p: p.code == 'ezbill' and p.ezbill_api_key):
            key = provider.ezbill_api_key.strip()
            if provider.state == 'enabled' and key.startswith('ez_test_'):
                raise ValidationError(_(
                    "EZBILL: a sandbox key (ez_test_…) cannot be used when the provider is Enabled. "
                    "Use your live key (ez_live_…) or switch the provider to Test Mode."
                ))
            if provider.state == 'test' and key.startswith('ez_live_'):
                raise ValidationError(_(
                    "EZBILL: a live key (ez_live_…) cannot be used in Test Mode. "
                    "Use your sandbox key (ez_test_…) or enable the provider."
                ))

    # === BUSINESS METHODS === #

    def _get_supported_currencies(self):
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'ezbill':
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'ezbill':
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _ezbill_make_request(self, method, endpoint, payload=None):
        """Call the EZBILL API and return the decoded JSON body.

        :raise ValidationError: on any API or network error, with EZBILL's message.
        """
        self.ensure_one()
        url = const.API_BASE_URL + endpoint
        headers = {
            'Authorization': f'Bearer {self.sudo().ezbill_api_key.strip()}',
            'Accept': 'application/json',
            'User-Agent': 'odoo-payment-ezbill/1.0',
        }
        try:
            response = requests.request(method, url, json=payload, headers=headers, timeout=20)
        except requests.exceptions.RequestException:
            _logger.exception("EZBILL: could not reach %s", url)
            raise ValidationError(_("EZBILL: could not reach the payment service. Please try again."))

        try:
            data = response.json() if response.content else {}
        except ValueError:
            data = {}
        if response.ok:
            return data

        error = data.get('error') if isinstance(data, dict) else None
        if isinstance(error, dict):
            _logger.warning(
                "EZBILL %s %s -> %s %s (%s) [correlation_id=%s]",
                method, endpoint, response.status_code, error.get('code'), error.get('reason'),
                error.get('correlation_id'),
            )
            if response.status_code == 503 or error.get('retryable'):
                raise ValidationError(_(
                    "Raast payments are temporarily unavailable. Please try again in a few minutes."
                ))
            raise ValidationError(_("EZBILL: %s", error.get('message') or error.get('code')))
        _logger.warning("EZBILL %s %s -> %s %s", method, endpoint, response.status_code, data)
        detail = data.get('detail') if isinstance(data, dict) else None
        raise ValidationError(_("EZBILL: %s", detail or json.dumps(data) or response.status_code))

    def _ezbill_verify_signature(self, raw_body, timestamp, signature):
        """Return True if the webhook was signed with this provider's secret.

        hex = HMAC_SHA256(secret, timestamp + "." + raw_body), header "v1=<hex>".
        """
        self.ensure_one()
        secret = self.sudo().ezbill_webhook_secret
        if not secret or not timestamp or not signature:
            return False
        timestamp = timestamp.strip()
        if not timestamp.isdigit() or abs(time.time() - int(timestamp)) > const.WEBHOOK_TOLERANCE:
            return False
        expected = hmac.new(
            secret.encode(), timestamp.encode() + b'.' + raw_body, hashlib.sha256
        ).hexdigest()
        for part in signature.split(','):
            part = part.strip()
            if part.startswith('v1=') and hmac.compare_digest(part[3:].lower(), expected):
                return True
        return False
