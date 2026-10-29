"""Builtin tests: the core builtins, their errors and the display form of values."""

import unittest
from io import StringIO
from types import SimpleNamespace

from pebble.errors import EvalError
from pebble.evaluator import Interpreter
from pebble.lexer import tokenize
from pebble.parser import parse
from pebble.stdlib import BUILTINS

BUILTIN_CALL = SimpleNamespace(line=1, col=1)


def evaluate(source: str, out=None):
    """Evaluate `source` with a fresh interpreter; the last statement's value comes back."""
    return Interpreter(out=out if out is not None else StringIO()).run(parse(tokenize(source)))


def call_builtin(name: str, *args):
    """Call one builtin directly, for guards that user source can no longer reach."""
    return BUILTINS[name].impl(None, BUILTIN_CALL, list(args))


def printed(source: str) -> str:
    """Everything `source` writes through print."""
    stream = StringIO()
    evaluate(source, out=stream)
    return stream.getvalue()


class BuiltinTests(unittest.TestCase):
    """One behaviour per test; messages, positions and return values are asserted."""

    def eval_error(self, source: str) -> EvalError:
        """The EvalError `source` raises."""
        with self.assertRaises(EvalError) as caught:
            evaluate(source)
        return caught.exception

    # print and display form

    def test_print_writes_the_display_form_and_a_newline(self) -> None:
        self.assertEqual(printed("print(42)"), "42\n")
        self.assertEqual(printed('print("hi")'), "hi\n")
        self.assertEqual(printed("print(true)"), "true\n")
        self.assertEqual(printed("print(none)"), "none\n")
        self.assertEqual(printed("print(2.0)"), "2.0\n")

    def test_print_returns_none_and_handles_a_string_escape(self) -> None:
        self.assertIsNone(evaluate('print("a\\nb")'))
        self.assertEqual(printed('print("a\\nb")'), "a\nb\n")

    def test_lists_display_with_quoted_strings_and_nested_values(self) -> None:
        self.assertEqual(printed('print([1, "a", true, none, [2]])'),
                         '[1, "a", true, none, [2]]\n')
        self.assertEqual(printed('print(["a\\nb", "q\\"q"])'),
                         '["a\\nb", "q\\"q"]\n')

    def test_functions_and_builtins_display_by_name(self) -> None:
        self.assertEqual(printed("fn f() { }\nprint(f)\nprint(len)"),
                         "<fn f>\n<builtin len>\n")

    def test_print_has_a_fixed_arity(self) -> None:
        error = self.eval_error("print(1, 2)")
        self.assertIn("print expects 1 argument, got 2", error.message)
        self.assertEqual((error.line, error.col), (1, 6))

    # len

    def test_len_counts_lists_and_strings(self) -> None:
        self.assertEqual(evaluate("len([1, 2, 3])"), 3)
        self.assertEqual(evaluate('len("abc")'), 3)
        self.assertEqual(evaluate("len([])"), 0)

    def test_len_rejects_other_types(self) -> None:
        error = self.eval_error("len(5)")
        self.assertIn("cannot take the length of int", error.message)
        self.assertIn("string or a list", error.why)
        self.assertIn("len([1, 2])", error.fix)

    # range

    def test_range_builds_half_open_lists(self) -> None:
        self.assertEqual(evaluate("range(4)"), [0, 1, 2, 3])
        self.assertEqual(evaluate("range(2, 5)"), [2, 3, 4])
        self.assertEqual(evaluate("range(3, 3)"), [])
        self.assertEqual(evaluate("range(-2)"), [])

    def test_range_needs_int_arguments(self) -> None:
        error = self.eval_error("range(2.5)")
        self.assertIn("range needs int arguments, got float", error.message)
        self.assertIn("whole numbers", error.why)
        self.assertIn("range needs int arguments, got bool",
                      self.eval_error("range(true)").message)

    def test_range_accepts_a_step(self) -> None:
        self.assertEqual(evaluate("range(0, 10, 3)"), [0, 3, 6, 9])
        self.assertEqual(evaluate("range(3, 0, -1)"), [3, 2, 1])
        self.assertEqual(evaluate("range(0, 5, -1)"), [])
        self.assertEqual(evaluate("range(5, 0, 2)"), [])
        self.assertEqual(evaluate("range(0, 10, 100)"), [0])

    def test_range_step_must_not_be_zero(self) -> None:
        error = self.eval_error("range(0, 5, 0)")
        self.assertIn("range step cannot be zero", error.message)
        self.assertIn("never advance", error.why)

    def test_a_stepped_range_is_still_length_capped(self) -> None:
        error = self.eval_error("range(0, 2000001)")
        self.assertIn("range would produce 2000001 values", error.message)
        error = self.eval_error("range(2000001, 0, -1)")
        self.assertIn("range would produce 2000001 values", error.message)

    def test_range_arity_is_one_to_three(self) -> None:
        self.assertIn("range expects 1 to 3 arguments, got 0",
                      self.eval_error("range()").message)
        self.assertIn("range expects 1 to 3 arguments, got 4",
                      self.eval_error("range(1, 2, 3, 4)").message)

    # str

    def test_str_returns_the_display_form(self) -> None:
        self.assertEqual(evaluate("str(42)"), "42")
        self.assertEqual(evaluate("str(2.5)"), "2.5")
        self.assertEqual(evaluate("str(true)"), "true")
        self.assertEqual(evaluate("str(none)"), "none")
        self.assertEqual(evaluate('str("abc")'), "abc")
        self.assertEqual(evaluate('str([1, "a"])'), '[1, "a"]')

    # int

    def test_int_truncates_floats_toward_zero(self) -> None:
        self.assertEqual(evaluate("int(3.9)"), 3)
        self.assertEqual(evaluate("int(-3.9)"), -3)
        self.assertEqual(evaluate("int(7)"), 7)
        self.assertIs(type(evaluate("int(7.0)")), int)

    def test_int_parses_signed_decimal_strings(self) -> None:
        self.assertEqual(evaluate('int("42")'), 42)
        self.assertEqual(evaluate('int("-7")'), -7)
        self.assertEqual(evaluate('int("+7")'), 7)

    def test_int_rejects_bad_strings_and_other_types(self) -> None:
        error = self.eval_error('int("3.5")')
        self.assertIn("cannot convert string '3.5' to int", error.message)
        self.assertIn("optional sign and digits only", error.why)
        self.assertIn("cannot convert string ' 4' to int", self.eval_error('int(" 4")').message)
        self.assertIn("cannot convert bool to int", self.eval_error("int(true)").message)
        self.assertIn("cannot convert none to int", self.eval_error("int(none)").message)

    def test_int_rejects_non_finite_floats(self) -> None:
        for value in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(EvalError) as caught:
                    call_builtin("int", value)
                self.assertIn("cannot convert a non-finite float to int",
                              caught.exception.message)

    # float

    def test_float_converts_ints_floats_and_decimal_strings(self) -> None:
        self.assertEqual(evaluate("float(3)"), 3.0)
        self.assertIs(type(evaluate("float(3)")), float)
        self.assertEqual(evaluate("float(2.5)"), 2.5)
        self.assertEqual(evaluate('float("2.5")'), 2.5)
        self.assertEqual(evaluate('float("-7")'), -7.0)
        self.assertEqual(evaluate('float("+3.0e2")'), 300.0)

    def test_float_rejects_bad_strings_and_bools(self) -> None:
        error = self.eval_error('float("3.5.1")')
        self.assertIn("cannot convert string '3.5.1' to float", error.message)
        self.assertIn("cannot convert string 'nan' to float", self.eval_error('float("nan")').message)
        self.assertIn("cannot convert string ' 4' to float", self.eval_error('float(" 4")').message)
        self.assertIn("cannot convert bool to float", self.eval_error("float(true)").message)
        self.assertIn("cannot convert none to float", self.eval_error("float(none)").message)

    def test_float_refuses_a_result_that_is_not_finite(self) -> None:
        error = self.eval_error('float("1e999")')
        self.assertIn("cannot convert a non-finite float", error.message)
        error = self.eval_error("float(10 ^ 309)")
        self.assertIn("cannot convert int to float", error.message)
        self.assertIn("largest float", error.why)
        for value in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(EvalError) as caught:
                    call_builtin("float", value)
                self.assertIn("cannot convert a non-finite float",
                              caught.exception.message)

    # floor

    def test_floor_rounds_down_to_an_int(self) -> None:
        self.assertEqual(evaluate("floor(3.9)"), 3)
        self.assertEqual(evaluate("floor(-3.1)"), -4)
        self.assertEqual(evaluate("floor(4)"), 4)
        self.assertIs(type(evaluate("floor(4.0)")), int)

    def test_floor_rejects_non_numbers_and_non_finite_floats(self) -> None:
        error = self.eval_error('floor("3")')
        self.assertIn("cannot take the floor of string", error.message)
        self.assertIn("floor needs a number", error.why)
        for value in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(EvalError) as caught:
                    call_builtin("floor", value)
                self.assertIn("cannot take the floor of a non-finite float",
                              caught.exception.message)

    # round

    def test_round_returns_the_nearest_int(self) -> None:
        self.assertEqual(evaluate("round(3.4)"), 3)
        self.assertEqual(evaluate("round(3.6)"), 4)
        self.assertEqual(evaluate("round(4)"), 4)
        self.assertIs(type(evaluate("round(4)")), int)
        self.assertIs(type(evaluate("round(4.0)")), int)
        self.assertEqual(evaluate("round(-3.6)"), -4)

    def test_round_ties_go_away_from_zero(self) -> None:
        self.assertEqual(evaluate("round(0.5)"), 1)
        self.assertEqual(evaluate("round(1.5)"), 2)
        self.assertEqual(evaluate("round(2.5)"), 3)
        self.assertEqual(evaluate("round(-0.5)"), -1)
        self.assertEqual(evaluate("round(-2.5)"), -3)

    def test_round_to_decimal_places_returns_a_float(self) -> None:
        self.assertEqual(evaluate("round(2.675, 2)"), 2.68)
        self.assertIs(type(evaluate("round(2.675, 2)")), float)
        self.assertEqual(evaluate("round(1.2345, 3)"), 1.235)
        self.assertEqual(evaluate("round(1.2355, 3)"), 1.236)
        self.assertEqual(evaluate("round(1.005, 2)"), 1.01)
        self.assertEqual(evaluate("round(3.5, 0)"), 4.0)
        self.assertEqual(evaluate("round(-2.675, 2)"), -2.68)
        self.assertEqual(evaluate("round(7, 2)"), 7.0)

    def test_round_rejects_non_numbers_and_non_finite_floats(self) -> None:
        error = self.eval_error('round("3")')
        self.assertIn("cannot round string", error.message)
        self.assertIn("round needs a number", error.why)
        self.assertIn("cannot round bool", self.eval_error("round(true)").message)
        for value in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(EvalError) as caught:
                    call_builtin("round", value)
                self.assertIn("cannot round a non-finite float",
                              caught.exception.message)

    def test_round_digits_must_be_an_int_in_range(self) -> None:
        self.assertIn("round needs an int digit count, got float",
                      self.eval_error("round(1.5, 1.5)").message)
        self.assertIn("round needs an int digit count, got bool",
                      self.eval_error("round(1.5, true)").message)
        error = self.eval_error("round(1.5, 16)")
        self.assertIn("round digit count 16 is out of range", error.message)
        self.assertIn("0 to 15", error.why)
        self.assertIn("round digit count -1 is out of range",
                      self.eval_error("round(1.5, -1)").message)

    def test_round_of_a_huge_int_is_exact_or_a_positioned_error(self) -> None:
        self.assertEqual(evaluate("round(10 ^ 300)"), 10 ** 300)
        error = self.eval_error("round(10 ^ 3990, 2)")
        self.assertIn("the result is too large for a float", error.message)
        self.assertIn("no float value", error.why)
        self.assertIn("without a digit count", error.fix)

    def test_round_of_a_huge_float_stays_finite(self) -> None:
        self.assertEqual(evaluate("round(float(10 ^ 300))"), evaluate("int(float(10 ^ 300))"))
        self.assertEqual(evaluate("round(float(10 ^ 300), 2)"), evaluate("float(10 ^ 300)"))

    def test_round_arity_is_one_or_two(self) -> None:
        self.assertIn("round expects 1 or 2 arguments, got 0",
                      self.eval_error("round()").message)
        self.assertIn("round expects 1 or 2 arguments, got 3",
                      self.eval_error("round(1, 2, 3)").message)

    # min and max

    def test_min_and_max_compare_numbers_and_strings(self) -> None:
        self.assertEqual(evaluate("min(3, 1, 2)"), 1)
        self.assertEqual(evaluate("max(3, 1, 2)"), 3)
        self.assertEqual(evaluate("min(2, 1.5)"), 1.5)
        self.assertEqual(evaluate('max("a", "c", "b")'), "c")
        self.assertEqual(evaluate("min(7)"), 7)

    def test_min_and_max_accept_a_single_list(self) -> None:
        self.assertEqual(evaluate("min([3, 1, 2])"), 1)
        self.assertEqual(evaluate("max([3, 1, 2])"), 3)
        error = self.eval_error("min([])")
        self.assertIn("min needs at least one value", error.message)
        self.assertIn("empty", error.why)

    def test_min_and_max_reject_mixed_or_unorderable_types(self) -> None:
        error = self.eval_error('min(1, "a")')
        self.assertIn("cannot compare int and string", error.message)
        self.assertIn("same kind", error.fix)
        self.assertIn("cannot compare bool with max", self.eval_error("max(true)").message)

    def test_min_and_max_need_at_least_one_argument(self) -> None:
        self.assertIn("min expects at least 1 argument, got 0",
                      self.eval_error("min()").message)
        self.assertIn("max expects at least 1 argument, got 0",
                      self.eval_error("max()").message)

    # abs

    def test_abs_returns_the_magnitude(self) -> None:
        self.assertEqual(evaluate("abs(-3)"), 3)
        self.assertEqual(evaluate("abs(3)"), 3)
        self.assertEqual(evaluate("abs(-2.5)"), 2.5)

    def test_abs_rejects_non_numbers(self) -> None:
        error = self.eval_error('abs("x")')
        self.assertIn("cannot take the absolute value of string", error.message)
        self.assertIn("abs needs a number", error.why)

    # discovery

    def test_a_misspelled_builtin_is_suggested(self) -> None:
        error = self.eval_error("lenn([1])")
        self.assertIn("did you mean 'len'", error.fix)


if __name__ == "__main__":
    unittest.main()
