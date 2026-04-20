"""CLI entry point for Tipoff."""

from __future__ import annotations

import argparse


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="tipoff",
        description="Terminal TUI for tracking NBA playoffs",
    )
    parser.add_argument(
        "--refresh-interval",
        type=int,
        default=30,
        help="Auto-refresh interval in seconds (default: 30, min: 5)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    refresh_interval = max(5, args.refresh_interval)

    from tipoff.app import TipoffApp

    app = TipoffApp(refresh_interval=refresh_interval)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())