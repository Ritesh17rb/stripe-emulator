import copy
import json
import re
import time
from pathlib import Path


def load_generated_cases() -> list[dict]:
    cases_path = Path(__file__).resolve().parents[1] / "generated" / "payment_intents_cases.json"
    content = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = content.get("cases", [])
    if not isinstance(cases, list):
        raise RuntimeError("Invalid generated case file format")
    return cases


def run_case(case: dict, *, client, target: str, logger, archive_logger):
    ctx = {"case_id": case.get("id", "unknown_case"), "target": target}
    case_start = time.time()
    step_results = []

    for index, step in enumerate(case.get("steps", []), start=1):
        step_start = time.time()
        rendered_request = _render(copy.deepcopy(step.get("request", {})), ctx)
        method = rendered_request.get("method", "GET").upper()
        path = rendered_request.get("path", "")
        body = rendered_request.get("body", {})
        headers = rendered_request.get("headers", {})

        response = client.request(method=method, path=path, form_data=body, headers=headers)
        ok, assertion_error = _evaluate_assertions(step.get("assert", {}), response.status_code, response.body, ctx)

        save_spec = step.get("save", {})
        for variable_name, json_path in save_spec.items():
            value = _get_path(response.body, json_path)
            if value is not None:
                ctx[variable_name] = value

        duration_ms = int((time.time() - step_start) * 1000)
        record = {
            "case_id": case.get("id"),
            "case_title": case.get("title"),
            "step_index": index,
            "step_name": step.get("name", f"step_{index}"),
            "doc_refs": case.get("doc_refs", []),
            "request": rendered_request,
            "response": {"status_code": response.status_code, "body": response.body},
            "assertions": step.get("assert", {}),
            "passed": ok,
            "duration_ms": duration_ms,
            "error": assertion_error,
        }
        for sink in (logger, archive_logger):
            sink.log(
                case_id=record["case_id"],
                target=target,
                request_data=record["request"],
                response_data=record["response"],
                assertions=record["assertions"],
                passed=record["passed"],
                duration_ms=record["duration_ms"],
                error=record["error"],
            )
        step_results.append(record)
        if not ok:
            return False, step_results, int((time.time() - case_start) * 1000)

    return True, step_results, int((time.time() - case_start) * 1000)


def _render(value, context: dict):
    if isinstance(value, str):
        return _render_str(value, context)
    if isinstance(value, dict):
        return {k: _render(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_render(item, context) for item in value]
    return value


def _render_str(text: str, context: dict) -> str:
    pattern = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")

    def replace(match):
        key = match.group(1)
        return str(context.get(key, match.group(0)))

    return pattern.sub(replace, text)


def _evaluate_assertions(assertions: dict, status_code: int, body: dict, context: dict):
    expected_code = assertions.get("status_code")
    if expected_code is not None and status_code != expected_code:
        return False, f"Expected status_code={expected_code}, got {status_code}"

    expected_codes = assertions.get("status_code_in")
    if expected_codes is not None and status_code not in expected_codes:
        return False, f"Expected status_code in {expected_codes}, got {status_code}"

    for path in assertions.get("exists", []):
        if _get_path(body, path) is None:
            return False, f"Expected field to exist: {path}"

    for path, value in assertions.get("equals", {}).items():
        actual = _get_path(body, path)
        if actual != value:
            return False, f"Expected {path}={value}, got {actual}"

    for path, values in assertions.get("in", {}).items():
        actual = _get_path(body, path)
        if actual not in values:
            return False, f"Expected {path} in {values}, got {actual}"

    for path, prefix in assertions.get("prefix", {}).items():
        actual = _get_path(body, path)
        if not isinstance(actual, str) or not actual.startswith(prefix):
            return False, f"Expected {path} prefix {prefix}, got {actual}"

    for path, min_value in assertions.get("gte", {}).items():
        actual = _get_path(body, path)
        if actual is None or actual < min_value:
            return False, f"Expected {path} >= {min_value}, got {actual}"

    for path, max_value in assertions.get("lte", {}).items():
        actual = _get_path(body, path)
        if actual is None or actual > max_value:
            return False, f"Expected {path} <= {max_value}, got {actual}"

    for path, context_key in assertions.get("context_equals", {}).items():
        actual = _get_path(body, path)
        expected = context.get(context_key)
        if actual != expected:
            return False, f"Expected {path} to equal context[{context_key}]={expected}, got {actual}"

    return True, None


def _get_path(data: dict, path: str):
    current = data
    for token in path.split("."):
        if isinstance(current, list):
            try:
                index = int(token)
                current = current[index]
            except (ValueError, IndexError):
                return None
            continue
        if not isinstance(current, dict):
            return None
        if token not in current:
            return None
        current = current[token]
    return current

