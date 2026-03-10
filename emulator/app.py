import copy
import json
import os
import re
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


PAYMENT_INTENTS = {}
CHARGES = {}
REFUNDS = {}
IDEMPOTENCY_CACHE = {}
IDEMPOTENCY_KEY_REGISTRY = {}

VALID_CURRENCIES = {"usd", "eur", "inr", "gbp", "cad", "aud", "sgd", "jpy"}
VALID_CAPTURE_METHODS = {"automatic", "automatic_async", "manual"}
MIN_CHARGE_AMOUNT = 50
MAX_CHARGE_AMOUNT = 99_999_999
CANCELABLE_STATUSES = {
    "requires_payment_method",
    "requires_capture",
    "requires_confirmation",
    "requires_action",
    "processing",
}


def _json_response(handler: BaseHTTPRequestHandler, status_code: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _error_response(handler: BaseHTTPRequestHandler, status_code: int, message: str) -> None:
    _json_response(handler, status_code, {"error": {"message": message, "type": "invalid_request_error"}})


def _read_payload(handler: BaseHTTPRequestHandler) -> dict:
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length <= 0:
        return {}

    raw = handler.rfile.read(content_length).decode("utf-8")
    content_type = handler.headers.get("Content-Type", "")

    if "application/json" in content_type:
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    parsed = parse_qs(raw, keep_blank_values=True)
    normalized = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
    return normalized


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def _now() -> int:
    return int(time.time())


def _to_int(value) -> int:
    if isinstance(value, bool):
        raise ValueError("bool is not int")
    if isinstance(value, int):
        return value
    return int(str(value).strip())


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def _sanitize_pi(intent: dict) -> dict:
    return {
        "id": intent["id"],
        "object": "payment_intent",
        "amount": intent["amount"],
        "amount_capturable": intent["amount_capturable"],
        "amount_received": intent["amount_received"],
        "capture_method": intent["capture_method"],
        "confirmation_method": "automatic",
        "created": intent["created"],
        "currency": intent["currency"],
        "last_payment_error": intent.get("last_payment_error"),
        "latest_charge": intent.get("latest_charge"),
        "livemode": False,
        "metadata": intent.get("metadata", {}),
        "payment_method": intent.get("payment_method"),
        "status": intent["status"],
        "canceled_at": intent.get("canceled_at"),
        "cancellation_reason": intent.get("cancellation_reason"),
    }


def _serialize_payload(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _resolve_idempotency(method: str, path: str, payload: dict, idempotency_key: str):
    key = f"{method}|{path}|{idempotency_key}|{_serialize_payload(payload)}"
    cached = IDEMPOTENCY_CACHE.get(key)
    if cached is None:
        return None
    status_code, response_body = cached
    return status_code, copy.deepcopy(response_body)


def _store_idempotency(method: str, path: str, payload: dict, idempotency_key: str, response):
    key = f"{method}|{path}|{idempotency_key}|{_serialize_payload(payload)}"
    IDEMPOTENCY_CACHE[key] = (response[0], copy.deepcopy(response[1]))
    registry_key = f"{method}|{path}|{idempotency_key}"
    IDEMPOTENCY_KEY_REGISTRY[registry_key] = _serialize_payload(payload)


def _idempotency_conflict(method: str, path: str, payload: dict, idempotency_key: str) -> bool:
    registry_key = f"{method}|{path}|{idempotency_key}"
    prior_payload = IDEMPOTENCY_KEY_REGISTRY.get(registry_key)
    if prior_payload is None:
        return False
    return prior_payload != _serialize_payload(payload)


def _create_charge(payment_intent_id: str, amount: int, currency: str, captured: bool) -> str:
    charge_id = _new_id("ch")
    CHARGES[charge_id] = {
        "id": charge_id,
        "payment_intent": payment_intent_id,
        "amount": amount,
        "amount_captured": amount if captured else 0,
        "currency": currency,
        "refunded_amount": 0,
        "created": _now(),
    }
    return charge_id


class StripeEmulatorHandler(BaseHTTPRequestHandler):
    server_version = "StripePaymentIntentsEmulator/0.2"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            _json_response(
                self,
                200,
                {"status": "ok", "service": "stripe-payment-intents-emulator", "timestamp": _now()},
            )
            return

        if parsed.path == "/v1/payment_intents":
            self._list_payment_intents(parsed)
            return

        match = re.match(r"^/v1/payment_intents/(pi_[A-Za-z0-9]+)$", parsed.path)
        if match:
            self._retrieve_payment_intent(match.group(1))
            return

        _error_response(self, 404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = _read_payload(self)
        idempotency_key = self.headers.get("Idempotency-Key", "").strip()

        if idempotency_key:
            if _idempotency_conflict("POST", parsed.path, payload, idempotency_key):
                _json_response(
                    self,
                    400,
                    {
                        "error": {
                            "type": "invalid_request_error",
                            "message": (
                                "Keys for idempotent requests can only be used with the same "
                                "request parameters they were first used with."
                            ),
                        }
                    },
                )
                return
            cached = _resolve_idempotency("POST", parsed.path, payload, idempotency_key)
            if cached:
                _json_response(self, cached[0], cached[1])
                return

        if parsed.path == "/v1/payment_intents":
            response = self._create_payment_intent(payload)
        elif re.match(r"^/v1/payment_intents/(pi_[A-Za-z0-9]+)/confirm$", parsed.path):
            payment_intent_id = parsed.path.split("/")[3]
            response = self._confirm_payment_intent(payment_intent_id, payload)
        elif re.match(r"^/v1/payment_intents/(pi_[A-Za-z0-9]+)/cancel$", parsed.path):
            payment_intent_id = parsed.path.split("/")[3]
            response = self._cancel_payment_intent(payment_intent_id, payload)
        elif re.match(r"^/v1/payment_intents/(pi_[A-Za-z0-9]+)/capture$", parsed.path):
            payment_intent_id = parsed.path.split("/")[3]
            response = self._capture_payment_intent(payment_intent_id, payload)
        elif parsed.path == "/v1/refunds":
            response = self._create_refund(payload)
        else:
            response = (404, {"error": {"message": "Not found", "type": "invalid_request_error"}})

        if idempotency_key and response[0] < 500:
            _store_idempotency("POST", parsed.path, payload, idempotency_key, response)
        _json_response(self, response[0], response[1])

    def log_message(self, fmt: str, *args) -> None:
        return

    def _list_payment_intents(self, parsed) -> None:
        query = parse_qs(parsed.query)
        limit = 10
        if "limit" in query:
            try:
                limit = max(1, min(100, int(query["limit"][0])))
            except ValueError:
                limit = 10

        intents = sorted(PAYMENT_INTENTS.values(), key=lambda x: x["created"], reverse=True)[:limit]
        payload = {
            "object": "list",
            "data": [_sanitize_pi(pi) for pi in intents],
            "has_more": len(PAYMENT_INTENTS) > limit,
            "url": "/v1/payment_intents",
        }
        _json_response(self, 200, payload)

    def _retrieve_payment_intent(self, payment_intent_id: str) -> None:
        intent = PAYMENT_INTENTS.get(payment_intent_id)
        if not intent:
            _error_response(self, 404, "No such payment_intent")
            return
        _json_response(self, 200, _sanitize_pi(intent))

    def _create_payment_intent(self, payload: dict):
        amount = payload.get("amount")
        currency = str(payload.get("currency", "")).strip().lower()

        if amount is None or currency == "":
            return 400, {"error": {"type": "invalid_request_error", "message": "Missing required param"}}

        try:
            amount_int = _to_int(amount)
        except ValueError:
            return 400, {"error": {"type": "invalid_request_error", "message": "Invalid integer for amount"}}

        if amount_int < MIN_CHARGE_AMOUNT:
            return 400, {"error": {"type": "invalid_request_error", "message": "Amount must be >= minimum charge amount"}}

        if amount_int > MAX_CHARGE_AMOUNT:
            return 400, {"error": {"type": "invalid_request_error", "message": "Amount must be <= 99999999"}}

        if currency not in VALID_CURRENCIES:
            return 400, {"error": {"type": "invalid_request_error", "message": "Invalid currency"}}

        payment_intent_id = _new_id("pi")
        capture_method = str(payload.get("capture_method", "automatic_async")).strip()
        if capture_method not in VALID_CAPTURE_METHODS:
            return 400, {"error": {"type": "invalid_request_error", "message": "Invalid capture_method"}}
        payment_method = payload.get("payment_method")
        confirm_now = _to_bool(payload.get("confirm", False))

        intent = {
            "id": payment_intent_id,
            "amount": amount_int,
            "amount_capturable": 0,
            "amount_received": 0,
            "capture_method": capture_method,
            "created": _now(),
            "currency": currency,
            "last_payment_error": None,
            "latest_charge": None,
            "metadata": {},
            "payment_method": payment_method,
            "status": "requires_payment_method",
            "canceled_at": None,
            "cancellation_reason": None,
        }
        PAYMENT_INTENTS[payment_intent_id] = intent

        if confirm_now:
            return self._confirm_payment_intent(payment_intent_id, payload)

        return 200, _sanitize_pi(intent)

    def _confirm_payment_intent(self, payment_intent_id: str, payload: dict):
        intent = PAYMENT_INTENTS.get(payment_intent_id)
        if not intent:
            return 404, {"error": {"type": "invalid_request_error", "message": "No such payment_intent"}}

        if intent["status"] == "canceled":
            return 400, {"error": {"type": "invalid_request_error", "message": "PaymentIntent is canceled"}}

        payment_method = payload.get("payment_method") or intent.get("payment_method")
        if not payment_method:
            intent["last_payment_error"] = {"message": "Missing payment_method"}
            intent["status"] = "requires_payment_method"
            return 400, {"error": {"type": "invalid_request_error", "message": "Missing payment_method"}}

        intent["payment_method"] = payment_method
        capture_method = str(intent.get("capture_method", "automatic_async"))
        if capture_method == "manual":
            intent["status"] = "requires_capture"
            intent["amount_capturable"] = intent["amount"]
            if not intent.get("latest_charge"):
                intent["latest_charge"] = _create_charge(
                    payment_intent_id=payment_intent_id,
                    amount=intent["amount"],
                    currency=intent["currency"],
                    captured=False,
                )
        else:
            intent["status"] = "succeeded"
            intent["amount_received"] = intent["amount"]
            intent["amount_capturable"] = 0
            if not intent.get("latest_charge"):
                intent["latest_charge"] = _create_charge(
                    payment_intent_id=payment_intent_id,
                    amount=intent["amount"],
                    currency=intent["currency"],
                    captured=True,
                )

        return 200, _sanitize_pi(intent)

    def _cancel_payment_intent(self, payment_intent_id: str, payload: dict):
        intent = PAYMENT_INTENTS.get(payment_intent_id)
        if not intent:
            return 404, {"error": {"type": "invalid_request_error", "message": "No such payment_intent"}}

        if intent["status"] == "canceled":
            return 400, {"error": {"type": "invalid_request_error", "message": "PaymentIntent already canceled"}}

        if intent["status"] not in CANCELABLE_STATUSES:
            return 400, {"error": {"type": "invalid_request_error", "message": "PaymentIntent not cancelable"}}

        intent["status"] = "canceled"
        intent["canceled_at"] = _now()
        reason = payload.get("cancellation_reason")
        intent["cancellation_reason"] = reason if reason else None
        intent["amount_capturable"] = 0
        return 200, _sanitize_pi(intent)

    def _capture_payment_intent(self, payment_intent_id: str, payload: dict):
        intent = PAYMENT_INTENTS.get(payment_intent_id)
        if not intent:
            return 404, {"error": {"type": "invalid_request_error", "message": "No such payment_intent"}}

        if intent["status"] != "requires_capture":
            return 400, {"error": {"type": "invalid_request_error", "message": "PaymentIntent is not capturable"}}

        amount_to_capture = payload.get("amount_to_capture")
        if amount_to_capture is None:
            capture_value = intent["amount_capturable"]
        else:
            try:
                capture_value = _to_int(amount_to_capture)
            except ValueError:
                return 400, {"error": {"type": "invalid_request_error", "message": "Invalid amount_to_capture"}}

        if capture_value <= 0 or capture_value > intent["amount_capturable"]:
            return 400, {"error": {"type": "invalid_request_error", "message": "Invalid capture amount"}}

        intent["amount_capturable"] -= capture_value
        intent["amount_received"] += capture_value

        charge_id = intent.get("latest_charge")
        if charge_id and charge_id in CHARGES:
            CHARGES[charge_id]["amount_captured"] = intent["amount_received"]

        final_capture = _to_bool(payload.get("final_capture", True))
        if final_capture or intent["amount_capturable"] == 0:
            intent["status"] = "succeeded"
        else:
            intent["status"] = "requires_capture"

        return 200, _sanitize_pi(intent)

    def _create_refund(self, payload: dict):
        payment_intent_id = payload.get("payment_intent")
        charge_id = payload.get("charge")

        if not payment_intent_id and not charge_id:
            return 400, {"error": {"type": "invalid_request_error", "message": "charge or payment_intent required"}}

        if payment_intent_id:
            intent = PAYMENT_INTENTS.get(payment_intent_id)
            if not intent:
                return 404, {"error": {"type": "invalid_request_error", "message": "No such payment_intent"}}
            charge_id = intent.get("latest_charge")

        if not charge_id or charge_id not in CHARGES:
            return 404, {"error": {"type": "invalid_request_error", "message": "No such charge"}}

        charge = CHARGES[charge_id]
        refundable_amount = max(0, charge["amount_captured"] - charge["refunded_amount"])
        if refundable_amount <= 0:
            return 400, {"error": {"type": "invalid_request_error", "message": "Charge already refunded"}}

        amount_raw = payload.get("amount")
        if amount_raw is None:
            refund_amount = refundable_amount
        else:
            try:
                refund_amount = _to_int(amount_raw)
            except ValueError:
                return 400, {"error": {"type": "invalid_request_error", "message": "Invalid refund amount"}}

        if refund_amount <= 0 or refund_amount > refundable_amount:
            return 400, {"error": {"type": "invalid_request_error", "message": "Refund amount exceeds remaining"}}

        charge["refunded_amount"] += refund_amount
        refund_id = _new_id("re")
        refund = {
            "id": refund_id,
            "object": "refund",
            "status": "succeeded",
            "amount": refund_amount,
            "currency": charge["currency"],
            "charge": charge_id,
            "payment_intent": charge["payment_intent"],
            "reason": payload.get("reason"),
            "created": _now(),
        }
        REFUNDS[refund_id] = refund
        return 200, refund


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), StripeEmulatorHandler)
    print(f"Stripe emulator listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
