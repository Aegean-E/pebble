"""Tree-walking evaluator: the runtime semantics of Pebble.

Scope rules are small enough to state in full:

- Names live in one global scope plus one frame per running call. A function sees its own frame
  and the globals, never a caller's locals, which is why v1 has recursion but no closures.
- `let` declares or rebinds in the current scope; `=` rebinds a name that already exists and
  never creates one, so a typo fails loudly instead of quietly becoming a new variable.
- Only expression statements produce a value. `if`, loops, `let` and `=` produce none, and a
  function that finishes without `return` returns none.

Calls are bounded: recursion stops at MAX_CALL_DEPTH with an EvalError whose fix suggests a base
case, and a pathologically long expression is converted from Python's RecursionError into a
Pebble error, so no failure ever reaches a user as a traceback.
"""

import difflib
import sys
from typing import NoReturn

from . import nodes
from .errors import EvalError
from .formatting import is_number, type_name
from .limits import MAX_CALL_DEPTH, MAX_EXPONENT, MAX_INT_BITS, MAX_SEQUENCE_LENGTH
from .stdlib import BUILTINS, Builtin


class _Return(Exception):
    """Internal signal carrying a `return` value out of nested blocks; never escapes run()."""

    def __init__(self, value: object) -> None:
        super().__init__("return")
        self.value = value


class _Break(Exception):
    """Internal signal carrying `break` out of nested blocks to the innermost loop."""


class _Continue(Exception):
    """Internal signal carrying `continue` out of nested blocks to the innermost loop."""


class PebbleFunction:
    """A function defined with `fn`: a name, parameters and a body; no closures in v1."""

    def __init__(self, name: str, params: tuple, body: tuple) -> None:
        self.pebble_name = name
        self.params = params
        self.body = body


def _equal(left, right) -> bool:
    """Pebble equality: ints and floats mix, bools do not, everything else compares within its type."""
    if is_number(left) and is_number(right):
        return left == right
    if type(left) is not type(right):
        return False
    return left == right


class Interpreter:
    """Runs a parsed program; `out` is the stream the builtins write to."""

    def __init__(self, out=None, args=None) -> None:
        self.out = out if out is not None else sys.stdout
        self.globals: dict[str, object] = dict(BUILTINS)
        self.globals["args"] = [str(a) for a in args] if args is not None else []
        self.frames: list[dict[str, object]] = []
        self.call_depth = 0
        self._at = None

    def run(self, program) -> object:
        """Execute a whole program; returns the last statement's value (none for most)."""
        value = None
        try:
            for statement in program:
                value = self.execute(statement)
        except RecursionError:
            node = self._at
            line, col = (node.line, node.col) if node is not None else (1, 1)
            raise EvalError("the program nests too deeply to evaluate", line, col,
                            "one long operator chain costs the evaluator one level per operator",
                            "split the expression into steps with let, or into smaller pieces") \
                from None
        return value

    def execute(self, statement) -> object:
        """One statement; only expression statements carry a value."""
        self._at = statement
        if isinstance(statement, nodes.ExprStmt):
            return self.evaluate(statement.expr)
        if isinstance(statement, nodes.Let):
            self._define(statement.name, self.evaluate(statement.value))
            return None
        if isinstance(statement, nodes.Assign):
            self._assign(statement.name, self.evaluate(statement.value), statement)
            return None
        if isinstance(statement, nodes.IfStmt):
            branch = statement.then_body if self._truth(self.evaluate(statement.condition)) \
                else statement.else_body
            self._execute_block(branch)
            return None
        if isinstance(statement, nodes.WhileStmt):
            self._execute_while(statement)
            return None
        if isinstance(statement, nodes.ForStmt):
            self._execute_for(statement)
            return None
        if isinstance(statement, nodes.FnStmt):
            self._define_function(statement)
            return None
        if isinstance(statement, nodes.ReturnStmt):
            if not self.frames:
                self._fail(statement, "return outside a function",
                           "return ends the current fn, but no function is running",
                           "move it inside a fn body, or delete it")
            raise _Return(self.evaluate(statement.value) if statement.value is not None else None)
        if isinstance(statement, nodes.BreakStmt):
            raise _Break()
        if isinstance(statement, nodes.ContinueStmt):
            raise _Continue()
        raise AssertionError(f"unhandled statement: {type(statement).__name__}")

    def evaluate(self, expression) -> object:
        """One expression, recursively; every failure is an EvalError with the node's position."""
        self._at = expression
        if isinstance(expression, nodes.Literal):
            return expression.value
        if isinstance(expression, nodes.ListLiteral):
            return [self.evaluate(element) for element in expression.elements]
        if isinstance(expression, nodes.Name):
            return self._lookup(expression)
        if isinstance(expression, nodes.Unary):
            return self._evaluate_unary(expression)
        if isinstance(expression, nodes.Binary):
            return self._evaluate_binary(expression)
        if isinstance(expression, nodes.Logical):
            return self._evaluate_logical(expression)
        if isinstance(expression, nodes.Call):
            return self._evaluate_call(expression)
        if isinstance(expression, nodes.Index):
            return self._evaluate_index(expression)
        if isinstance(expression, nodes.Slice):
            return self._evaluate_slice(expression)
        raise AssertionError(f"unhandled expression: {type(expression).__name__}")

    # statements

    def _execute_block(self, body) -> None:
        """Statements in order, in a fresh or existing scope."""
        for statement in body:
            self.execute(statement)

    def _execute_while(self, statement) -> None:
        """A while loop; break and continue affect this innermost loop only."""
        while self._truth(self.evaluate(statement.condition)):
            try:
                self._execute_block(statement.body)
            except _Continue:
                continue
            except _Break:
                break

    def _execute_for(self, statement) -> None:
        """`for name in ...`, walking a list or the characters of a string."""
        iterable = self.evaluate(statement.iterable)
        if not isinstance(iterable, (list, str)):
            self._fail(statement, f"cannot iterate over {type_name(iterable)}",
                       "for-in walks a list or a string",
                       "pass a list or a string, for example [1, 2, 3] or \"abc\"")
        for item in iterable:
            self._define(statement.name, item)
            try:
                self._execute_block(statement.body)
            except _Continue:
                continue
            except _Break:
                break

    def _define_function(self, statement) -> None:
        """A function definition; nested definitions are refused because v1 has no closures."""
        if self.frames:
            self._fail(statement, "functions cannot be defined inside functions",
                       "v1 has no closures, so a nested function could not see the enclosing "
                       "variables",
                       "define it at the top level, or pass the values in as parameters")
        self._define(statement.name, PebbleFunction(statement.name, statement.params,
                                                    statement.body))

    def _define(self, name: str, value) -> None:
        """`let` semantics: bind or rebind the name in the current scope."""
        (self.frames[-1] if self.frames else self.globals)[name] = value

    def _assign(self, name: str, value, node) -> None:
        """`=` semantics: the name must already exist somewhere visible."""
        if self.frames and name in self.frames[-1]:
            self.frames[-1][name] = value
            return
        if name in self.globals:
            self.globals[name] = value
            return
        self._fail(node, f"cannot assign to undeclared name '{name}'",
                   "= rebinds a name that already exists; it never creates one",
                   self._declaration_fix(name))

    def _lookup(self, node) -> object:
        """Resolve a name through the frame chain, then the globals."""
        name = node.identifier
        if self.frames and name in self.frames[-1]:
            return self.frames[-1][name]
        if name in self.globals:
            return self.globals[name]
        self._fail(node, f"unknown name '{name}'",
                   "no variable or builtin with this name is visible here",
                   self._declaration_fix(name))

    def _declaration_fix(self, name: str) -> str:
        """Suggest a close visible name, or how to declare the name being looked for."""
        visible = set(self.globals)
        if self.frames:
            visible |= set(self.frames[-1])
        close = difflib.get_close_matches(name, sorted(visible), n=1, cutoff=0.6)
        if close:
            return f"did you mean '{close[0]}'? otherwise declare it with let {name} = ..."
        return f"check the spelling, or declare it first with let {name} = ..."

    # expressions

    def _evaluate_unary(self, expression) -> object:
        """`-x` on a number, `not x` on any value."""
        value = self.evaluate(expression.operand)
        if expression.op == "not":
            return not self._truth(value)
        if not is_number(value):
            self._fail(expression, f"cannot negate {type_name(value)}",
                       "unary minus needs a number",
                       "apply it to an int or a float")
        return -value

    def _evaluate_logical(self, expression) -> object:
        """`and` / `or` short-circuit and return an operand, so `x or fallback` works."""
        left = self.evaluate(expression.left)
        if expression.op == "and":
            return self.evaluate(expression.right) if self._truth(left) else left
        return left if self._truth(left) else self.evaluate(expression.right)

    def _evaluate_binary(self, expression) -> object:
        """Arithmetic, power, comparison and equality, each with its own message."""
        left = self.evaluate(expression.left)
        right = self.evaluate(expression.right)
        op = expression.op
        if op == "+":
            return self._add(expression, left, right)
        if op == "-":
            return self._numeric(expression, left, right, "subtract", lambda a, b: a - b)
        if op == "*":
            return self._multiply(expression, left, right)
        if op == "/":
            return self._divide(expression, left, right)
        if op == "%":
            return self._remainder(expression, left, right)
        if op == "^":
            return self._power(expression, left, right)
        if op in ("==", "!="):
            return _equal(left, right) if op == "==" else not _equal(left, right)
        return self._order(expression, left, right)

    def _add(self, expression, left, right) -> object:
        """Numbers add, strings join, lists join; nothing else mixes."""
        if is_number(left) and is_number(right):
            return self._check_int(expression, left + right)
        if isinstance(left, str) and isinstance(right, str):
            return left + right
        if isinstance(left, list) and isinstance(right, list):
            return left + right
        self._fail(expression, f"cannot add {type_name(left)} and {type_name(right)}",
                   "+ adds two numbers, joins two strings or joins two lists",
                   "make both operands numbers, or both the same kind of sequence")

    def _numeric(self, expression, left, right, word: str, operation):
        """A binary operation over two numbers, with a shared type error."""
        if is_number(left) and is_number(right):
            return self._check_int(expression, operation(left, right))
        self._fail(expression, f"cannot {word} {type_name(left)} and {type_name(right)}",
                   f"{word}ing needs two numbers",
                   "make both operands numbers")

    def _multiply(self, expression, left, right) -> object:
        """Numbers multiply; a string or list repeats by a whole count."""
        if is_number(left) and is_number(right):
            return self._check_int(expression, left * right)
        sequence, count = (left, right) if isinstance(left, (str, list)) else (right, left)
        if isinstance(sequence, (str, list)) and isinstance(count, int) and not isinstance(count, bool):
            if count < 0:
                self._fail(expression, f"cannot repeat a {type_name(sequence)} {count} times",
                           "the repeat count must be zero or more",
                           "use a count of 0 or more")
            length = len(sequence) * count
            if length > MAX_SEQUENCE_LENGTH:
                unit = "characters" if isinstance(sequence, str) else "elements"
                self._fail(expression,
                           f"repeating a {type_name(sequence)} {count} times is too large",
                           f"the result would have {length} {unit}; v1 caps sequences at "
                           f"{MAX_SEQUENCE_LENGTH}",
                           "use a smaller count, or build the sequence with a loop")
            return sequence * count
        self._fail(expression, f"cannot multiply {type_name(left)} and {type_name(right)}",
                   "* multiplies two numbers, or repeats a string or list by a whole count",
                   "multiply two numbers, or multiply a string or list by an int")

    def _divide(self, expression, left, right) -> object:
        """Always a float; a zero divisor and an overflowing result are refused with a position."""
        if is_number(left) and is_number(right):
            if right == 0:
                self._fail(expression, "division by zero",
                           "dividing by zero has no defined result",
                           "guard the divisor with an if, or change it")
            try:
                return left / right
            except OverflowError:
                self._fail(expression, "the result is too large for a float",
                           "dividing these ints needs a float beyond the largest float",
                           "divide smaller numbers, or scale them down first")
        self._fail(expression, f"cannot divide {type_name(left)} and {type_name(right)}",
                   "dividing needs two numbers",
                   "make both operands numbers")

    def _remainder(self, expression, left, right) -> object:
        """The Python remainder: its sign follows the divisor."""
        if is_number(left) and is_number(right):
            if right == 0:
                self._fail(expression, "remainder by zero",
                           "the divisor is zero, and x % 0 is undefined",
                           "guard the divisor with an if, or change it")
            return left % right
        self._fail(expression, f"cannot take the remainder of {type_name(left)} and "
                               f"{type_name(right)}",
                   "remainder ( % ) needs two numbers",
                   "make both operands numbers")

    def _power(self, expression, left, right) -> object:
        """Right-associative `^`, with guards for huge, unreal and undefined results."""
        if not (is_number(left) and is_number(right)):
            self._fail(expression, f"cannot raise the power of {type_name(left)} and "
                                   f"{type_name(right)}",
                       "power ( ^ ) needs two numbers",
                       "make both operands numbers")
        if left == 0 and right < 0:
            self._fail(expression, "zero cannot be raised to a negative power",
                       "a negative exponent divides by the base, and zero has no reciprocal",
                       "use an exponent of zero or more")
        if isinstance(right, int) and right > MAX_EXPONENT:
            self._fail(expression, f"exponent {right} is too large",
                       f"v1 caps integer exponents at {MAX_EXPONENT} so results stay small",
                       f"use an exponent of {MAX_EXPONENT} or less")
        if isinstance(left, int) and isinstance(right, int) and right > 0 and abs(left) > 1:
            lower_bound_bits = (abs(left).bit_length() - 1) * right + 1
            if lower_bound_bits > MAX_INT_BITS:
                self._fail(expression, "integer result is too large",
                           "the result would exceed the v1 cap of about 4000 decimal digits",
                           "use a smaller base or exponent, or a float for an approximation")
        if left < 0 and isinstance(right, float) and not right.is_integer():
            self._fail(expression, "the result is not a real number",
                       "a negative base with a fractional exponent has no real result",
                       "use an int exponent, or a non-negative base")
        try:
            return self._check_int(expression, left ** right)
        except OverflowError:
            self._fail(expression, "the result is too large for a float",
                       "the exponent pushes the result past the largest float",
                       "use a smaller exponent")

    def _check_int(self, expression, value) -> object:
        """Refuse an int above the digit cap so arithmetic and printing stay bounded."""
        if isinstance(value, int) and not isinstance(value, bool) \
                and value.bit_length() > MAX_INT_BITS:
            self._fail(expression, "integer result is too large",
                       "the result would exceed the v1 cap of about 4000 decimal digits",
                       "scale the values down, or use a float for an approximation")
        return value

    def _order(self, expression, left, right) -> object:
        """`< <= > >=` on two numbers or two strings."""
        if (is_number(left) and is_number(right)) or \
                (isinstance(left, str) and isinstance(right, str)):
            if expression.op == "<":
                return left < right
            if expression.op == "<=":
                return left <= right
            if expression.op == ">":
                return left > right
            return left >= right
        self._fail(expression, f"cannot order {type_name(left)} and {type_name(right)}",
                   "ordering needs two numbers or two strings",
                   "compare numbers with numbers, or strings with strings")

    def _evaluate_index(self, expression) -> object:
        """`target[index]` on lists and strings, with negative offsets and length in errors."""
        target = self.evaluate(expression.target)
        index = self.evaluate(expression.index)
        if isinstance(index, bool) or not isinstance(index, int):
            self._fail(expression, f"cannot index with {type_name(index)}",
                       "an index must be an int",
                       "use a whole number as the index")
        if not isinstance(target, (list, str)):
            self._fail(expression, f"cannot index {type_name(target)}",
                       "only lists and strings have elements",
                       "index a list or a string")
        length = len(target)
        if index < -length or index >= length:
            if length == 0:
                self._fail(expression, f"index {index} is out of range",
                           f"the {type_name(target)} is empty",
                           "add elements before indexing")
            self._fail(expression, f"index {index} is out of range",
                       f"the {type_name(target)} has {length} "
                       f"element{'s' if length != 1 else ''}, so valid indexes run from "
                       f"-{length} to {length - 1}",
                       "check the index, or the length with len(...)")
        return target[index]

    def _evaluate_slice(self, expression) -> object:
        """`target[start:stop:step]` on lists and strings, with Python-style bounds."""
        target = self.evaluate(expression.target)
        if not isinstance(target, (list, str)):
            self._fail(expression, f"cannot slice {type_name(target)}",
                       "only lists and strings have subsequences",
                       "slice a list or a string")
        start = self._slice_part(expression.start, "start")
        stop = self._slice_part(expression.stop, "stop")
        step = self._slice_part(expression.step, "step")
        if step == 0:
            self._fail(expression.step, "slice step cannot be zero",
                       "a step of zero would never advance through the sequence",
                       "use a step of 1, or a negative step to walk backwards")
        return target[start:stop:step]

    def _slice_part(self, node, role: str):
        """One optional slice part: an int, evaluated only when it is present."""
        if node is None:
            return None
        value = self.evaluate(node)
        if isinstance(value, bool) or not isinstance(value, int):
            self._fail(node, f"slice {role} must be an int, got {type_name(value)}",
                       "start, stop and step are whole-number positions",
                       "use int bounds, for example xs[1:3]")
        return value

    def _evaluate_call(self, expression) -> object:
        """A builtin or a defined function can be called."""
        callee = self.evaluate(expression.callee)
        if isinstance(callee, Builtin):
            return self._call_builtin(expression, callee)
        if isinstance(callee, PebbleFunction):
            return self._call_function(expression, callee)
        fix = "call a function, or remove the parentheses"
        if isinstance(expression.callee, nodes.Name) and expression.callee.identifier == "args":
            fix = "'args' is already a list of strings; index it with args[0] or iterate with for a in args"
        self._fail(expression, f"cannot call {type_name(callee)}",
                   "only a function or builtin can be called",
                   fix)

    def _call_builtin(self, expression, builtin: Builtin) -> object:
        """Check the builtin's arity, evaluate its arguments, then run it."""
        count = len(expression.args)
        if count < builtin.min_args or \
                (builtin.max_args is not None and count > builtin.max_args):
            self._fail(expression,
                       f"{builtin.pebble_name} expects {builtin.expects}, got {count}",
                       "builtins accept a fixed number of arguments",
                       f"call {builtin.pebble_name} with {builtin.expects}")
        args = [self.evaluate(arg) for arg in expression.args]
        return builtin.impl(self, expression, args)

    def _call_function(self, expression, function: PebbleFunction) -> object:
        """Arity check, depth check, a fresh frame for the parameters, then the body."""
        expected = len(function.params)
        got = len(expression.args)
        if expected != got:
            plural = "s" if expected != 1 else ""
            self._fail(expression, f"{function.pebble_name} expects {expected} argument{plural}, "
                                   f"got {got}",
                       "the number of arguments must match the parameters the function declares",
                       f"pass {expected} argument{plural}, or change the parameter list")
        if self.call_depth >= MAX_CALL_DEPTH:
            self._fail(expression, f"call stack too deep (more than {MAX_CALL_DEPTH} calls)",
                       "every call adds a frame; this program recursed past the limit",
                       "give the recursion a base case that returns without calling again")
        frame = {name: self.evaluate(arg) for name, arg in zip(function.params, expression.args)}
        self.frames.append(frame)
        self.call_depth += 1
        try:
            for statement in function.body:
                self.execute(statement)
        except _Return as returned:
            return returned.value
        finally:
            self.call_depth -= 1
            self.frames.pop()
        return None

    @staticmethod
    def _truth(value) -> bool:
        """Pebble truthiness: false, none, zero and empties are falsy; everything else is truthy."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, (str, list)):
            return len(value) > 0
        return True

    def _fail(self, node, message: str, why: str, fix: str) -> NoReturn:
        """Raise the positioned EvalError; every runtime failure goes through here."""
        raise EvalError(message, node.line, node.col, why, fix)
