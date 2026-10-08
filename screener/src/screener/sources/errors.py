"""Failures while reading a sanctions file."""


class ParseError(Exception):
    """The file is not the list format this adapter understands."""
