"""Command line. This step supports ingest only."""

from __future__ import annotations

import sys

from screener.pipeline.ingest import ingest


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["ingest"]:
        print("usage: python -m screener ingest", file=sys.stderr)
        return 2
    result = ingest(log=print)
    return 0 if result.active else 1


if __name__ == "__main__":
    raise SystemExit(main())
