# Paystack Fees & Net Platform Revenue

This document explains how the platform tracks what Paystack charges, and how that turns "platform earnings" into a number that matches the bank.

## The problem this solves

Every naira that moves through Paystack pays a toll:

- **Collections** (a customer paying for an order, a wallet top-up) are settled to us **net** of a processing fee.
- **Payouts** (vendor and rider withdrawals) are debited from our balance **plus** a transfer fee.

Neither fee appears on `Order` or `WalletTransaction`. So the dashboard's "Total Platform Earnings" — built from `platform_amount`, `service_fee`, and marketplace delivery fees — is money we **billed**, not money we **kept**. On a ₦10,000 card order, Paystack takes ₦250 before the money reaches us.

## The ledger: `wallet.PaystackFeeRecord`

One row per Paystack money movement. Written directly from Paystack's own payloads at every point money moves.

| Field | Meaning |
|---|---|
| `direction` | `collection` (money in), `payout` (money out), `reversal` |
| `gross_amount` | Amount that moved, in naira |
| `fee_amount` | What Paystack charged |
| `net_amount` | Settled to us (collection) or total debited (payout = amount + fee) |
| `is_estimated` | `False` when Paystack reported the fee; `True` when we derived it |
| `source` | `webhook`, `verify`, `balance_ledger`, `backfill`, `estimate` |
| `paid_at` | When Paystack processed it — this is what reporting windows filter on |
| `order`, `wallet_transaction`, `user` | Links back to what the movement paid for |

Rows are unique on `(direction, reference)`, so re-delivered webhooks and a verify call arriving after a webhook update the row rather than duplicating it. A reported fee always wins over an estimate written earlier.

## Reported vs. estimated

This distinction is the point, and the dashboard surfaces it:

- **Reported** — Paystack's charge payloads carry `fees` (in kobo). Collections are exact from the moment they land.
- **Estimated** — Paystack's *transfer* payloads usually carry no fee at all. Those rows start out computed from the published fee schedule and flagged `is_estimated=True`.

The **balance ledger** (`/balance/ledger`) is the only Paystack endpoint that reports a fee on every movement, including transfers. Running the sync replaces estimates with actuals.

### Fee schedule (fallback only)

Defined in `helpers/paystack_fees.py` as `DEFAULT_FEE_SCHEDULE`, matching Paystack's published Nigerian pricing:

- **Card / local channels** — 1.5% + ₦100, with the ₦100 waived below ₦2,500, whole fee capped at ₦2,000.
- **Bank transfer / dedicated NUBAN** — 1%, capped at ₦300.
- **Payouts** — ₦10 up to ₦5,000; ₦25 from ₦5,001 to ₦50,000; ₦50 above that.

Override any of it in `settings.py` when your negotiated rate differs — keys are merged over the defaults, so you only state what changed:

```python
PAYSTACK_FEE_SCHEDULE = {
    'card': {'percentage': Decimal('0.014'), 'cap': Decimal('1500')},
}
```

## Where fees get captured

| Path | File | Direction |
|---|---|---|
| Order payment confirmed (verify) | `rider/views.py` → `ConfirmOrderPaymentAPIView` | collection |
| Order payment webhook | `rider/views.py` → `OrderPaymentWebhookView` | collection |
| Wallet deposit via virtual account | `helpers/paystack.py` → `handle_webhook` (`charge.success`) | collection |
| Payout confirmed | `helpers/paystack.py` → `handle_webhook` (`transfer.success`) | payout |
| Instant payout at initiation | `helpers/paystack.py` → `initiate_transfer` | payout |
| Payout failed / reversed | `handle_webhook` (`transfer.failed`, `transfer.reversed`) | row deleted — Paystack returned the fee |

Every recorder is best-effort and swallows its own errors: **a fee-capture failure can never break a payment.**

## Dashboard

`GET /admin-manager/dashboard/overview/` gains two keys under `revenue_summary`. All existing keys are unchanged.

```jsonc
"paystack_fees": {
  "value": 12450.00,                         // total fees in the window
  "breakdown": {
    "collection_fees": { "value": 11200.00 },
    "payout_fees":     { "value":  1250.00 }
  },
  "gross_collected": { "value": 780000.00 },
  "net_settled":     { "value": 768800.00 },
  "confidence": {
    "reported_amount":  11200.00,            // Paystack said so
    "estimated_amount":  1250.00,            // we derived it
    "movements": 64,
    "estimated_movements": 50
  }
},
"net_platform_revenue": { "value": 48550.00 } // platform_earnings − paystack_fees
```

### Dedicated endpoints

```
GET  /admin-manager/analytics/paystack-fees/
GET  /admin-manager/analytics/paystack-fees/transactions/
POST /admin-manager/analytics/paystack-fees/sync/
```

The first returns headline totals, the **effective collection rate** (what share of everything customers paid ends up with Paystack — the single number to watch month over month), a per-channel breakdown showing which payment method costs most, a daily series for charting, and the costliest individual movements.

All three accept `period=day|week|month|year` or `start_date`/`end_date`.

## Windowing

Fees are windowed on `paid_at` (when Paystack processed the movement); platform earnings are windowed on order `created_at`. For a rolling period the two agree closely, but an order paid just after a window boundary can land its fee in the next window. If you need the two perfectly tied, join through `PaystackFeeRecord.order`.

## Setup

**1. Migrate:**

```bash
python manage.py migrate wallet
```

**2. Backfill history.** Fee capture only records from the moment it ships, which would leave every past order looking fee-free. But the raw Paystack payloads are already stored in `WalletTransaction.response_data` — this replays them:

```bash
python manage.py backfill_paystack_fees --dry-run
```

```bash
python manage.py backfill_paystack_fees --estimate-missing
```

`--estimate-missing` additionally covers paid orders with no stored payload by applying the fee schedule, flagged as estimates.

**3. Reconcile with Paystack's actuals:**

```bash
python manage.py sync_paystack_fees
```

Safe to run repeatedly — it only corrects rows. Worth scheduling nightly so payout estimates become reported numbers automatically.

**4. Webhook coverage.** Fee accuracy depends on Paystack delivering events. Confirm the Paystack dashboard has a webhook pointing at `/wallet/transactions/webhook/` with `charge.success`, `transfer.success`, `transfer.failed`, and `transfer.reversed` enabled. Without `transfer.*`, payout fees stay estimated until the ledger sync runs.
