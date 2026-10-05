"""Name normalization, the search index, and score bands."""

from screener.matching.index import SnapshotNotReady, active_snapshot_id, build_index
from screener.matching.retrieve import MatchResult, match_supplier

__all__ = [
    "MatchResult",
    "SnapshotNotReady",
    "active_snapshot_id",
    "build_index",
    "match_supplier",
]
