import time


def test_health_or_api_reachability(run_context):
    cfg = run_context["config"]
    logger = run_context["logger"]
    archive_logger = run_context["archive_logger"]
    client = run_context["client"]

    case_id = "smoke_reachability_001"
    start = time.time()

    if cfg.target == "emulator":
        response = client.get("/health")
        passed = response.status_code == 200 and response.body.get("status") == "ok"
        assertions = {"expected_status_code": 200, "expected_status_field": "ok"}
        request_data = {"method": "GET", "path": "/health"}
    else:
        response = client.get("/v1/payment_intents?limit=1")
        passed = response.status_code in (200, 401)
        assertions = {"expected_status_code_in": [200, 401]}
        request_data = {"method": "GET", "path": "/v1/payment_intents?limit=1"}

    duration_ms = int((time.time() - start) * 1000)
    for sink in (logger, archive_logger):
        sink.log(
            case_id=case_id,
            target=cfg.target,
            request_data=request_data,
            response_data={"status_code": response.status_code, "body": response.body},
            assertions=assertions,
            passed=passed,
            duration_ms=duration_ms,
            error=None if passed else "Reachability/assertion mismatch",
        )
    assert passed


def test_payment_intent_create_minimal(run_context):
    cfg = run_context["config"]
    logger = run_context["logger"]
    archive_logger = run_context["archive_logger"]
    client = run_context["client"]

    case_id = "smoke_create_payment_intent_001"
    request_payload = {"amount": "2000", "currency": "usd"}

    start = time.time()
    response = client.post("/v1/payment_intents", request_payload)
    duration_ms = int((time.time() - start) * 1000)

    body = response.body
    payment_intent_id = body.get("id", "")
    is_pi = isinstance(payment_intent_id, str) and payment_intent_id.startswith("pi_")
    is_object = body.get("object") == "payment_intent"
    passed = response.status_code == 200 and is_pi and is_object

    for sink in (logger, archive_logger):
        sink.log(
            case_id=case_id,
            target=cfg.target,
            request_data={"method": "POST", "path": "/v1/payment_intents", "body": request_payload},
            response_data={"status_code": response.status_code, "body": body},
            assertions={
                "expected_status_code": 200,
                "expected_id_prefix": "pi_",
                "expected_object": "payment_intent",
            },
            passed=passed,
            duration_ms=duration_ms,
            error=None if passed else "Create payment_intent assertion mismatch",
        )
    assert passed
