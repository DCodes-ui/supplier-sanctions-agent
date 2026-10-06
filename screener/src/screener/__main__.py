"""Command line for ingest, indexing, and one screening."""

from __future__ import annotations

import argparse
import sys

from screener.matching.index import SnapshotNotReady, active_snapshot_id, build_index
from screener.pipeline.ingest import ingest
from screener.pipeline.screen import adjudication_label, screen_supplier


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        _usage()
        return 2
    command, rest = args[0], args[1:]
    if command == "ingest":
        if rest:
            _usage()
            return 2
        result = ingest(log=print)
        return 0 if result.active else 1
    if command == "index":
        if rest:
            _usage()
            return 2
        try:
            build_index(active_snapshot_id(), log=print)
        except SnapshotNotReady as exc:
            print(exc, file=sys.stderr)
            return 1
        return 0
    if command == "screen":
        return _screen(rest)
    _usage()
    return 2


def _screen(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m screener screen")
    parser.add_argument("--name", required=True)
    parser.add_argument("--country", required=True)
    parser.add_argument("--registration-number", default=None)
    args = parser.parse_args(argv)
    try:
        result = screen_supplier(args.name, args.country, args.registration_number)
    except SnapshotNotReady as exc:
        print(exc, file=sys.stderr)
        return 1
    decision = result.decision
    print(f"adjudication: {adjudication_label(result)}")
    print(f"status: {decision.status}")
    print(f"confidence: {decision.match_confidence:.2f}")
    print(f"basis: {decision.decision_basis}")
    if decision.matched_entity is not None:
        print(f"matched: {decision.matched_entity.name}")
        print(f"list: {decision.matched_entity.list}")
        print(f"programme: {decision.matched_entity.programme}")
    print(f"action: {decision.recommended_action}")
    print(f"rationale: {decision.rationale}")
    return 0


def _usage() -> None:
    print(
        "usage:\n"
        "  python -m screener ingest\n"
        "  python -m screener index\n"
        "  python -m screener screen --name NAME --country CC [--registration-number ID]",
        file=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
