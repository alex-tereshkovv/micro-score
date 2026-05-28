"""Backward-compatible command-line entrypoint for the MicroScore experiment."""

from __future__ import annotations

from microscore.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
