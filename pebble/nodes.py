"""Pebble's abstract syntax tree: frozen nodes, each carrying the position it started at."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union


@dataclass(frozen=True)
class Literal:
    """A constant: int, float, bool, string, or none (stored as None)."""

    value: object
    line: int
    col: int


@dataclass(frozen=True)
class ListLiteral:
    """A [a, b, c] list constructor."""

    elements: tuple[Expr, ...]
    line: int
    col: int


@dataclass(frozen=True)
class Name:
    """A reference to a variable, function or builtin."""

    identifier: str
    line: int
    col: int


@dataclass(frozen=True)
class Unary:
    """A prefix operator: `-x` or `not x`."""

    op: str
    operand: Expr
    line: int
    col: int


@dataclass(frozen=True)
class Binary:
    """An infix operator: arithmetic, `^`, or a single comparison."""

    op: str
    left: Expr
    right: Expr
    line: int
    col: int


@dataclass(frozen=True)
class Logical:
    """`and` / `or`, kept apart from Binary so the evaluator can short-circuit."""

    op: str
    left: Expr
    right: Expr
    line: int
    col: int


@dataclass(frozen=True)
class Call:
    """Calling a function or builtin; the position is the opening parenthesis."""

    callee: Expr
    args: tuple[Expr, ...]
    line: int
    col: int


@dataclass(frozen=True)
class Index:
    """Indexing a list or string; the position is the opening bracket."""

    target: Expr
    index: Expr
    line: int
    col: int


@dataclass(frozen=True)
class Slice:
    """A `target[start:stop:step]` subsequence; None marks an omitted part."""

    target: Expr
    start: Optional[Expr]
    stop: Optional[Expr]
    step: Optional[Expr]
    line: int
    col: int


@dataclass(frozen=True)
class Let:
    """`let name = value`, declaring or rebinding in the current scope."""

    name: str
    value: Expr
    line: int
    col: int


@dataclass(frozen=True)
class Assign:
    """`name = value`, rebinding a name that already exists."""

    name: str
    value: Expr
    line: int
    col: int


@dataclass(frozen=True)
class ExprStmt:
    """An expression used as a statement; its value is the REPL's echo."""

    expr: Expr
    line: int
    col: int


@dataclass(frozen=True)
class IfStmt:
    """`if` with optional `else` (an `else if` chain is a one-statement else body)."""

    condition: Expr
    then_body: tuple[Statement, ...]
    else_body: tuple[Statement, ...]
    line: int
    col: int


@dataclass(frozen=True)
class WhileStmt:
    """A `while` loop; the body repeats as long as the condition is truthy."""

    condition: Expr
    body: tuple[Statement, ...]
    line: int
    col: int


@dataclass(frozen=True)
class ForStmt:
    """`for name in iterable { ... }`, iterating a list or a string."""

    name: str
    iterable: Expr
    body: tuple[Statement, ...]
    line: int
    col: int


@dataclass(frozen=True)
class FnStmt:
    """A named function definition; v1 has recursion but no closures."""

    name: str
    params: tuple[str, ...]
    body: tuple[Statement, ...]
    line: int
    col: int


@dataclass(frozen=True)
class ReturnStmt:
    """`return` with an optional value; None here means a bare return."""

    value: Optional[Expr]
    line: int
    col: int


@dataclass(frozen=True)
class BreakStmt:
    """`break`, leaving the innermost while or for loop."""

    line: int
    col: int


@dataclass(frozen=True)
class ContinueStmt:
    """`continue`, starting the innermost while or for loop's next iteration."""

    line: int
    col: int


Expr = Union[Literal, ListLiteral, Name, Unary, Binary, Logical, Call, Index, Slice]
Statement = Union[Let, Assign, ExprStmt, IfStmt, WhileStmt, ForStmt, FnStmt, ReturnStmt,
                  BreakStmt, ContinueStmt]
