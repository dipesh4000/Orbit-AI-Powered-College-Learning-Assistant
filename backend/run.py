"""Start Orbit with its project virtual environment, from any working directory."""

import subprocess
import sys
from pathlib import Path


def main():
    backend = Path(__file__).resolve().parent
    candidates = [backend / ".venv/Scripts/python.exe", backend / ".venv/bin/python"]
    python = next((path for path in candidates if path.is_file()), None)
    if python is None:
        print(
            "Orbit's virtual environment is missing. From backend/, run:\n"
            "  uv venv .venv\n"
            "  uv pip install --python .venv/Scripts/python.exe -r requirements.txt",
            file=sys.stderr,
        )
        return 1
    try:
        return subprocess.call(
            [
                str(python),
                "-m",
                "uvicorn",
                "orbit.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                *sys.argv[1:],
            ],
            cwd=backend,
        )
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
