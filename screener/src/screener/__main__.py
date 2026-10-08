"""Command line for indexing, screening, and the API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from screener.evalset import evaluate, write_cases
from screener.matching.index import SnapshotNotReady, active_snapshot_id, build_index
from screener.pipeline.screen import (
    StoredScreen,
    parse_batch_csv,
    run_batch,
    run_screen,
    screenings_csv,
)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        _usage()
        return 2
    command, rest = args[0], args[1:]
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
    if command == "batch":
        return _batch(rest)
    if command == "eval":
        return _eval(rest)
    if command == "api":
        if rest:
            _usage()
            return 2
        import uvicorn

        uvicorn.run("screener.api:app", host="127.0.0.1", port=8000)
        return 0
    _usage()
    return 2


def _screen(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m screener screen")
    parser.add_argument("--name", required=True)
    parser.add_argument("--country", required=True)
    parser.add_argument("--registration-number", default=None)
    args = parser.parse_args(argv)
    try:
        stored = run_screen(args.name, args.country, args.registration_number)
    except SnapshotNotReady as exc:
        print(exc, file=sys.stderr)
        return 1
    _print_screen(stored)
    return 0


def _eval(argv: list[str]) -> int:
    try:
        if argv == ["--write"]:
            count = write_cases()
            print(f"wrote {count} cases")
        elif argv:
            _usage()
            return 2
        return evaluate()
    except (OSError, RuntimeError, FileNotFoundError) as exc:
        print(exc, file=sys.stderr)
        return 1


def _batch(argv: list[str]) -> int:
    if len(argv) != 1:
        _usage()
        return 2
    try:
        rows = parse_batch_csv(Path(argv[0]).read_text(encoding="utf-8-sig"))
        stored = run_batch(rows)
    except (OSError, ValueError, SnapshotNotReady) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(screenings_csv(stored), end="")
    return 0


def _print_screen(stored: StoredScreen) -> None:
    decision = stored.record.decision
    print(f"id: {stored.record.id}")
    print(f"adjudication: {_adjudication(stored)}")
    print(f"status: {decision.status}")
    print(f"confidence: {decision.match_confidence:.2f}")
    print(f"basis: {decision.decision_basis}")
    if decision.matched_entity is not None:
        print(f"matched: {decision.matched_entity.name}")
        print(f"list: {decision.matched_entity.list}")
        print(f"programme: {decision.matched_entity.programme}")
    print(f"action: {decision.recommended_action}")
    print(f"rationale: {decision.rationale}")


def _adjudication(stored: StoredScreen) -> str:
    if stored.adjudication == "llm":
        return "llm"
    if stored.adjudication == "fallback":
        return "rules (model output rejected)"
    if stored.record.decision.decision_basis in {"below_threshold", "fallback_rules"}:
        return "rules (no XAI_API_KEY)"
    return "rules"


def _usage() -> None:
    print(
        "usage:\n"
        "  python -m screener index\n"
        "  python -m screener screen --name NAME --country CC [--registration-number ID]\n"
        "  python -m screener batch suppliers.csv\n"
        "  python -m screener eval\n"
        "  python -m screener api",
        file=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
