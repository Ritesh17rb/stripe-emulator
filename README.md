# Stripe Payment Simulator

CLI-first Stripe PaymentIntents emulator + docs-traceable dual-target tests.

- `test-cases/` contains test harness and generated-case placeholders.
- `emulator/` contains a local Stripe-like server entrypoint (`app.py`).
- `artifacts/logs/` and `artifacts/reports/` are ready for run outputs.

## Quick Start

1. Install dev dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

2. Generate docs-linked test corpus (90 generated cases):

```bash
python scripts/phase2_generate_cases.py
```

3. Run one-command local smoke test (starts emulator, runs smoke tests, stops emulator):

```bash
python scripts/phase0_smoke.py
```

4. Run full suite on both Stripe and emulator + build reports:

```bash
python scripts/run_dual_target_suite.py
```

5. Run tests directly on a selected target:

```bash
# Emulator target
set TARGET=emulator
python -m pytest test-cases/harness -q

# Stripe target (PowerShell)
$env:TARGET="stripe"
$env:STRIPE_API_KEY="sk_test_..."
python -m pytest test-cases/harness -q
```

## Phase 1 Bootstrap Command

Generate sentence-level traceability files from Stripe docs:

```bash
python scripts/phase1_ingest_docs.py
```

## Reports

- Pass rate summary: `artifacts/reports/pass_rate_summary.json`
- Documentation coverage: `artifacts/reports/doc_coverage_report.json`
- Data story: `docs/data_story.md`
- Demo runbook: `docs/demo_runbook.md`
