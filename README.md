# Advanced Commerce

A multi-channel, headless commerce engine for **Frappe / ERPNext**, built to
bring two ideas from best-in-class commerce platforms onto Frappe:

- **Channels + a generic attribute engine** (the pattern that makes Saleor
  good at multi-region/multi-brand catalogs)
- **Saga-style order workflows with automatic compensation** (the pattern
  that makes Medusa robust when a payment or stock step fails mid-checkout)

It installs as a normal Frappe app on top of ERPNext (uses ERPNext's Item,
Warehouse, Sales Order, Stock Reservation Entry, Customer, etc.) and adds a
REST API meant to be called from a headless storefront (Next.js, Remix,
mobile app...).

## What's included

| Doctype | Purpose |
|---|---|
| **Sales Channel** | A sellable context: currency, price list, warehouse, payment provider, storefront domain — the same role as Saleor's "Channel" |
| **Commerce Attribute** / **Commerce Attribute Value** | Generic attribute engine for variants + storefront filtering (color, size, material...) |
| **Commerce Product Type** | Groups attributes that apply to a category of product |
| **Cart** / **Cart Item** | Headless cart, works for guest sessions and logged-in customers |
| **Promotion Rule** | Percentage / flat / free-shipping discounts, with coupon codes, usage limits, channel & item eligibility |
| **Workflow Run** / **Workflow Step Log** | The saga engine's execution record — full visibility into every checkout, with automatic retry and compensation on failure |
| **Webhook Subscription** | External subscribers to internal events (`sales_order.confirmed`, `payment_entry.confirmed`, etc.), delivered via background jobs with HMAC signing |
| **Commerce Settings** | Single doctype for app-wide defaults |

## The saga workflow engine

`advanced_commerce/workflow_engine/engine.py` runs a named list of `Step`
objects, each with a `run()` and a `compensate()`. The built-in
`place_order` workflow is:

```
reserve_stock  →  charge_payment  →  create_order
```

If `charge_payment` fails after retries are exhausted, `reserve_stock`'s
compensation automatically cancels the stock reservation — no manual
cleanup, no stuck inventory. Add your own workflow by writing steps under
`workflow_engine/steps/` and registering them in `workflows.py`.

## REST API (for your storefront)

All endpoints are under `/api/method/advanced_commerce.api.<module>.<fn>`.

```
GET  advanced_commerce.api.catalog.list_products     ?channel=us-web
GET  advanced_commerce.api.catalog.get_product       ?channel=us-web&item_code=TSHIRT-001
GET  advanced_commerce.api.catalog.list_facets        ?channel=us-web

POST advanced_commerce.api.cart.get_or_create_cart    {channel, session_id}
POST advanced_commerce.api.cart.add_item              {cart_name, item_code, qty}
POST advanced_commerce.api.cart.update_item_qty        {cart_name, item_code, qty}
POST advanced_commerce.api.cart.apply_coupon           {cart_name, coupon_code}

POST advanced_commerce.api.checkout.start_checkout     {cart_name, payment_method_token}
GET  advanced_commerce.api.checkout.get_checkout_status ?workflow_run=...

POST advanced_commerce.api.webhooks.subscribe          {event, target_url, secret}
```

`start_checkout` returns immediately with a `workflow_run` id; poll
`get_checkout_status` (or subscribe to the `workflow_run.updated` webhook
event) since payment/stock steps run asynchronously.

## Adding a real payment gateway

Payment providers are a small plugin registry
(`advanced_commerce/api/payments.py`). Ships with a `manual` provider that
never blocks checkout. To add Stripe/Razorpay/etc.:

```python
from advanced_commerce.api.payments import PaymentProvider, register_provider

class StripeProvider(PaymentProvider):
    name = "stripe"
    def charge(self, amount, currency, payment_method_token, reference):
        ...  # call Stripe, return a charge id
    def refund(self, charge_id):
        ...

register_provider("stripe", StripeProvider)
```

Then set `payment_provider = "stripe"` on the relevant Sales Channel.

## Installation

Requires an existing Frappe bench with ERPNext already installed.

```bash
# 1. get the app into your bench
cd frappe-bench
bench get-app advanced_commerce /path/to/advanced_commerce   # local path
# or, once pushed to a git remote:
# bench get-app https://github.com/your-org/advanced_commerce.git

# 2. install it on your site
bench --site your-site.local install-app advanced_commerce

# 3. restart
bench restart
```

`after_install` automatically creates the `Commerce Manager` and
`Commerce API` roles and a default `Commerce Settings` record — no manual
setup step required before you can start creating Sales Channels.

### First steps after install

1. **Desk → Advanced Commerce → Sales Channel**: create at least one channel
   (currency, price list, warehouse).
2. **Commerce Attribute**: define Color/Size/etc. if you use variants.
3. **Commerce Settings**: set a default Sales Channel.
4. Point your storefront at the REST endpoints above.

## Background workers

The workflow engine and webhook delivery both rely on Frappe's standard
background workers and scheduler — make sure `bench start` (or your
production supervisor config) is running the `short` queue worker and the
scheduler is enabled (`bench --site your-site.local enable-scheduler`).

## Design notes / what was intentionally left out

This is a foundation, not a full clone of Saleor or Medusa: there's no
GraphQL layer (layer `frappe-graphql` on top if you need it), no built-in
tax engine (delegate to ERPNext's existing tax rules or a service like
TaxJar/Avalara via a workflow step), and no admin dashboard beyond Frappe
Desk. Those are the next logical additions once the core patterns here
(channels, attributes, sagas, webhooks) are proven out for your catalog.
