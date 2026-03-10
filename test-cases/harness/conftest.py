import random
import time
from pathlib import Path

import pytest

from config import load_config
from http_client import ApiClient
from result_logger import JsonlResultLogger


@pytest.fixture(scope="session")
def run_context():
    cfg = load_config()
    random.seed(cfg.test_seed)

    if cfg.target not in {"stripe", "emulator"}:
        raise RuntimeError("TARGET must be one of: stripe, emulator")

    if cfg.target == "stripe" and not cfg.stripe_api_key:
        pytest.skip("STRIPE_API_KEY is required when TARGET=stripe")

    artifacts_root = Path(__file__).resolve().parents[2] / "artifacts" / "logs"
    run_token = cfg.run_id or str(int(time.time()))
    log_file = artifacts_root / f"latest_run_{cfg.target}.jsonl"
    archive_log_file = artifacts_root / f"run_{run_token}_{cfg.target}.jsonl"
    logger = JsonlResultLogger(log_file, truncate=True)
    archive_logger = JsonlResultLogger(archive_log_file, truncate=True)

    client = ApiClient(
        base_url=cfg.base_url,
        target=cfg.target,
        stripe_api_key=cfg.stripe_api_key,
        timeout_seconds=cfg.request_timeout_seconds,
        retries=cfg.http_retries,
        retry_backoff_seconds=cfg.retry_backoff_seconds,
    )

    return {"config": cfg, "logger": logger, "archive_logger": archive_logger, "client": client}
