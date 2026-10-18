"""How Pebble names and displays values in messages and in print."""

_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}


def is_number(value) -> bool:
    """True for int and float, but not for bool: Pebble keeps booleans out of arithmetic."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def type_name(value) -> str:
    """The name Pebble uses for this value's type: int, string, list, none, function."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if getattr(value, "pebble_name", None):
        return "function"
    return type(value).__name__


def format_value(value) -> str:
    """The text a value shows as: strings bare at the top, quoted inside a list."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "[" + ", ".join(_format_element(element) for element in value) + "]"
    if isinstance(value, (int, float)):
        return str(value)
    name = getattr(value, "pebble_name", None)
    if name is not None:
        kind = "builtin" if getattr(value, "is_builtin", False) else "fn"
        return f"<{kind} {name}>"
    return str(value)


def _format_element(value) -> str:
    """An element inside a list: strings are quoted so their boundaries stay visible."""
    if isinstance(value, str):
        return '"' + "".join(_ESCAPES.get(ch, ch) for ch in value) + '"'
    return format_value(value)
