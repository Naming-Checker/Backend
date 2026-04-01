from __future__ import annotations

import argparse

import uvicorn

from naming_check_backend.shared.settings import settings


def run_server() -> None:
    uvicorn.run(
        "naming_check_backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "local",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backend development commands")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run-server", help="Start the HTTP API")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run-server":
        run_server()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
