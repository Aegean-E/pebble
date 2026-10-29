"""Pebble's builtins and their shared argument rules.

Each builtin is a `Builtin` record: a name, an implementation and the arity it advertises. The
evaluator checks the arity before evaluating arguments and passes the call node, so every builtin
failure is a positioned EvalError with a Why and a Fix. v2 added `float()` and the `range` step;
v5 adds the text helpers `split`, `join`, `trim` and `replace`.
"""

import math
import re
from typing import NoReturn

from .errors import EvalError
from .formatting import format_value, is_number, type_name
from .limits import MAX_INT_DIGITS, MAX_RANGE_LENGTH, MAX_SEQUENCE_LENGTH


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


def _range_length(start: int, stop: int, step: int) -> int:
    """How many values range(start, stop, step) yields, computed without len()."""
    if step > 0:
        if start >= stop:
            return 0
        return (stop - start + step - 1) // step
    if start <= stop:
        return 0
    return (start - stop - step - 1) // (-step)


def _range(interpreter, call, args) -> list:
    """A half-open list of ints: range(stop), range(start, stop) or range(start, stop, step)."""
    for value in args:
        if isinstance(value, bool) or not isinstance(value, int):
            _fail(call, f"range needs int arguments, got {type_name(value)}",
                  "range counts whole numbers",
                  "pass int values, for example range(5) or range(1, 5)")
    if len(args) == 1:
        start, stop, step = 0, args[0], 1
    elif len(args) == 2:
        start, stop, step = args[0], args[1], 1
    else:
        start, stop, step = args
    if step == 0:
        _fail(call, "range step cannot be zero",
              "a step of zero would never advance through the range",
              "use a step of 1, or a negative step to count down")
    length = _range_length(start, stop, step)
    if length > MAX_RANGE_LENGTH:
        _fail(call, f"range would produce {length} values",
              f"v1 holds a range in memory and caps it at {MAX_RANGE_LENGTH} values",
              "use a smaller range, or count with a while loop")
    return list(range(start, stop, step))


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
    significant = digits.lstrip("0") or "0"
    if len(significant) > MAX_INT_DIGITS:
        _fail(call, f"cannot convert a {len(significant)}-digit string to int",
              f"v1 caps an int at about {MAX_INT_DIGITS} digits",
              "use a shorter number, or build it with arithmetic")
    return int(text)


_DECIMAL = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")


def _float(interpreter, call, args) -> float:
    """A float from an int, a float or a decimal string; booleans are refused."""
    value = args[0]
    if isinstance(value, bool):
        _fail(call, "cannot convert bool to float",
              "Pebble keeps booleans out of arithmetic",
              'convert a number or a numeric string, for example float(3) or float("2.5")')
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail(call, "cannot convert a non-finite float",
                  "infinity and nan are not finite values",
                  "check the value, or convert a finite number")
        return value
    if isinstance(value, int):
        try:
            return float(value)
        except OverflowError:
            _fail(call, "cannot convert int to float",
                  "the int is beyond the largest float",
                  "use a smaller number, or scale it down first")
    if isinstance(value, str):
        return _parse_float(call, value)
    _fail(call, f"cannot convert {type_name(value)} to float",
          "float accepts a number or a numeric string",
          'convert a number or a numeric string, for example float(3) or float("2.5")')


def _parse_float(call, text: str) -> float:
    """A strict decimal number with an optional fraction and exponent."""
    if _DECIMAL.fullmatch(text) is None:
        _fail(call, f"cannot convert string {text!r} to float",
              "float(...) on a string accepts a decimal number such as "
              '"2.5" or "-1e3"',
              'pass a decimal number such as "2.5"')
    value = float(text)
    if not math.isfinite(value):
        _fail(call, "cannot convert a non-finite float",
              "the text denotes a value beyond the largest float",
              "use a smaller number")
    return value


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


def _sort(interpreter, call, args) -> list:
    """A new list of the values in ascending order, by the min/max ordering rules."""
    values = args[0]
    if not isinstance(values, list):
        _fail(call, f"sort needs a list, got {type_name(values)}",
              "sort reads a list of values and orders them",
              'pass a list of numbers or strings, for example sort([3, 1, 2])')
    if not values:
        return []
    first = values[0]
    if not _orderable(first):
        _fail(call, f"cannot compare {type_name(first)} with sort",
              "sort orders numbers or strings",
              "pass a list of numbers or a list of strings")
    for value in values[1:]:
        if not _orderable(value) or not _same_kind(first, value):
            _fail(call, f"cannot compare {type_name(first)} and {type_name(value)}",
                  "sort compares numbers with numbers, or strings with strings",
                  "make every value the same kind")
    return sorted(values)


def _abs(interpreter, call, args):
    """The magnitude of a number."""
    value = args[0]
    if is_number(value):
        return abs(value)
    _fail(call, f"cannot take the absolute value of {type_name(value)}",
          "abs needs a number",
          "pass an int or a float, for example abs(-3)")


_WHITESPACE = " \t\n\r\f\v"


def _string_arg(call, value, name: str, why: str, fix: str) -> str:
    """One argument as a string, or the builtin's positioned type error."""
    if isinstance(value, str):
        return value
    _fail(call, f"{name} needs a string, got {type_name(value)}", why, fix)


def _split(interpreter, call, args) -> list:
    """Text cut into fields: on whitespace runs, or at every exact separator."""
    text = _string_arg(call, args[0], "split",
                       "split reads a text string and an optional separator",
                       'pass a string, for example split("a,b", ",")')
    if len(args) == 1:
        return _split_whitespace(text)
    separator = _string_arg(call, args[1], "split",
                            "the text and the separator must both be strings",
                            'pass a separator string, or omit it to split on whitespace')
    if separator == "":
        _fail(call, "split separator cannot be empty",
              "an empty separator would never advance from one field to the next",
              'pass a separator such as a comma, or omit it to split on whitespace')
    pieces = text.count(separator) + 1
    if pieces > MAX_SEQUENCE_LENGTH:
        _fail(call, f"split would produce {pieces} pieces",
              f"a list holds at most {MAX_SEQUENCE_LENGTH} values",
              "split a shorter piece of text, or use the one-argument whitespace split")
    return text.split(separator)


def _split_whitespace(text: str) -> list:
    """The fields between runs of whitespace; leading and trailing whitespace is dropped."""
    pieces = []
    start = None
    for index, character in enumerate(text):
        if character in _WHITESPACE:
            if start is not None:
                pieces.append(text[start:index])
                start = None
        elif start is None:
            start = index
    if start is not None:
        pieces.append(text[start:])
    return pieces


def _join(interpreter, call, args) -> str:
    """The strings of a list in order, with a separator between them."""
    values = args[0]
    if not isinstance(values, list):
        _fail(call, f"join needs a list, got {type_name(values)}",
              "join reads a list of values and a separator string",
              'pass a list of strings, for example join(["a", "b"], ",")')
    separator = _string_arg(call, args[1], "join",
                            "the values and the separator must both be strings",
                            'pass a separator string, for example join(["a"], ",")')
    length = len(separator) * (len(values) - 1) if values else 0
    for index, value in enumerate(values):
        if not isinstance(value, str):
            _fail(call, f"join needs a list of strings, found {type_name(value)} "
                        f"at index {index}",
                  "the values and the separator must both be strings",
                  "convert each element with str(...), or keep the list to strings only")
        length += len(value)
    if length > MAX_SEQUENCE_LENGTH:
        _fail(call, "joining these strings is too large",
              f"the result would have {length} characters; v1 caps sequences at "
              f"{MAX_SEQUENCE_LENGTH}",
              "join fewer or shorter strings")
    return separator.join(values)


def _trim(interpreter, call, args) -> str:
    """The text without leading or trailing whitespace; the interior is untouched."""
    text = _string_arg(call, args[0], "trim",
                       "trim removes whitespace from both ends of a string",
                       'pass a string, for example trim("  hi  ")')
    start, end = 0, len(text)
    while start < end and text[start] in _WHITESPACE:
        start += 1
    while end > start and text[end - 1] in _WHITESPACE:
        end -= 1
    return text[start:end]


def _replace(interpreter, call, args) -> str:
    """Every non-overlapping occurrence of a search string, left to right, rewritten."""
    text = _string_arg(call, args[0], "replace",
                       "replace reads text, the search text and the replacement",
                       'pass strings, for example replace("a-b", "-", "+")')
    search = _string_arg(call, args[1], "replace",
                         "the text, the search text and the replacement must all be strings",
                         "pass the text to search for, for example a dash")
    replacement = _string_arg(call, args[2], "replace",
                              "the text, the search text and the replacement must all be strings",
                              "pass the replacement text, or an empty string to delete matches")
    if search == "":
        _fail(call, "replace search text cannot be empty",
              "an empty search would match between every character",
              "pass the text to replace, for example replace(\"a-b\", \"-\", \"_\")")
    length = len(text) + text.count(search) * (len(replacement) - len(search))
    if length > MAX_SEQUENCE_LENGTH:
        _fail(call, "replacing this text is too large",
              f"the result would have {length} characters; v1 caps sequences at "
              f"{MAX_SEQUENCE_LENGTH}",
              "replace with shorter text, or work on a smaller piece")
    return text.replace(search, replacement)


BUILTINS = {
    "print": Builtin("print", _print, "1 argument", 1, 1),
    "len": Builtin("len", _len, "1 argument", 1, 1),
    "range": Builtin("range", _range, "1 to 3 arguments", 1, 3),
    "str": Builtin("str", _str, "1 argument", 1, 1),
    "int": Builtin("int", _int, "1 argument", 1, 1),
    "float": Builtin("float", _float, "1 argument", 1, 1),
    "floor": Builtin("floor", _floor, "1 argument", 1, 1),
    "min": Builtin("min", _min, "at least 1 argument", 1),
    "max": Builtin("max", _max, "at least 1 argument", 1),
    "abs": Builtin("abs", _abs, "1 argument", 1, 1),
    "sort": Builtin("sort", _sort, "1 argument", 1, 1),
    "split": Builtin("split", _split, "1 to 2 arguments", 1, 2),
    "join": Builtin("join", _join, "2 arguments", 2, 2),
    "trim": Builtin("trim", _trim, "1 argument", 1, 1),
    "replace": Builtin("replace", _replace, "3 arguments", 3, 3),
}
