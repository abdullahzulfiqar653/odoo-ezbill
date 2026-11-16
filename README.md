# EZBILL – Raast QR payments for Odoo

Odoo payment provider module for [EZBILL](https://ezbill.pk). At checkout the
customer sees a Raast dynamic QR code and pays with any bank app, JazzCash or
Easypaisa; the transaction is confirmed by a signed EZBILL webhook.

- Module: [`payment_ezbill`](payment_ezbill/) (see its [README](payment_ezbill/README.rst))
- Written for Odoo 17.0 and 18.0
- License: LGPL-3
- Status: **beta**. Not yet run in a production Odoo install. Test it with an
  `ez_test_` sandbox key first, and report problems to info@ezbill.pk.
- Docs: <https://ezbill.pk/developers/>

## Install

Copy `payment_ezbill` into your Odoo addons path, update the apps list, install
**Payment Provider: EZBILL (Raast QR)**, then configure it under
*Invoicing/Accounting → Configuration → Payment Providers → EZBILL*.
