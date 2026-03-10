# Coverage Scope Definition

Date: 2026-03-08

## Why Two Traceability Files Exist

- `docs/traceability_matrix.csv`:
  - Broad sentence extraction baseline from selected Stripe sources.
  - Useful for auditability and exploratory coverage analysis.
- `docs/requirements/traceability_scope_core.csv`:
  - Filtered, higher-signal behavioral requirement set.
  - Intended as the primary denominator for the 70% coverage KPI.

## Current Counts

- Broad baseline sentences: 1891
- Core behavioral scope sentences: 577

## KPI Rule for This Project

- Coverage KPI should be computed on `traceability_scope_core.csv`.
- Broad matrix coverage may still be reported as supplemental context.

## Rationale

- Raw API markdown includes heavy parameter schema and navigation text.
- Core scope focuses on executable behavior (create/confirm/cancel/capture/refund, status, errors, idempotency).
- This keeps the metric defensible and aligned to 50-500 test case volume.

