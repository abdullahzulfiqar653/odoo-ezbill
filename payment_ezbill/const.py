API_BASE_URL = 'https://api.ezbill.pk'

# EZBILL collects PKR only.
SUPPORTED_CURRENCIES = ['PKR']

DEFAULT_PAYMENT_METHOD_CODES = {'ezbill'}

# EZBILL status -> Odoo transaction state.
STATUS_MAPPING = {
    'pending': ('CREATED', 'SENT', 'ACCEPTED'),
    'done': ('PAID', 'SETTLED'),
    'cancel': ('REJECTED', 'EXPIRED', 'CANCELLED'),
}

WEBHOOK_TOLERANCE = 300  # seconds

WEBHOOK_ROUTE = '/payment/ezbill/webhook'
PAY_ROUTE = '/payment/ezbill/pay'
POLL_ROUTE = '/payment/ezbill/poll'
