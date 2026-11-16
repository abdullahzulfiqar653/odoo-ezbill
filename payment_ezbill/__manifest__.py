{
    'name': "Payment Provider: EZBILL (Raast QR)",
    'version': '1.0.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': "Accept Raast payments in Pakistan with a dynamic QR any bank app, JazzCash or Easypaisa can scan.",
    'description': " ",  # Non-empty to avoid loading README.rst as the app description.
    'author': "EZBILL",
    'website': "https://ezbill.pk",
    'license': 'LGPL-3',
    'depends': ['payment'],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_ezbill_templates.xml',
        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_ezbill/static/src/css/ezbill_pay.css',
            'payment_ezbill/static/src/js/ezbill_pay.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': False,
}
