"""List helpers: sort, with the ordering rules min and max already share."""

import unittest
from io import StringIO

from pebble.errors import EvalError
from pebble.evaluator import Interpreter
from pebble.lexer import tokenize
from pebble.parser import parse


def evaluate(source: str):
    """Evaluate `source` with a fresh interpreter; the last statement's value comes back."""
    return Interpreter(out=StringIO()).run(parse(tokenize(source)))


class SortTests(unittest.TestCase):
    """One behaviour per test; the result is a new list and the input is untouched."""

    def eval_error(self, source: str) -> EvalError:
        """The EvalError `source` raises."""
        with self.assertRaises(EvalError) as caught:
            evaluate(source)
        return caught.exception

    def test_sort_orders_numbers_ascending(self) -> None:
        self.assertEqual(evaluate("sort([3, 1, 2])"), [1, 2, 3])
        self.assertEqual(evaluate("sort([-1, 2.5, 0])"), [-1, 0, 2.5])
        self.assertEqual(evaluate("sort([])"), [])
        self.assertEqual(evaluate("sort([7])"), [7])

    def test_sort_orders_strings_by_code_point(self) -> None:
        self.assertEqual(evaluate('sort(["b", "a", "c"])'), ["a", "b", "c"])
        self.assertEqual(evaluate('sort(["B", "a"])'), ["B", "a"])
        self.assertEqual(evaluate('sort(["", "a"])'), ["", "a"])

    def test_sort_is_stable_for_equal_values(self) -> None:
        self.assertEqual(evaluate("sort([1.0, 1, 0])"), [0, 1.0, 1])
        self.assertEqual(evaluate('sort(["a", "a"])'), ["a", "a"])

    def test_sort_returns_a_new_list_and_leaves_the_input_alone(self) -> None:
        stream = StringIO()
        Interpreter(out=stream).run(
            parse(tokenize("let xs = [3, 1]\nlet ys = sort(xs)\nprint(xs)\nprint(ys)")))
        self.assertEqual(stream.getvalue(), "[3, 1]\n[1, 3]\n")
        self.assertIs(evaluate("let xs = [3, 1]\nxs == sort(xs)"), False)

    def test_sort_composes_with_a_reverse_slice(self) -> None:
        self.assertEqual(evaluate("sort([3, 1, 2])[::-1]"), [3, 2, 1])

    def test_sort_needs_a_list(self) -> None:
        error = self.eval_error("sort(5)")
        self.assertIn("sort needs a list, got int", error.message)
        self.assertIn("values", error.why)
        self.assertEqual((error.line, error.col), (1, 5))
        self.assertIn("sort needs a list, got string",
                      self.eval_error('sort("abc")').message)
        self.assertIn("sort needs a list, got none",
                      self.eval_error("sort(none)").message)

    def test_sort_refuses_values_it_cannot_order(self) -> None:
        self.assertIn("cannot compare bool with sort",
                      self.eval_error("sort([true])").message)
        self.assertIn("cannot compare function with sort",
                      self.eval_error("sort([len])").message)
        self.assertIn("cannot compare list with sort",
                      self.eval_error("sort([[1]])").message)

    def test_sort_refuses_mixed_kinds(self) -> None:
        error = self.eval_error('sort([1, "a"])')
        self.assertIn("cannot compare int and string", error.message)
        self.assertIn("numbers with numbers", error.why)
        self.assertIn("make every value the same kind", error.fix)

    def test_sort_arity_is_one(self) -> None:
        self.assertIn("sort expects 1 argument, got 0", self.eval_error("sort()").message)
        self.assertIn("sort expects 1 argument, got 2",
                      self.eval_error("sort([1], [2])").message)
