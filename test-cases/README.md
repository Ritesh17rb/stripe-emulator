# Test Cases

This folder contains generated case data and the reusable dual-target harness.

## Install

```bash
python -m pip install -r ../requirements-dev.txt
```

## Run Against Emulator

1. Start emulator:

```bash
python ../emulator/app.py
```

2. Run tests:

```bash
# PowerShell
$env:TARGET="emulator"
python -m pytest harness -q
```

Generated suite file:

- `generated/payment_intents_cases.json` (90 docs-linked cases)

## Run Against Stripe Test API

```bash
# PowerShell
$env:TARGET="stripe"
$env:STRIPE_API_KEY="sk_test_..."
python -m pytest harness -q
```

## One-Command Local Smoke

From repo root:

```bash
python scripts/phase0_smoke.py
```

## One-Command Dual-Target Run

From repo root:

```bash
python scripts/run_dual_target_suite.py
```
