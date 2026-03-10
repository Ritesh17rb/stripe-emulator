import os
from dataclasses import dataclass
from pathlib import Path


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _load_dotenv() -> None:
    root = Path(__file__).resolve().parents[2]
    dotenv_path = root / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class RunConfig:
    target: str
    stripe_api_key: str
    emulator_base_url: str
    stripe_base_url: str
    test_seed: int
    http_retries: int
    retry_backoff_seconds: float
    request_timeout_seconds: int
    run_id: str

    @property
    def base_url(self) -> str:
        return self.stripe_base_url if self.target == "stripe" else self.emulator_base_url


def load_config() -> RunConfig:
    _load_dotenv()
    return RunConfig(
        target=os.environ.get("TARGET", "emulator").strip().lower(),
        stripe_api_key=os.environ.get("STRIPE_API_KEY", "").strip(),
        emulator_base_url=os.environ.get("EMULATOR_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
        stripe_base_url=os.environ.get("STRIPE_BASE_URL", "https://api.stripe.com").rstrip("/"),
        test_seed=_get_int("TEST_SEED", 42),
        http_retries=_get_int("HTTP_RETRIES", 6),
        retry_backoff_seconds=_get_float("RETRY_BACKOFF_SECONDS", 0.75),
        request_timeout_seconds=_get_int("REQUEST_TIMEOUT_SECONDS", 20),
        run_id=os.environ.get("RUN_ID", "").strip(),
    )
