"""Pebble's nine v1 builtins and their shared argument rules.

Each builtin is a `Builtin` record: a name, an implementation and the arity it advertises. The
evaluator checks the arity before evaluating arguments and passes the call node, so every builtin
failure is a positioned EvalError with a Why and a Fix.
"""

import math
from typing import NoReturn

from .errors import EvalError
from .formatting import format_value, is_number, type_name


class Builtin:
    """A callable provided by the language itself; stateless and safe to share."""

    is_builtin = True

    def __init__(self, name: str, impl, expects: str, min_args: int,
                 max_args=None) -> None:
        self.pebble_name = name
        self.impl = impl
        self.expects = expects
        self.min_args = min_args
        self.max_args = max_args


def _fail(node, message: str, why: str, fix: str) -> NoReturn:
    """Raise the positioned EvalError shared by every builtin failure."""
    raise EvalError(message, node.line, node.col, why, fix)


def _print(interpreter, call, args) -> None:
    """Write one value in display form, then a newline; returns none."""
    interpreter.out.write(format_value(args[0]) + "\n")
    return None


def _len(interpreter, call, args) -> int:
    """The number of characters in a string or elements in a list."""
    value = args[0]
    if isinstance(value, (str, list)):
        return len(value)
    _fail(call, f"cannot take the length of {type_name(value)}",
          "len works on a string or a list",
          'pass a string or a list, for example len("abc") or len([1, 2])')


def _range(interpreter, call, args) -> list:
    """A half-open list of ints: range(stop) or range(start, stop)."""
    for value in args:
        if isinstance(value, bool) or not isinstance(value, int):
            _fail(call, f"range needs int arguments, got {type_name(value)}",
                  "range counts whole numbers",
                  "pass int values, for example range(5) or range(1, 5)")
    if len(args) == 1:
        return list(range(args[0]))
    return list(range(args[0], args[1]))


def _str(interpreter, call, args) -> str:
    """The display form of any value, as a string."""
    return format_value(args[0])


def _int(interpreter, call, args) -> int:
    """An int from an int, a float truncated toward zero, or a signed decimal string."""
    value = args[0]
    if isinstance(value, bool):
        _fail(call, "cannot convert bool to int",
              "Pebble keeps booleans out of arithmetic",
              'convert a number or a numeric string, for example int(3.9) or int("42")')
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail(call, "cannot convert a non-finite float to int",
                  "infinity and nan have no whole-number value",
                  "check the float, or convert a finite number")
        return int(value)
    if isinstance(value, str):
        return _parse_int(call, value)
    _fail(call, f"cannot convert {type_name(value)} to int",
          "int accepts a number or a numeric string",
          'convert a number or a numeric string, for example int(3.9) or int("42")')


def _parse_int(call, text: str) -> int:
    """A strict decimal integer: optional sign, ASCII digits, nothing else."""
    digits = text[1:] if text[:1] in ("+", "-") else text
    if not digits or any(ch < "0" or ch > "9" for ch in digits):
        _fail(call, f"cannot convert string {text!r} to int",
              "int(...) on a string accepts an optional sign and digits only",
              'pass a whole number such as "42", or convert a float value with int(3.9)')
    return int(text)


def _floor(interpreter, call, args) -> int:
    """The greatest int not greater than a number."""
    value = args[0]
    if isinstance(value, bool):
        _fail(call, "cannot take the floor of bool",
              "floor needs a number",
              "pass an int or a float, for example floor(3.9)")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail(call, "cannot take the floor of a non-finite float",
                  "infinity and nan have no whole-number value",
                  "check the float, or take the floor of a finite number")
        return math.floor(value)
    _fail(call, f"cannot take the floor of {type_name(value)}",
          "floor needs a number",
          "pass an int or a float, for example floor(3.9)")


def _extreme(call, args, want_max: bool, name: str):
    """The smallest or largest value, from the arguments or from one list argument."""
    values = args[0] if len(args) == 1 and isinstance(args[0], list) else args
    if not values:
        _fail(call, f"{name} needs at least one value",
              "the list is empty, so the result would be undefined",
              "pass a non-empty list, or pass values directly")
    first = values[0]
    if not _orderable(first):
        _fail(call, f"cannot compare {type_name(first)} with {name}",
              "min and max order numbers or strings",
              "pass numbers, strings, or one list of them")
    for value in values[1:]:
        if not _orderable(value) or not _same_kind(first, value):
            _fail(call, f"cannot compare {type_name(first)} and {type_name(value)}",
                  "min and max compare numbers with numbers, or strings with strings",
                  "make every value the same kind")
    best = first
    for value in values[1:]:
        if value > best if want_max else value < best:
            best = value
    return best


def _orderable(value) -> bool:
    """Whether min and max may order this value in isolation."""
    return is_number(value) or isinstance(value, str)


def _same_kind(left, right) -> bool:
    """Whether two orderable values are comparable: both numbers or both strings."""
    return (is_number(left) and is_number(right)) or \
        (isinstance(left, str) and isinstance(right, str))


def _min(interpreter, call, args):
    """The smallest of the values."""
    return _extreme(call, args, False, "min")


def _max(interpreter, call, args):
    """The largest of the values."""
    return _extreme(call, args, True, "max")


def _abs(interpreter, call, args):
    """The magnitude of a number."""
    value = args[0]
    if is_number(value):
        return abs(value)
    _fail(call, f"cannot take the absolute value of {type_name(value)}",
          "abs needs a number",
          "pass an int or a float, for example abs(-3)")


BUILTINS = {
    "print": Builtin("print", _print, "1 argument", 1, 1),
    "len": Builtin("len", _len, "1 argument", 1, 1),
    "range": Builtin("range", _range, "1 or 2 arguments", 1, 2),
    "str": Builtin("str", _str, "1 argument", 1, 1),
    "int": Builtin("int", _int, "1 argument", 1, 1),
    "floor": Builtin("floor", _floor, "1 argument", 1, 1),
    "min": Builtin("min", _min, "at least 1 argument", 1),
    "max": Builtin("max", _max, "at least 1 argument", 1),
    "abs": Builtin("abs", _abs, "1 argument", 1, 1),
}
