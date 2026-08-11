# Paystack Fees & Net Platform Revenue

This document explains how the platform tracks what Paystack charges, and how that turns "platform earnings" into a number that matches the bank.

## First: Paystack money is not your revenue

This is the most important thing on the page, because getting it wrong overstates the business by an order of magnitude.

When a customer pays ₦10,000 for an order, Paystack settles roughly ₦9,750 into the company bank account. **That ₦9,750 is not revenue.** Almost all of it is other people's money that you are holding briefly:

```
₦10,000   customer pays
 −  ₦250  Paystack collection fee
 ────────
  ₦9,750  settled into your bank        ← float, not revenue
 −₦7,500  owed to the vendor            (vendor_amount)
 −₦1,200  owed to the rider             (rider_earning)
 ────────
  ₦1,050  platform earnings             ← revenue
 −  ₦250  Paystack collection fee
 −  ₦25   Paystack payout fee (to pay the vendor/rider out)
 ────────
   ₦775   net platform revenue          ← what you actually keep
```

So:

- **Paystack balance / settlements** = gross float. Mostly a liability — you owe it onward. Never report this as revenue.
- **Platform earnings** = your commission slice: `platform_amount` + `service_fee` + marketplace delivery fees. This is **revenue**.
- **Net platform revenue** = platform earnings − Paystack fees. This is revenue after payment processing costs.
- **Profit** = net platform revenue − your other costs: in-house rider salaries, staff, infrastructure, marketing, support. Those live outside this system, so **nothing here is profit** — the dashboard reports revenue, and you subtract operating costs to get profit.

A useful sanity check: if "net platform revenue" ever approaches the settlement total, something is wrong — the two should differ by roughly the vendor and rider share.

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
  "gross_paid_out":  { "value": 250000.00 },
  "total_debited_for_payouts": { "value": 251250.00 },
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
GET  /admin-manager/analytics/paystack-settlements/
```

The first returns headline totals, the **effective collection rate** (what share of everything customers paid ends up with Paystack — the single number to watch month over month), a per-channel breakdown showing which payment method costs most, a daily series for charting, and the costliest individual movements.

`sync/` accepts `{"source": "transactions" | "transfers" | "ledger" | "both"}` (default `both`): `transactions` pulls collection fees, `transfers` imports successful payouts and completes matching local withdrawals when a webhook was missed, and `ledger` corrects payout estimates from the balance ledger.

`paystack-settlements/` reads live from Paystack and shows what actually reached the bank account. Remember it is float, not revenue — see the top of this document.

All accept `period=day|week|month|year` or `start_date`/`end_date`.

## Which Paystack endpoint tells you what

| Endpoint | Reports fees? | Use for |
|---|---|---|
| `GET /transaction` (List) | **Yes** — `fees` per transaction, in kobo | Authoritative collection fees; complete history; immune to missed webhooks |
| `GET /transaction/verify/:ref` | **Yes** — `fees` | Per-payment capture at confirmation time |
| `GET /balance/ledger` | **Yes** — on *every* movement, including transfers | The only source of real payout fees |
| `GET /settlement` | No fee field | What actually hit the bank (already net of fees) |
| `GET /transaction/totals` | **No** — only `total_transactions`, `total_volume`, `pending_transfers` | Volume sanity checks only. It cannot tell you fees |
| `GET /transfer` | `fee_charged` when present; otherwise estimated until ledger sync | Payout status, missed-webhook reconciliation, and transfer fees |

The practical consequence: **never compute fees from `transaction/totals`** — it has no fee field. Collections come from the Transaction API, payouts from the balance ledger.

Paystack's own guidance is not to hardcode fee percentages or caps, but to read the fee from the transaction response. That is exactly what this system does — the fee schedule in `DEFAULT_FEE_SCHEDULE` is a clearly-flagged fallback, never the primary path.

## Windowing

Fees are windowed on `paid_at` (when Paystack processed the movement); platform earnings are windowed on order `created_at`. For a rolling period the two agree closely, but an order paid just after a window boundary can land its fee in the next window. If you need the two perfectly tied, join through `PaystackFeeRecord.order`.

## Setup

**1. Migrate:**

```bash
python manage.py migrate wallet
```

**2. Import history from Paystack.** This is the one that matters, and it should be run before the others. It walks Paystack's Transaction List API and records the reported fee on every successful charge — including payments whose webhook never arrived and anything predating fee capture. No estimates:

```bash
python manage.py import_paystack_transactions --dry-run
```

```bash
python manage.py import_paystack_transactions --since 2025-01-01
```

The output reports an `unlinked` count: transactions whose fee was recorded but which couldn't be matched to one of our orders. A few are normal (test charges, dashboard payments). A lot suggests reference drift worth investigating.

Import successful payouts too. This is what repairs local withdrawals that
remained pending because a `transfer.success` webhook was missed:

```bash
python manage.py sync_paystack_transfers --since 2025-01-01
```

**3. Backfill from stored payloads (optional).** Replays the Paystack payloads already in `WalletTransaction.response_data`. Largely redundant once step 2 has run, but it also covers payouts and can fill in orders the Transaction API window missed:

```bash
python manage.py backfill_paystack_fees --estimate-missing
```

`--estimate-missing` covers paid orders with no stored payload by applying the fee schedule, flagged as estimates.

**4. Reconcile with Paystack's actuals:**

```bash
python manage.py sync_paystack_fees
```

Safe to run repeatedly — it only corrects rows. Worth scheduling nightly so payout estimates become reported numbers automatically.

**4. Webhook coverage.** Fee accuracy depends on Paystack delivering events. Confirm the Paystack dashboard has a webhook pointing at `/wallet/transactions/webhook/` with `charge.success`, `transfer.success`, `transfer.failed`, and `transfer.reversed` enabled. Without `transfer.*`, payout fees stay estimated until the ledger sync runs.
