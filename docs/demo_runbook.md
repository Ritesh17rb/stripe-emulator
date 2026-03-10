# Demo Runbook

Date: 2026-03-08

## 1. Set Stripe Test Credential

Use `.env` in repo root:

```bash
STRIPE_API_KEY=rk_test_...
```

Do not commit secrets.

## 2. Generate Traceable Test Corpus

```bash
python scripts/phase2_generate_cases.py
```

Expected:
- 90 generated cases in `test-cases/generated/payment_intents_cases.json`
- Traceability links in `docs/requirements/test_case_traceability.csv`

## 3. Run Stripe + Emulator with the Same Suite

```bash
python scripts/run_dual_target_suite.py
```

What this does:
- Runs `pytest` on Stripe target
- Starts local emulator on a dedicated port
- Runs the same suite on emulator target
- Builds pass-rate and coverage reports

## 4. Present Output

Open:
- `artifacts/reports/pass_rate_summary.json`
- `artifacts/reports/doc_coverage_report.json`
- `docs/data_story.md`

Key talking points:
- Same suite ran on both targets.
- High pass rate on Stripe and emulator.
- Tests are mapped to Stripe documentation sentences.

