"""Failures while downloading or reading a sanctions file."""


class FetchError(Exception):
    """The raw file could not be downloaded."""

    def __init__(self, message: str, *, retryable: bool, http_status: int = 0) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.http_status = http_status


class ParseError(Exception):
    """The file is not the list format this adapter understands."""
