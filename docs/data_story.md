# Data Story: Stripe Payment Simulator and Test-Driven Migration

Date: 2026-03-08

## Objective

Demonstrate a test-driven migration methodology by:
- generating tests from Stripe documentation,
- running the same suite against live Stripe test API and local emulator,
- using logs and reports to prove behavioral parity.

## Inputs

- Stripe doc sources: `docs/stripe_sources.md`
- Requirement extraction:
  - broad matrix: `docs/traceability_matrix.csv`
  - mapped matrix: `docs/traceability_matrix_mapped.csv`
  - core scope denominator: `docs/requirements/traceability_scope_core.csv`
- Prompt/process log: `artifacts/logs/prompt_log.jsonl`

## What Was Built

- Emulator API: `emulator/app.py`
  - PaymentIntent create/retrieve/list/confirm/cancel/capture
  - Refund create
  - Idempotency-key behavior
- Dual-target harness: `test-cases/harness/`
  - same assertions for `TARGET=stripe` and `TARGET=emulator`
- Generated test corpus: `test-cases/generated/payment_intents_cases.json`
  - 248 generated, docs-linked cases (within required 50-500 range)
  - plus 2 smoke cases in harness

## Final Measured Results

From `artifacts/reports/pass_rate_summary.json`:
- Stripe: 250/250 passed (100.0%)
- Emulator: 250/250 passed (100.0%)
- Combined target executions: 500/500 passed (100.0%)

From `artifacts/reports/doc_coverage_report.json`:
- Core-scope denominator: 577 documentation sentences
- Covered by mapped tests: 559
- Coverage: 96.88%

## Why This Proves the Methodology

- Tests were generated and linked to documentation requirements.
- The same suite validates both systems without rewriting assertions.
- Emulator behavior is iteratively aligned until it passes the same checks as Stripe.
- The process is reproducible from CLI and captured in logs/reports.

## Reproducibility

Run:

```bash
python scripts/phase2_generate_cases.py
python scripts/run_dual_target_suite.py
```

Then inspect:
- `artifacts/reports/pass_rate_summary.json`
- `artifacts/reports/doc_coverage_report.json`
