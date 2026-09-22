"""Windows development launcher; owns and cleans up only its child processes."""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def available(port):
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def check(sandbox=False):
    if not (ROOT / "frontend/node_modules/vite/bin/vite.js").exists():
        raise RuntimeError(
            "Frontend dependencies missing. Run start.bat to install them."
        )
    if not shutil.which("node"):
        raise RuntimeError("Node.js is not on PATH.")
    if not sandbox:
        from orbit.config import settings

        if not settings.database_url or "USER:PASSWORD@HOST" in settings.database_url:
            target = ROOT / ".env"
            raise RuntimeError(
                f"Set DATABASE_URL in {target} (template: backend/.env.example), or use start.bat --sandbox."
            )
        if not settings.database_url.startswith(
            ("postgresql://", "postgresql+psycopg://")
        ):
            raise RuntimeError("DATABASE_URL must be a PostgreSQL URL.")
        if settings.cookie_secure or settings.cookie_samesite == "none":
            raise RuntimeError(
                "Local HTTP requires COOKIE_SECURE=false and COOKIE_SAMESITE=lax or strict."
            )
        if "http://localhost:5173" not in settings.allowed_origins:
            raise RuntimeError(
                "For local development set ALLOWED_ORIGIN=http://localhost:5173."
            )


def stop(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sandbox", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    check(args.sandbox)
    if args.check:
        print(
            "Dependencies and local configuration look ready. Database connectivity was not checked; no migrations were run."
        )
        return
    api_port, web_port = (8011, 4176) if args.sandbox else (8000, 5173)
    for port in (api_port, web_port):
        if not available(port):
            raise RuntimeError(
                f"Port {port} is in use. Stop the existing server and retry."
            )
    if args.sandbox:
        print(
            "SANDBOX: disposable SQLite database. Records reset on shutdown; AI credentials disabled.",
            flush=True,
        )
        backend_command = [sys.executable, "tests/personal_server.py"]
    else:
        print(
            "Applying personal workspace migrations to the configured PostgreSQL database...",
            flush=True,
        )
        result = subprocess.run(
            [sys.executable, "-m", "orbit.migrate"], cwd=BACKEND, check=False
        )
        if result.returncode:
            raise RuntimeError(
                "Migration failed. Check DATABASE_URL and network access. Servers were not started."
            )
        backend_command = [
            sys.executable,
            "-m",
            "uvicorn",
            "orbit.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
            "--reload",
        ]
    logs = BACKEND / "logs"
    logs.mkdir(exist_ok=True)
    (BACKEND / "data").mkdir(exist_ok=True)
    env = {**os.environ, "ORBIT_API_PROXY": f"http://127.0.0.1:{api_port}"}
    # Browser-test fixtures are never enabled by the interactive sandbox launcher.
    env.pop("ORBIT_TEST_CODOLIO", None)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    processes = []
    with (
        (logs / "dev-backend.log").open("w", encoding="utf-8") as backend_log,
        (logs / "dev-frontend.log").open("w", encoding="utf-8") as frontend_log,
    ):
        sandbox_directory = None
        try:
            if args.sandbox:
                sandbox_directory = Path(
                    tempfile.mkdtemp(prefix="orbit-sandbox-", dir=BACKEND / "data")
                )
                env["ORBIT_SANDBOX_DIR"] = str(sandbox_directory)
            processes.append(
                subprocess.Popen(
                    backend_command,
                    cwd=BACKEND,
                    env=env,
                    stdout=backend_log,
                    stderr=subprocess.STDOUT,
                    creationflags=flags,
                )
            )
            processes.append(
                subprocess.Popen(
                    [
                        shutil.which("node"),
                        "node_modules/vite/bin/vite.js",
                        "--host",
                        "localhost",
                        "--port",
                        str(web_port),
                        "--strictPort",
                    ],
                    cwd=ROOT / "frontend",
                    env=env,
                    stdout=frontend_log,
                    stderr=subprocess.STDOUT,
                    creationflags=flags,
                )
            )
            url = f"http://localhost:{web_port}"
            pending = {f"http://127.0.0.1:{api_port}/api/health", url}
            deadline = time.monotonic() + 60
            while pending and time.monotonic() < deadline:
                if any(p.poll() is not None for p in processes):
                    raise RuntimeError(
                        f"A server stopped during startup. See logs in {logs}."
                    )
                for endpoint in list(pending):
                    try:
                        with urlopen(endpoint, timeout=1) as response:
                            if response.status == 200:
                                pending.remove(endpoint)
                    except (URLError, TimeoutError):
                        pass
                time.sleep(0.3)
            if pending:
                raise RuntimeError(f"Server startup timed out. See logs in {logs}.")
            print(
                f"Orbit is ready: {url}\nAPI docs: http://127.0.0.1:{api_port}/docs\nLogs: {logs}\nKeep this window open. Press Ctrl+C to stop both servers.",
                flush=True,
            )
            if not args.no_browser:
                webbrowser.open(url)
            while all(p.poll() is None for p in processes):
                time.sleep(0.5)
            raise RuntimeError(f"A server exited. Check logs in {logs}.")
        except KeyboardInterrupt:
            print("\nStopping Orbit...", flush=True)
        finally:
            for process in reversed(processes):
                stop(process)
            if sandbox_directory is not None:
                # Verify the absolute owned target before recursive removal on Windows.
                target = sandbox_directory.resolve()
                if target.parent != (BACKEND / "data").resolve():
                    raise RuntimeError(
                        "Sandbox cleanup target is outside the expected data folder."
                    )
                shutil.rmtree(target)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"Orbit: {exc}", file=sys.stderr)
        sys.exit(1)
