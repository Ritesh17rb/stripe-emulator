# API Calls & Live Demo Guide

## API calls the project makes

All calls use **HTTP** against either:
- **Stripe:** `https://api.stripe.com` with `Authorization: Bearer sk_test_...`
- **Emulator:** `http://127.0.0.1:8000` (or the port you set)

Request body format is **`application/x-www-form-urlencoded`** (same as Stripe’s API).

---

### 1. Health check (emulator only)

| Method | Path        | Body | Purpose |
|--------|-------------|------|--------|
| GET    | `/health`   | —    | Check emulator is up before running tests |

---

### 2. PaymentIntents

| Method | Path | Typical body / query | Purpose |
|--------|------|----------------------|--------|
| **GET**  | `/v1/payment_intents` | Query: `limit` (optional) | List payment intents |
| **GET**  | `/v1/payment_intents/{id}` | — | Retrieve one payment intent |
| **POST** | `/v1/payment_intents` | `amount`, `currency`, `capture_method`, `metadata[...]`, etc. | Create payment intent |
| **POST** | `/v1/payment_intents/{id}/confirm` | `payment_method` (e.g. `pm_card_visa`) | Confirm intent |
| **POST** | `/v1/payment_intents/{id}/cancel` | optional: `cancellation_reason` | Cancel intent |
| **POST** | `/v1/payment_intents/{id}/capture` | optional: `amount_to_capture`, `final_capture` | Capture (for manual capture) |

---

### 3. Refunds

| Method | Path | Typical body | Purpose |
|--------|------|--------------|--------|
| **POST** | `/v1/refunds` | `payment_intent` or `charge`, optional `amount`, `reason` | Create refund |

---

### 4. Idempotency

For **POST** requests, the tests (and Stripe) support an **`Idempotency-Key`** header. Same key + same body returns the same response without re-executing (emulator and Stripe both implement this).

---

## How to check and show it live

### Option A: Emulator only (no Stripe key, ~2 min)

**1. Start the emulator** (in one terminal):

```powershell
cd c:\Users\admin\work\stripe-payment-simulator
python emulator/app.py
```

You should see: `Stripe emulator listening on http://127.0.0.1:8000`

**2. In a second terminal**, hit the APIs with PowerShell:

```powershell
# Health
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get

# Create a payment intent (min amount 50 cents, currency usd)
$form = "amount=100&currency=usd&capture_method=manual"
$created = Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/payment_intents" -Method Post -Body $form -ContentType "application/x-www-form-urlencoded"

# Retrieve (use id from create)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/payment_intents/$($created.id)" -Method Get

# List
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/payment_intents" -Method Get
```

**3. Run the test suite against the emulator** (in the second terminal, emulator still running in the first):

```powershell
$env:TARGET = "emulator"
$env:EMULATOR_BASE_URL = "http://127.0.0.1:8000"
python -m pytest test-cases/harness -q
```

**If you see lots of failures (e.g. "Expected capture_method=..., got None"):** the tests are hitting something that isn’t this repo’s emulator (e.g. nothing on 8000 or another app). Start the emulator from this repo in a **separate** terminal first (`python emulator/app.py`), leave it running, then run the commands above. The emulator must be the one in `emulator/app.py` so responses include all required fields.

Show him the pytest output and, if you want, the latest log:

```powershell
Get-Content artifacts\logs\latest_run_emulator.jsonl | Select-Object -First 3
```

---

### Option B: Full dual-target run + reports (~3–5 min)

**1. Put your Stripe test key in `.env`** (if not already):

```
STRIPE_API_KEY=sk_test_...
```

**2. Run the full proof** (runs Stripe first, then starts emulator and runs same suite, then builds reports):

```powershell
cd c:\Users\admin\work\stripe-payment-simulator
python scripts/run_dual_target_suite.py
```

**3. Show him:**

- **API calls in practice:** open `artifacts\logs\latest_run_emulator.jsonl` (or `latest_run_stripe.jsonl`). Each line is one request/response: `request` (method, path, body) and `response` (status_code, body). You can open in VS Code or run:
  ```powershell
  Get-Content artifacts\logs\latest_run_emulator.jsonl | Select-Object -First 1
  ```
- **Pass rates:** `artifacts\reports\pass_rate_summary.json`
- **Doc coverage:** `artifacts\reports\doc_coverage_report.json`

---

### Option C: One manual “story” (create → retrieve → confirm) in browser/Postman

1. Start emulator: `python emulator/app.py`
2. Use **Postman** or **curl** (or PowerShell above):
   - **POST** `http://127.0.0.1:8000/v1/payment_intents`  
     Body (x-www-form-urlencoded): `amount=500&currency=usd&capture_method=manual`
   - **GET** `http://127.0.0.1:8000/v1/payment_intents/{id}` (use `id` from step 1)
   - **POST** `http://127.0.0.1:8000/v1/payment_intents/{id}/confirm`  
     Body: `payment_method=pm_card_visa`

That shows the same three API calls the automated tests use in a flow.

---

## Quick reference: where things are

| What | Where |
|------|--------|
| API implementation (emulator) | `emulator/app.py` |
| Client that sends the API calls | `test-cases/harness/http_client.py` |
| Test cases (paths, methods, bodies) | `test-cases/generated/payment_intents_cases.json` |
| Live request/response logs | `artifacts/logs/latest_run_emulator.jsonl`, `latest_run_stripe.jsonl` |
| Pass rate & doc coverage | `artifacts/reports/pass_rate_summary.json`, `doc_coverage_report.json` |
