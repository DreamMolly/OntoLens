from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

from ontolens.delivery import file_digest, source_manifest


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8]
    run_dir = ROOT / ".runtime" / "validation" / stamp
    run_dir.mkdir(parents=True)
    inputs = source_manifest(ROOT)
    environment = dict(os.environ)
    for name in list(environment):
        if name.startswith(("ONTOLENS_", "TYPESAFE_", "MODEL_", "NEXENT_", "OPENAI_", "ANTHROPIC_")):
            environment.pop(name)
    temp = run_dir / "tmp"
    temp.mkdir()
    environment.update({"ONTOLENS_ROOT": str(ROOT), "ONTOLENS_DB": str(run_dir / "smoke.sqlite3"),
                        "ONTOLENS_WORKSPACE_MODE": "synthetic", "ONTOLENS_LOAD_ENV": "false",
                        "TEMP": str(temp), "TMP": str(temp), "TMPDIR": str(temp),
                        "PIP_CACHE_DIR": str(ROOT / ".runtime/pip-cache"), "PYTHONIOENCODING": "utf-8",
                        "PLAYWRIGHT_BROWSERS_PATH": str(ROOT / ".runtime/playwright-browsers")})
    for _ in range(128):
        with socket.socket() as listener:
            try:
                listener.bind(("127.0.0.1", 12000 + secrets.randbelow(48000)))
            except OSError:
                continue
            port = listener.getsockname()[1]
            break
    else:
        raise RuntimeError("Unable to allocate a browser-safe loopback port")
    url = f"http://127.0.0.1:{port}"
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    rows = []
    with (run_dir / "server.log").open("w", encoding="utf-8") as server_log:
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "ontolens.web:create_app", "--factory",
                                   "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=environment,
                                  stdout=server_log, stderr=subprocess.STDOUT, creationflags=creationflags)
        try:
            with httpx.Client(trust_env=False, timeout=1) as client:
                for attempt in range(100):
                    try:
                        if client.get(url + "/api/status").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if server.poll() is not None:
                        raise RuntimeError("Smoke server exited; inspect " + str(run_dir / "server.log"))
                    time.sleep(0.2)
                else:
                    raise RuntimeError("Smoke server did not become ready")
            commands = [
                ("pytest", [sys.executable, "-m", "pytest", "-q", "--basetemp", str(run_dir / "pytest"),
                            "--junitxml", str(run_dir / "pytest.xml")]),
                ("browser", [sys.executable, "tests/browser_smoke.py", "--url", url]),
                ("mcp", [sys.executable, "tests/mcp_smoke.py", "--url", url + "/mcp/"]),
                ("assets", [sys.executable, "scripts/evaluate_assets.py", "--output", "artifacts/asset-recognition-report.json"]),
                ("jev", [sys.executable, "scripts/verify_jev.py"]),
                ("pip", [sys.executable, "-m", "pip", "check"]),
                ("javascript", [sys.executable, "scripts/check_javascript.py"]),
            ]
            for name, command in commands:
                log_path = run_dir / (name + ".log")
                with log_path.open("w", encoding="utf-8") as log:
                    result = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                            timeout=300, creationflags=creationflags)
                    if name == "pytest" and result.returncode == 0:
                        result = subprocess.run([sys.executable, "scripts/summarize_ui_qa.py", "--junit", str(run_dir / "pytest.xml")],
                                                cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                                timeout=30, creationflags=creationflags)
                rows.append({"name": name, "command": subprocess.list2cmdline(command),
                             "exit_code": result.returncode, "log": str(log_path.relative_to(ROOT)),
                             "log_sha256": file_digest(log_path)})
                print(f"{name}: exit={result.returncode}")
                print(log_path.read_text(encoding="utf-8")[-1800:])
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
    report = {"run_dir": str(run_dir.relative_to(ROOT)), "scope": "isolated synthetic database; no live model requests",
              "input_manifest": inputs, "checks": rows,
              "passed": all(row["exit_code"] == 0 for row in rows) and inputs == source_manifest(ROOT)}
    output = ROOT / "artifacts/local-validation-report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("report=" + str(output))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
