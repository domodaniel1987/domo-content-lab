from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_STREAMLIT = ROOT / ".venv" / "bin" / "streamlit"


def find_port(start: int = 8501, end: int = 8520) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No encontre un puerto libre entre 8501 y 8520.")


def get_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "TU-IP-LOCAL"


def main() -> None:
    if not VENV_STREAMLIT.exists():
        print("Primero instala el entorno local:")
        print("python3 -m venv .venv")
        print(".venv/bin/pip install -r requirements.txt")
        sys.exit(1)

    port = find_port()
    env = os.environ.copy()
    env["DOMO_STREAMLIT_PORT"] = str(port)

    command = [
        str(VENV_STREAMLIT),
        "run",
        "app.py",
        "--server.headless",
        "true",
        "--server.port",
        str(port),
        "--browser.gatherUsageStats",
        "false",
    ]

    print_launch_message(port, address="0.0.0.0", mobile=True)
    result = subprocess.run(
        [
            *command,
            "--server.address",
            "0.0.0.0",
        ],
        cwd=ROOT,
        env=env,
        check=False,
    )
    if result.returncode == 0:
        return

    print("")
    print("No se pudo abrir en modo celular desde este entorno.")
    print("Voy a probar en modo solo computadora.")
    print("")
    print_launch_message(port, address="127.0.0.1", mobile=False)
    subprocess.run(
        [
            *command,
            "--server.address",
            "127.0.0.1",
        ],
        cwd=ROOT,
        env=env,
        check=False,
    )


def print_launch_message(port: int, address: str, mobile: bool) -> None:
    print("")
    print("DOMO Content Lab")
    print(f"Computadora: http://localhost:{port}")
    if mobile:
        print(f"Celular en el mismo Wi-Fi: http://{get_lan_ip()}:{port}")
    else:
        print("Modo celular no disponible en este arranque.")
    print(f"Direccion interna: {address}")
    print("")
    print("Para cerrarlo, vuelve a esta ventana y presiona Ctrl+C.")
    print("")


if __name__ == "__main__":
    main()
