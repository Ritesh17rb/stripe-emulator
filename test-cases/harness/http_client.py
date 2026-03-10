import json
import socket
import time
from dataclasses import dataclass
from urllib import parse, request
from urllib.error import HTTPError, URLError


@dataclass
class HttpResponse:
    status_code: int
    body: dict
    raw_text: str


class ApiClient:
    def __init__(
        self,
        base_url: str,
        target: str,
        stripe_api_key: str,
        timeout_seconds: int,
        retries: int,
        retry_backoff_seconds: float,
    ) -> None:
        self.base_url = base_url
        self.target = target
        self.stripe_api_key = stripe_api_key
        self.timeout_seconds = timeout_seconds
        self.retries = max(0, retries)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    def get(self, path: str, headers: dict | None = None) -> HttpResponse:
        return self._send("GET", path, {}, headers or {})

    def post(self, path: str, form_data: dict, headers: dict | None = None) -> HttpResponse:
        return self._send("POST", path, form_data, headers or {})

    def request(self, method: str, path: str, form_data: dict | None = None, headers: dict | None = None) -> HttpResponse:
        return self._send(method.upper(), path, form_data or {}, headers or {})

    def _headers(self, custom_headers: dict) -> dict:
        headers = {"User-Agent": "stripe-payment-simulator-tests/0.1"}
        if self.target == "stripe":
            headers["Authorization"] = f"Bearer {self.stripe_api_key}"
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers.update(custom_headers)
        return headers

    def _send(self, method: str, path: str, form_data: dict, custom_headers: dict) -> HttpResponse:
        url = f"{self.base_url}{path}"
        body_bytes = None
        if method == "POST":
            body_bytes = parse.urlencode(form_data, doseq=True).encode("utf-8")

        last_error = None
        for attempt in range(self.retries + 1):
            req = request.Request(url=url, data=body_bytes, headers=self._headers(custom_headers), method=method)
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    raw = resp.read().decode("utf-8")
                    parsed = _safe_json(raw)
                    return HttpResponse(status_code=resp.status, body=parsed, raw_text=raw)
            except HTTPError as http_error:
                raw = http_error.read().decode("utf-8")
                parsed = _safe_json(raw)
                status_code = int(http_error.code)
                if attempt < self.retries and status_code in (429, 500, 502, 503, 504):
                    time.sleep(self.retry_backoff_seconds * (attempt + 1))
                    continue
                return HttpResponse(status_code=status_code, body=parsed, raw_text=raw)
            except (URLError, TimeoutError, socket.timeout) as url_error:
                last_error = url_error
                if attempt < self.retries:
                    time.sleep(self.retry_backoff_seconds * (attempt + 1))
                    continue
                raise RuntimeError(f"Network failure for {url}: {url_error}") from url_error

        raise RuntimeError(f"Request failed without response for {url}: {last_error}")


def _safe_json(raw_text: str) -> dict:
    try:
        parsed = json.loads(raw_text)
        return parsed if isinstance(parsed, dict) else {"raw": parsed}
    except json.JSONDecodeError:
        return {"raw_text": raw_text}
