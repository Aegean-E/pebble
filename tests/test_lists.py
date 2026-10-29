"""List helpers: sort and sum, with the numeric rules min, max and sum share."""

import unittest
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from pebble.errors import EvalError
from pebble.evaluator import Interpreter
from pebble.lexer import tokenize
from pebble.parser import parse
from pebble.stdlib import BUILTINS

BUILTIN_CALL = SimpleNamespace(line=1, col=1)


def evaluate(source: str):
    """Evaluate `source` with a fresh interpreter; the last statement's value comes back."""
    return Interpreter(out=StringIO()).run(parse(tokenize(source)))


def call_builtin(name: str, *args):
    """Call one builtin directly, for guards that plain source reaches only with big values."""
    return BUILTINS[name].impl(None, BUILTIN_CALL, list(args))


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


class SumTests(unittest.TestCase):
    """sum totals a list of numbers and keeps the int/float distinction."""

    def eval_error(self, source: str) -> EvalError:
        """The EvalError `source` raises."""
        with self.assertRaises(EvalError) as caught:
            evaluate(source)
        return caught.exception

    def test_sum_totals_ints_and_returns_an_int(self) -> None:
        self.assertEqual(evaluate("sum([1, 2, 3])"), 6)
        self.assertIs(type(evaluate("sum([1, 2, 3])")), int)
        self.assertEqual(evaluate("sum([-5, 5])"), 0)
        self.assertEqual(evaluate("sum([])"), 0)

    def test_sum_promotes_to_a_float_when_any_value_is_a_float(self) -> None:
        self.assertEqual(evaluate("sum([1, 2.5])"), 3.5)
        self.assertIs(type(evaluate("sum([1, 2.5])")), float)
        self.assertEqual(evaluate("sum([1.0])"), 1.0)

    def test_sum_needs_a_list(self) -> None:
        error = self.eval_error("sum(5)")
        self.assertIn("sum needs a list, got int", error.message)
        self.assertIn("numbers", error.why)
        self.assertEqual((error.line, error.col), (1, 4))
        self.assertIn("sum needs a list, got none", self.eval_error("sum(none)").message)

    def test_sum_refuses_non_numbers_and_bools(self) -> None:
        error = self.eval_error('sum([1, "a"])')
        self.assertIn("sum needs a list of numbers, found string at index 1",
                      error.message)
        self.assertIn("booleans are not numbers", error.why)
        self.assertIn("sum needs a list of numbers, found bool at index 0",
                      self.eval_error("sum([true])").message)
        self.assertIn("sum needs a list of numbers, found list at index 0",
                      self.eval_error("sum([[1]])").message)

    def test_sum_refuses_an_int_result_over_the_digit_cap(self) -> None:
        with mock.patch("pebble.stdlib.MAX_INT_BITS", 8):
            self.assertEqual(call_builtin("sum", [10, 20]), 30)
            with self.assertRaises(EvalError) as caught:
                call_builtin("sum", [200, 200])
        self.assertIn("integer result is too large", caught.exception.message)
        self.assertIn("scale the values down", caught.exception.fix)

    def test_sum_refuses_a_non_finite_float_result(self) -> None:
        error = self.eval_error('sum([float("1e308"), float("1e308")])')
        self.assertIn("the result is too large for a float", error.message)
        self.assertIn("beyond the largest float", error.why)

    def test_sum_arity_is_one(self) -> None:
        self.assertIn("sum expects 1 argument, got 0", self.eval_error("sum()").message)
        self.assertIn("sum expects 1 argument, got 2",
                      self.eval_error("sum([1], [2])").message)


class AverageTests(unittest.TestCase):
    """average returns the mean as a float, and refuses an empty list explicitly."""

    def eval_error(self, source: str) -> EvalError:
        """The EvalError `source` raises."""
        with self.assertRaises(EvalError) as caught:
            evaluate(source)
        return caught.exception

    def test_average_returns_the_mean_as_a_float(self) -> None:
        self.assertEqual(evaluate("average([1, 2, 3])"), 2.0)
        self.assertIs(type(evaluate("average([1, 2, 3])")), float)
        self.assertEqual(evaluate("average([2, 3])"), 2.5)
        self.assertEqual(evaluate("average([7])"), 7.0)
        self.assertEqual(evaluate("average([-2, 2])"), 0.0)

    def test_average_of_an_empty_list_is_an_error_not_zero(self) -> None:
        error = self.eval_error("average([])")
        self.assertIn("average needs at least one value", error.message)
        self.assertIn("nothing to divide by", error.why)
        self.assertIn("non-empty list", error.fix)
        self.assertEqual((error.line, error.col), (1, 8))

    def test_average_needs_a_list(self) -> None:
        error = self.eval_error("average(5)")
        self.assertIn("average needs a list, got int", error.message)
        self.assertIn("numbers", error.why)
        self.assertIn("average needs a list, got none",
                      self.eval_error("average(none)").message)

    def test_average_refuses_non_numbers_and_bools(self) -> None:
        self.assertIn("average needs a list of numbers, found string at index 1",
                      self.eval_error('average([1, "a"])').message)
        self.assertIn("average needs a list of numbers, found bool at index 0",
                      self.eval_error("average([true, 1])").message)

    def test_average_refuses_a_non_finite_result(self) -> None:
        error = self.eval_error('average([float("1e308"), float("1e308")])')
        self.assertIn("the result is too large for a float", error.message)
        self.assertIn("beyond the largest float", error.why)

    def test_average_of_a_huge_int_is_a_pebble_error_not_a_host_overflow(self) -> None:
        error = self.eval_error("average([10 ^ 3990])")
        self.assertIn("the result is too large for a float", error.message)
        self.assertIn("no float value", error.why)
        self.assertIn("scale them down", error.fix)

    def test_average_arity_is_one(self) -> None:
        self.assertIn("average expects 1 argument, got 0",
                      self.eval_error("average()").message)
        self.assertIn("average expects 1 argument, got 2",
                      self.eval_error("average([1], [2])").message)


class ListSearchTests(unittest.TestCase):
    """index_of and the list form of contains both use Pebble's own equality."""

    def eval_error(self, source: str) -> EvalError:
        """The EvalError `source` raises."""
        with self.assertRaises(EvalError) as caught:
            evaluate(source)
        return caught.exception

    # index_of

    def test_index_of_returns_the_first_matching_index(self) -> None:
        self.assertEqual(evaluate("index_of([10, 20, 30], 20)"), 1)
        self.assertEqual(evaluate("index_of([1, 2, 1], 1)"), 0)
        self.assertEqual(evaluate('index_of(["a", "b"], "b")'), 1)
        self.assertIs(type(evaluate("index_of([1], 1)")), int)

    def test_index_of_returns_none_for_a_miss(self) -> None:
        self.assertIsNone(evaluate("index_of([1, 2], 3)"))
        self.assertIsNone(evaluate("index_of([], 1)"))

    def test_index_of_uses_pebble_equality_across_number_types(self) -> None:
        self.assertEqual(evaluate("index_of([1.0, 2], 1)"), 0)
        self.assertEqual(evaluate("index_of([1, 2], 1.0)"), 0)

    def test_index_of_does_not_mix_bools_and_numbers(self) -> None:
        self.assertIsNone(evaluate("index_of([1, 2], true)"))
        self.assertIsNone(evaluate("index_of([true], 1)"))
        self.assertEqual(evaluate("index_of([true, false], true)"), 0)

    def test_index_of_matches_a_nested_list_deeply(self) -> None:
        self.assertEqual(evaluate("index_of([[1], [2, 3]], [2, 3])"), 1)
        self.assertIsNone(evaluate("index_of([[1], [2]], [3])"))

    def test_index_of_does_not_mix_kinds(self) -> None:
        self.assertIsNone(evaluate('index_of([1, 2], "1")'))
        self.assertIsNone(evaluate("index_of([none], 0)"))
        self.assertEqual(evaluate("index_of([none, 0], none)"), 0)

    def test_index_of_needs_a_list(self) -> None:
        error = self.eval_error('index_of("abc", "a")')
        self.assertIn("index_of needs a list, got string", error.message)
        self.assertIn("position", error.why)
        self.assertEqual((error.line, error.col), (1, 9))
        self.assertIn("index_of needs a list, got int",
                      self.eval_error("index_of(5, 1)").message)

    def test_index_of_arity_is_two(self) -> None:
        self.assertIn("index_of expects 2 arguments, got 1",
                      self.eval_error("index_of([1])").message)
        self.assertIn("index_of expects 2 arguments, got 3",
                      self.eval_error("index_of([1], 1, 2)").message)

    # contains on a list

    def test_contains_accepts_a_list_and_uses_the_same_equality(self) -> None:
        self.assertIs(evaluate("contains([1, 2, 3], 2)"), True)
        self.assertIs(evaluate("contains([1, 2, 3], 4)"), False)
        self.assertIs(evaluate("contains([], 1)"), False)
        self.assertIs(evaluate("contains([1.0], 1)"), True)
        self.assertIs(evaluate("contains([[1]], [1])"), True)
        self.assertIs(evaluate("contains([1], true)"), False)

    def test_contains_still_searches_text_and_refuses_an_empty_string_search(self) -> None:
        self.assertIs(evaluate('contains("abc", "b")'), True)
        error = self.eval_error('contains("abc", "")')
        self.assertIn("contains search text cannot be empty", error.message)

    def test_contains_refuses_other_first_arguments(self) -> None:
        self.assertIn("contains needs a string, got int",
                      self.eval_error("contains(5, 1)").message)
        self.assertIn("contains needs a string, got none",
                      self.eval_error("contains(none, 1)").message)
