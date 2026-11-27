"""One-command launcher for Cor ad Cor with automatic free-port selection."""

from __future__ import annotations

import argparse
import os
import socket

import uvicorn


def is_port_free(host: str, port: int) -> bool:
    """Return True if (host, port) can be bound without conflict."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def find_free_port(host: str = "127.0.0.1", preferred: int = 8010, max_tries: int = 20) -> int:
    """Return `preferred` if free, otherwise scan upward for the next available port."""
    for candidate in range(preferred, preferred + max_tries):
        if is_port_free(host, candidate):
            return candidate
    raise RuntimeError(f"No free TCP port found in range {preferred}..{preferred + max_tries - 1}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Cor ad Cor web server on an available port.")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8010")))
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    chosen_port = find_free_port(args.host, args.port)
    if chosen_port != args.port:
        print(f"Port {args.port} is busy — automatically selected port {chosen_port}.")
    print(f"Starting Cor ad Cor at: http://{args.host}:{chosen_port}")
    uvicorn.run("app.main:app", host=args.host, port=chosen_port, reload=args.reload)


if __name__ == "__main__":
    main()
