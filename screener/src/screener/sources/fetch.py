"""Download one sanctions file to a new snapshot path."""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from pathlib import Path

from screener.sources.errors import FetchError

USER_AGENT = "supplier-sanctions-agent/0.1 (non-commercial screening poc)"
CHUNK = 64 * 1024
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def download(
    url: str,
    dest: Path,
    *,
    max_bytes: int,
    timeout: float = 180,
    attempts: int = 3,
) -> tuple[int, str]:
    """Stream url to dest. Returns the HTTP status and the SHA-256 of the saved bytes."""

    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".part")
    last_error: FetchError | None = None
    for attempt in range(attempts):
        try:
            status, digest = _download_once(url, partial, max_bytes=max_bytes, timeout=timeout)
        except FetchError as exc:
            partial.unlink(missing_ok=True)
            last_error = exc
            if not exc.retryable or attempt == attempts - 1:
                raise
            time.sleep(2**attempt)
            continue
        partial.replace(dest)
        return status, digest
    assert last_error is not None
    raise last_error


def _download_once(url: str, dest: Path, *, max_bytes: int, timeout: float) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    hasher = hashlib.sha256()
    size = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200) or 200
            with dest.open("wb") as handle:
                while True:
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise FetchError(
                            f"download exceeded {max_bytes} bytes",
                            retryable=False,
                            http_status=status,
                        )
                    hasher.update(chunk)
                    handle.write(chunk)
    except FetchError:
        raise
    except urllib.error.HTTPError as exc:
        raise FetchError(
            f"HTTP {exc.code} for {url}",
            retryable=exc.code in RETRYABLE_STATUS,
            http_status=exc.code,
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FetchError(str(exc), retryable=True) from exc
    if size == 0:
        raise FetchError("download was empty", retryable=True, http_status=status)
    return status, hasher.hexdigest()
