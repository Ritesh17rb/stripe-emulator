import pytest
import time

from case_runner import load_generated_cases, run_case


CASES = load_generated_cases()
MAX_NETWORK_RETRIES_PER_CASE = 3


def _case_id(case: dict):
    return case.get("id", "unknown_case")


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_generated_case(case, run_context):
    cfg = run_context["config"]
    logger = run_context["logger"]
    archive_logger = run_context["archive_logger"]
    client = run_context["client"]

    last_runtime_error = None
    for attempt in range(MAX_NETWORK_RETRIES_PER_CASE + 1):
        try:
            passed, step_results, _ = run_case(
                case,
                client=client,
                target=cfg.target,
                logger=logger,
                archive_logger=archive_logger,
            )
            break
        except RuntimeError as runtime_error:
            if "Network failure" not in str(runtime_error):
                raise
            last_runtime_error = runtime_error
            if attempt >= MAX_NETWORK_RETRIES_PER_CASE:
                raise
            time.sleep(0.75 * (attempt + 1))
    else:
        raise last_runtime_error if last_runtime_error else RuntimeError("Unknown case execution failure")

    if not passed:
        failed = next((step for step in step_results if not step["passed"]), None)
        if failed:
            pytest.fail(
                f"Case {case.get('id')} failed at step {failed['step_index']} "
                f"({failed['step_name']}): {failed['error']}"
            )
        pytest.fail(f"Case {case.get('id')} failed without detailed step info")
