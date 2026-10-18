"""Pebble lexer: source text to tokens carrying 1-based line and column positions.

Whitespace is insignificant (statements need no separators), comments run from `#` to the end of
the line, and every failure is a LexError with a position, a reason and a fix.
"""

import math
from dataclasses import dataclass

from .errors import LexError
from .limits import MAX_INT_DIGITS

KEYWORDS = frozenset({"let", "if", "else", "while", "for", "in", "fn", "return",
                      "true", "false", "none", "and", "or", "not"})
TWO_CHAR_OPERATORS = frozenset({"==", "!=", "<=", ">="})
ONE_CHAR_OPERATORS = frozenset("+-*/%^<>=(){}[],")
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'"}
CHARACTER_HINTS = {
    ";": "Pebble statements need no separator; remove the ';'",
    ":": "v1 has no type annotations or dict literals; remove the ':'",
    "&": "write 'and' for logical and",
    "|": "write 'or' for logical or",
    "!": "write 'not' for logical not, or '!=' for not-equal",
    "~": "v1 has no bitwise operators; remove the '~'",
    "@": "v1 has no decorators; remove the '@'",
    "?": "write an if/else statement instead of '?'",
    "\\": "a backslash is only used inside strings",
}


@dataclass(frozen=True)
class Token:
    """One lexical unit; `value` is the payload for numbers and strings, else the token text."""

    kind: str
    value: object
    line: int
    col: int


class _Scanner:
    """One pass over the source, appending tokens with exact positions."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.index = 0
        self.line = 1
        self.col = 1
        self.tokens: list[Token] = []

    def scan(self) -> list[Token]:
        """Every token in the source, ending with one EOF token."""
        while self.index < len(self.source):
            ch = self.source[self.index]
            if ch == "\n":
                self._newline()
            elif ch in " \t\r":
                self._skip(1)
            elif ch == "#":
                self._comment()
            elif "0" <= ch <= "9":
                self._number()
            elif ch in "\"'":
                self._string()
            elif _is_name_start(ch):
                self._name()
            else:
                self._operator()
        self.tokens.append(Token("EOF", None, self.line, self.col))
        return self.tokens

    def _skip(self, count: int) -> None:
        """Advance the cursor `count` characters on the same line."""
        self.index += count
        self.col += count

    def _newline(self) -> None:
        """Advance past a line break, resetting the column."""
        self.index += 1
        self.line += 1
        self.col = 1

    def _comment(self) -> None:
        """Skip from `#` to the end of the line."""
        while self.index < len(self.source) and self.source[self.index] != "\n":
            self.index += 1

    def _number(self) -> None:
        """Lex an int or a float; a directly following letter is reported as a typo."""
        line, col, start = self.line, self.col, self.index
        while self.index < len(self.source) and "0" <= self.source[self.index] <= "9":
            self._skip(1)
        is_float = (self.index + 1 < len(self.source) and self.source[self.index] == "."
                    and "0" <= self.source[self.index + 1] <= "9")
        if is_float:
            self._skip(1)
            while self.index < len(self.source) and "0" <= self.source[self.index] <= "9":
                self._skip(1)
        text = self.source[start:self.index]
        if is_float:
            value = float(text)
            if not math.isfinite(value):
                raise LexError("float literal is too large", line, col,
                               "the literal is beyond the largest float",
                               "use a smaller number")
            self.tokens.append(Token("NUMBER", value, line, col))
        else:
            significant = text.lstrip("0") or "0"
            if len(significant) > MAX_INT_DIGITS:
                raise LexError("integer literal is too large", line, col,
                               f"v1 caps an integer literal at {MAX_INT_DIGITS} digits",
                               "use a shorter number, or build it with arithmetic")
            self.tokens.append(Token("NUMBER", int(text), line, col))
        if self.index < len(self.source) and _is_name_start(self.source[self.index]):
            letter = self.source[self.index]
            raise LexError(f"a number cannot be followed directly by a letter '{letter}'",
                           self.line, self.col,
                           "the source reads as one word, but a number and a name are two tokens",
                           "separate the number and the name with a space")

    def _string(self) -> None:
        """Lex a single- or double-quoted string; strings never cross a line."""
        quote = self.source[self.index]
        line, col = self.line, self.col
        self._skip(1)
        parts: list[str] = []
        while True:
            if self.index >= len(self.source) or self.source[self.index] == "\n":
                raise LexError("unterminated string", line, col,
                               "the string opens here, but no matching " + quote
                               + " appears before the end of the line",
                               "close the string on the same line it opens with " + quote)
            ch = self.source[self.index]
            if ch == "\\":
                parts.append(self._escape())
                continue
            if ch == quote:
                self._skip(1)
                break
            parts.append(ch)
            self._skip(1)
        self.tokens.append(Token("STRING", "".join(parts), line, col))

    def _escape(self) -> str:
        """The character the escape at the cursor produces, with the cursor moving past it."""
        line, col = self.line, self.col
        if self.index + 1 >= len(self.source) or self.source[self.index + 1] == "\n":
            raise LexError("unterminated string", line, col,
                           "the string ends with a lone backslash before the line ends",
                           "finish the escape, or drop the trailing backslash")
        nxt = self.source[self.index + 1]
        if nxt not in ESCAPES:
            raise LexError(f"unknown escape '\\{nxt}'", line, col,
                           "this escape is not one of the six Pebble understands",
                           "use \\n, \\t, \\r, \\\\, \\\" or \\' (or drop the backslash)")
        self._skip(2)
        return ESCAPES[nxt]

    def _name(self) -> None:
        """Lex an identifier and mark whether it is a reserved word."""
        line, col, start = self.line, self.col, self.index
        while self.index < len(self.source) and _is_name_part(self.source[self.index]):
            self._skip(1)
        text = self.source[start:self.index]
        self.tokens.append(Token("KEYWORD" if text in KEYWORDS else "NAME", text, line, col))

    def _operator(self) -> None:
        """Lex an operator, or explain the character that is not one."""
        line, col = self.line, self.col
        two = self.source[self.index:self.index + 2]
        if two in TWO_CHAR_OPERATORS:
            self.tokens.append(Token("OP", two, line, col))
            self._skip(2)
            return
        ch = self.source[self.index]
        if ch == "." and self.tokens and self.tokens[-1].kind == "NUMBER":
            raise LexError("'.' must be followed by a digit", line, col,
                           "a float such as 1.5 needs digits on both sides of the dot",
                           "write 1.0 for a whole number, or fix the decimal part")
        if ch in ONE_CHAR_OPERATORS:
            self.tokens.append(Token("OP", ch, line, col))
            self._skip(1)
            return
        raise LexError(f"unexpected character '{ch}'", line, col,
                       "Pebble does not use this character here",
                       CHARACTER_HINTS.get(ch, "valid input is ASCII letters, digits, operators, "
                                               "quotes, commas and # comments"))


def _is_name_start(ch: str) -> bool:
    """ASCII letter or underscore (v1 identifiers are ASCII on purpose)."""
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ch == "_"


def _is_name_part(ch: str) -> bool:
    """ASCII letter, digit or underscore."""
    return _is_name_start(ch) or ("0" <= ch <= "9")


def tokenize(source: str) -> list[Token]:
    """Every token in `source`, ending with one EOF token."""
    return _Scanner(source).scan()
