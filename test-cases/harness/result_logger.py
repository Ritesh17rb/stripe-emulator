import json
from pathlib import Path
from typing import Optional


class JsonlResultLogger:
    REDACT_KEYS = {"client_secret", "authorization", "api_key"}

    def __init__(self, filepath: Path, truncate: bool = False) -> None:
        self.filepath = filepath
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        if truncate:
            self.filepath.write_text("", encoding="utf-8")

    def log(
        self,
        *,
        case_id: str,
        target: str,
        request_data: dict,
        response_data: dict,
        assertions: dict,
        passed: bool,
        duration_ms: int,
        error: Optional[str] = None,
    ) -> None:
        record = {
            "case_id": case_id,
            "target": target,
            "request": self._redact(request_data),
            "response": self._redact(response_data),
            "assertions": assertions,
            "passed": passed,
            "duration_ms": duration_ms,
            "error": error,
        }
        with self.filepath.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _redact(self, value):
        if isinstance(value, dict):
            redacted = {}
            for key, item in value.items():
                if key.lower() in self.REDACT_KEYS:
                    redacted[key] = "[REDACTED]"
                else:
                    redacted[key] = self._redact(item)
            return redacted
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return value
