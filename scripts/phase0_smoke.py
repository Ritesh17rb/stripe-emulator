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


def main() -> int:
    if not EMULATOR_APP.exists():
        print("Missing emulator/app.py")
        return 2

    emulator_env = os.environ.copy()
    emulator_env.setdefault("HOST", "127.0.0.1")
    emulator_env.setdefault("PORT", "8010")
    emulator_base_url = f"http://{emulator_env['HOST']}:{emulator_env['PORT']}"

    emulator_proc = subprocess.Popen([sys.executable, str(EMULATOR_APP)], env=emulator_env)

    try:
        if not wait_for_emulator(f"{emulator_base_url}/health"):
            print("Emulator failed to start within timeout")
            return 2

        test_env = os.environ.copy()
        test_env["TARGET"] = "emulator"
        test_env["EMULATOR_BASE_URL"] = emulator_base_url
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(ROOT / "test-cases" / "harness" / "test_smoke.py"),
            "-q",
        ]
        print("Running:", " ".join(cmd))
        return subprocess.call(cmd, env=test_env, cwd=str(ROOT))
    finally:
        if emulator_proc.poll() is None:
            emulator_proc.send_signal(signal.SIGTERM)
            try:
                emulator_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                emulator_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
