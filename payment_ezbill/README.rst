=====================================
Payment Provider: EZBILL (Raast QR)
=====================================

Accept payments in Pakistan with `EZBILL <https://ezbill.pk>`_. At checkout the
customer sees a Raast dynamic QR code and pays with any bank app, JazzCash or
Easypaisa. The order is confirmed automatically the moment the money arrives.

Written for Odoo 17.0 and 18.0 (Community and Enterprise).

**Status: beta.** Not yet run in a production Odoo install. Test it with an
``ez_test_`` sandbox key before switching to live, and report problems to
info@ezbill.pk.

Features
========

* Payment provider ``ezbill`` with its own "Raast QR" payment method (PKR).
* Dynamic QR shown on a payment page that polls and redirects to Odoo's
  payment status page once paid.
* Signed webhook (``X-EZBILL-Signature``, HMAC-SHA256, 5-minute replay window)
  marks the transaction done even if the customer closes the page.
* Test Mode uses the EZBILL sandbox (``ez_test_`` key); Enabled takes real
  payments (``ez_live_`` key). The module refuses a mismatched key.
* Raast / 1LINK outages are shown to the customer as a friendly
  "temporarily unavailable" message.

Configuration
=============

1. Install the module (Apps > search "EZBILL").
2. Go to *Invoicing/Accounting > Configuration > Payment Providers > EZBILL*.
3. Enter your **API Key** and **Webhook Secret** from the EZBILL merchant
   console (https://ezbill.pk/developers/).
4. Copy the **Webhook URL** shown on the form
   (``https://<your-odoo>/payment/ezbill/webhook``) into the EZBILL console as
   the **endpoint base URL**. EZBILL posts to ``…/webhook/onego-notification``,
   which the module accepts.
5. Set the state to **Test Mode** with an ``ez_test_`` key, try a payment, then
   switch to **Enabled** with your ``ez_live_`` key.
6. Make sure the website / company currency is **PKR**.

How it works
============

* When the customer pays, Odoo calls ``POST /v1/qr`` with the amount in paisa
  and the transaction reference, stores the EZBILL id as the provider
  reference, and shows the QR on ``/payment/ezbill/pay``.
* The page polls ``/payment/ezbill/poll``, which reads ``GET /v1/rtp/<id>``.
* EZBILL posts ``payment.received`` / ``payment.settled`` (done) and
  ``rtp.rejected`` / ``rtp.expired`` (cancelled) to the webhook. The signature
  is verified on the raw body with a constant-time comparison. Replays are
  harmless: state changes are idempotent.
* A paid amount different from the order amount puts the transaction in error
  for review instead of confirming it.

Links
=====

* Website: https://ezbill.pk
* Developer docs: https://ezbill.pk/developers/

License
=======

LGPL-3
