"""Pebble error types and their one report format.

Every failure a user can trigger carries a position and two answers: why it happened and how to
fix it. The CLI renders all of them with `format_error`; Python tracebacks never reach a user.
"""


class PebbleError(Exception):
    """A user-facing failure: a position in the source, a reason and a concrete fix."""

    kind = "error"

    def __init__(self, message: str, line: int, col: int, why: str, fix: str) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        self.why = why
        self.fix = fix


class LexError(PebbleError):
    """The source text is malformed: an unknown character, a broken string or number."""


class ParseError(PebbleError):
    """Well-formed tokens that do not form a valid program."""

    def __init__(self, message: str, line: int, col: int, why: str, fix: str,
                 at_eof: bool = False) -> None:
        super().__init__(message, line, col, why, fix)
        self.at_eof = at_eof


class EvalError(PebbleError):
    """A valid program asked for something impossible: an unknown name, a bad type, zero division."""


def format_error(error: PebbleError, filename: str) -> str:
    """The three-line report every Pebble failure renders as."""
    return (f"{filename}:{error.line}:{error.col}: {error.kind}: {error.message}\n"
            f"  Why: {error.why}\n"
            f"  Fix: {error.fix}")
