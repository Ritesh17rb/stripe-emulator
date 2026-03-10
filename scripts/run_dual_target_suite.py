import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib import request
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
EMULATOR_APP = ROOT / "emulator" / "app.py"


def has_stripe_key() -> bool:
    env_key = os.environ.get("STRIPE_API_KEY", "").strip()
    if env_key:
        return True
    dotenv = ROOT / ".env"
    if not dotenv.exists():
        return False
    for raw_line in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "STRIPE_API_KEY" and value.strip():
            return True
    return False


def wait_for_emulator(url: str, timeout_seconds: int = 15) -> bool:
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            with request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except URLError:
            time.sleep(0.25)
        except Exception:
            time.sleep(0.25)
    return False


def run_pytest(target: str, extra_env: dict | None = None) -> int:
    env = os.environ.copy()
    env["TARGET"] = target
    env["RUN_ID"] = str(int(time.time()))
    if extra_env:
        env.update(extra_env)
    cmd = [sys.executable, "-m", "pytest", str(ROOT / "test-cases" / "harness"), "-q"]
    print("Running:", " ".join(cmd), f"(TARGET={target})")
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


def run_emulator_suite() -> int:
    env = os.environ.copy()
    env.setdefault("HOST", "127.0.0.1")
    env["PORT"] = env.get("PORT", "8010")
    emulator_base_url = f"http://{env['HOST']}:{env['PORT']}"
    proc = subprocess.Popen([sys.executable, str(EMULATOR_APP)], cwd=str(ROOT), env=env)
    try:
        if not wait_for_emulator(f"{emulator_base_url}/health"):
            print("Emulator failed to start.")
            return 2
        return run_pytest("emulator", {"EMULATOR_BASE_URL": emulator_base_url})
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def main() -> int:
    if not has_stripe_key():
        print("Missing STRIPE_API_KEY in env or .env")
        return 2

    rc1 = run_pytest("stripe")
    rc2 = run_emulator_suite()
    rc3 = subprocess.call([sys.executable, str(ROOT / "scripts" / "phase6_build_reports.py")], cwd=str(ROOT))
    if rc1 != 0 or rc2 != 0 or rc3 != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
