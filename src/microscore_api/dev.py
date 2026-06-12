"""Local one-command launcher for the MicroScore web prototype."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from microscore.paths import PROJECT_ROOT

from .seed import seed_demo_data

DEFAULT_HOST = "127.0.0.1"
API_PORT_CANDIDATES = (8010, 8011, 8012, 8000)
WEB_PORT_CANDIDATES = (5173, 5174, 5175, 5180)
WEB_ROOT = PROJECT_ROOT / "apps" / "web"


def _port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        return probe.connect_ex((host, port)) != 0


def _pick_port(host: str, candidates: tuple[int, ...]) -> int:
    for port in candidates:
        if _port_is_free(host, port):
            return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


def _wait_for_health(api_base: str, timeout_seconds: float = 20.0) -> bool:
    deadline = time.time() + timeout_seconds
    health_url = f"{api_base}/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1.5) as response:
                return response.status == 200
        except OSError:
            time.sleep(0.35)
    return False


def _start_process(command: list[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(command, cwd=PROJECT_ROOT)


def parse_args() -> object:
    import argparse

    parser = argparse.ArgumentParser(
        description="Start the MicroScore API and web UI for local demo work.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Local host to bind.")
    parser.add_argument("--api-port", type=int, help="Preferred API port.")
    parser.add_argument("--web-port", type=int, help="Preferred web UI port.")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start servers without opening a browser window.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    host = args.host
    if not WEB_ROOT.exists():
        print(f"Web root not found: {WEB_ROOT}")
        return 1

    print("MicroScore local launcher")
    print("Seeding demo accounts and Pavlodar application portfolio...")
    seed_demo_data()

    api_port = args.api_port if args.api_port else _pick_port(host, API_PORT_CANDIDATES)
    web_port = args.web_port if args.web_port else _pick_port(host, WEB_PORT_CANDIDATES)
    api_base = f"http://{host}:{api_port}"
    web_url = (
        f"http://{host}:{web_port}/"
        f"?api={urllib.parse.quote(api_base, safe=':/')}"
    )

    api_process = _start_process(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "microscore_api.main:app",
            "--host",
            host,
            "--port",
            str(api_port),
        ]
    )
    web_process = _start_process(
        [
            sys.executable,
            "-m",
            "http.server",
            str(web_port),
            "--bind",
            host,
            "--directory",
            str(WEB_ROOT),
        ]
    )

    print(f"API: {api_base}")
    print(f"Web: http://{host}:{web_port}")
    print("Demo password: password123")
    print("Close this window or press Ctrl+C to stop MicroScore.")

    if _wait_for_health(api_base) and not args.no_browser:
        webbrowser.open(web_url)
    else:
        if args.no_browser:
            print(f"Open manually: {web_url}")
        else:
            print("API did not become ready in time. Check the messages above.")

    try:
        while True:
            if api_process.poll() is not None:
                print("API process stopped.")
                return int(api_process.returncode or 1)
            if web_process.poll() is not None:
                print("Web process stopped.")
                return int(web_process.returncode or 1)
            time.sleep(0.75)
    except KeyboardInterrupt:
        print("\nStopping MicroScore...")
        return 0
    finally:
        for process in (api_process, web_process):
            if process.poll() is None:
                process.terminate()
        for process in (api_process, web_process):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
