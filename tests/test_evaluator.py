"""Evaluator tests: semantics, scoping, control flow, functions and runtime errors."""

import unittest
from io import StringIO

from pebble.errors import EvalError
from pebble.evaluator import Interpreter
from pebble.lexer import tokenize
from pebble.parser import parse

FIBONACCI = (
    "fn fib(n) { if n < 2 { return n } return fib(n - 1) + fib(n - 2) }\n"
    "fib(10)"
)


def run(source: str, out=None):
    """Evaluate `source` with a fresh interpreter; the last statement's value comes back."""
    if out is None:
        out = StringIO()
    return Interpreter(out=out).run(parse(tokenize(source)))


class EvaluatorTests(unittest.TestCase):
    """One behaviour per test; messages, positions and types are asserted, not just raised."""

    def eval_error(self, source: str) -> EvalError:
        """The EvalError `source` raises."""
        with self.assertRaises(EvalError) as caught:
            run(source)
        return caught.exception

    # values and operators

    def test_arithmetic_evaluates_with_precedence(self) -> None:
        self.assertEqual(run("2 + 3 * 4"), 14)
        self.assertIs(type(run("2 + 3 * 4")), int)

    def test_power_is_right_associative_and_unary_minus_applies_after(self) -> None:
        self.assertEqual(run("2 ^ 3 ^ 2"), 512)
        self.assertEqual(run("-2 ^ 2"), -4)

    def test_division_always_produces_a_float(self) -> None:
        self.assertEqual(run("6 / 3"), 2.0)
        self.assertIs(type(run("6 / 3")), float)

    def test_remainder_follows_the_divisor_sign(self) -> None:
        self.assertEqual(run("-7 % 3"), 2)
        self.assertEqual(run("7 % -3"), -2)

    def test_float_arithmetic(self) -> None:
        self.assertEqual(run("1.5 + 1.5"), 3.0)
        self.assertEqual(run("2.5 * 2"), 5.0)

    def test_string_concatenation_and_repetition(self) -> None:
        self.assertEqual(run('"ab" + "cd"'), "abcd")
        self.assertEqual(run('"ab" * 2'), "abab")
        self.assertEqual(run('2 * "ab"'), "abab")

    def test_list_concatenation_repetition_and_deep_equality(self) -> None:
        self.assertEqual(run("[1] + [2]"), [1, 2])
        self.assertEqual(run("[1, 2] * 2"), [1, 2, 1, 2])
        self.assertTrue(run("[1, [2]] == [1, [2]]"))
        self.assertFalse(run("[1] == [1, 2]"))

    def test_repeat_count_must_not_be_negative(self) -> None:
        error = self.eval_error('"ab" * -1')
        self.assertIn("cannot repeat a string -1 times", error.message)
        self.assertIn("zero or more", error.why)

    def test_division_by_zero_is_a_positioned_eval_error(self) -> None:
        error = self.eval_error("1 / 0")
        self.assertIn("division by zero", error.message)
        self.assertEqual((error.line, error.col), (1, 3))

    def test_remainder_by_zero_is_an_eval_error(self) -> None:
        error = self.eval_error("5 % 0")
        self.assertIn("remainder by zero", error.message)

    def test_type_errors_name_both_types(self) -> None:
        self.assertIn("cannot add int and string", self.eval_error('1 + "a"').message)
        self.assertIn("cannot add list and int", self.eval_error("[1] + 1").message)
        self.assertIn("cannot subtract int and string", self.eval_error('1 - "a"').message)
        self.assertIn("cannot negate string", self.eval_error('-"a"').message)

    def test_ordering_mixed_types_is_an_error(self) -> None:
        self.assertIn("cannot order int and string", self.eval_error('1 < "a"').message)
        self.assertIn("cannot order list and list", self.eval_error("[1] < [2]").message)

    def test_comparisons_work_on_strings(self) -> None:
        self.assertTrue(run('"a" < "b"'))
        self.assertFalse(run('"b" <= "a"'))

    def test_equality_across_types_is_false_not_an_error(self) -> None:
        self.assertFalse(run('1 == "1"'))
        self.assertFalse(run("1 == true"))
        self.assertFalse(run("none == false"))
        self.assertTrue(run("none == none"))

    def test_power_guards(self) -> None:
        self.assertIn("exponent 10001 is too large", self.eval_error("2 ^ 10001").message)
        self.assertIn("not a real number", self.eval_error("(-8) ^ 0.5").message)

    # logic and truthiness

    def test_logical_operators_short_circuit(self) -> None:
        self.assertIs(run("false and 1 / 0"), False)
        self.assertIs(run("true or 1 / 0"), True)
        self.assertEqual(run("false or 2"), 2)
        self.assertEqual(run("true and 3"), 3)
        self.assertEqual(run('none or "fallback"'), "fallback")

    def test_truthiness_rules(self) -> None:
        for falsy in ("0", "0.0", '""', "[]", "none", "false"):
            self.assertTrue(run(f"not {falsy}"), falsy)
        for truthy in ("1", "0.5", '"x"', "[0]", "true"):
            self.assertFalse(run(f"not {truthy}"), truthy)

    # statements, scoping, control flow

    def test_last_statement_value_is_returned(self) -> None:
        self.assertEqual(run("1\n2"), 2)
        self.assertIsNone(run("let x = 1"))

    def test_if_is_a_statement_and_produces_no_value(self) -> None:
        self.assertIsNone(run("if true { 1 }"))

    def test_if_else_runs_only_the_taken_branch(self) -> None:
        self.assertEqual(run("let x = 0\nif true { x = 1 } else { x = 2 }\nx"), 1)
        self.assertEqual(run("let x = 0\nif false { x = 1 } else { x = 2 }\nx"), 2)

    def test_while_loop_accumulates(self) -> None:
        self.assertEqual(run("let i = 0\nlet total = 0\nwhile i < 5 { total = total + i\ni = i + 1 }\ntotal"), 10)

    def test_for_loop_walks_lists_and_strings(self) -> None:
        self.assertEqual(run("let s = 0\nfor n in [1, 2, 3] { s = s + n }\ns"), 6)
        self.assertEqual(run('let out = ""\nfor c in "abc" { out = out + c }\nout'), "abc")

    def test_for_over_a_number_is_an_error(self) -> None:
        error = self.eval_error("for x in 5 { x }")
        self.assertIn("cannot iterate over int", error.message)

    def test_let_and_assignment_scope_rules(self) -> None:
        self.assertEqual(run("let x = 1\nx = x + 1\nx"), 2)
        self.assertEqual(run("let x = 1\nlet x = 2\nx"), 2)
        self.assertIn("cannot assign to undeclared name 'x'", self.eval_error("x = 1").message)

    def test_unknown_name_suggests_a_close_declared_name(self) -> None:
        error = self.eval_error("let total = 1\ntotl")
        self.assertIn("unknown name 'totl'", error.message)
        self.assertIn("did you mean 'total'", error.fix)

    def test_unknown_name_without_a_close_match_offers_declaration(self) -> None:
        error = self.eval_error("zzz")
        self.assertIn("declare it first with let zzz = ...", error.fix)

    def test_position_on_a_type_error_points_at_the_operator(self) -> None:
        error = self.eval_error('let a = 1\na + "x"')
        self.assertEqual((error.line, error.col), (2, 3))

    # functions

    def test_recursion_works(self) -> None:
        self.assertEqual(run(FIBONACCI), 55)

    def test_function_without_a_return_produces_none(self) -> None:
        self.assertIsNone(run("fn nothing() { }\nnothing()"))

    def test_return_unwinds_nested_blocks(self) -> None:
        self.assertEqual(run("fn f() { while true { return 7 } }\nf()"), 7)

    def test_return_outside_a_function_is_an_error(self) -> None:
        error = self.eval_error("return 1")
        self.assertIn("return outside a function", error.message)

    def test_arity_mismatch_names_the_function(self) -> None:
        self.assertIn("f expects 2 arguments, got 1", self.eval_error("fn f(a, b) { a }\nf(1)").message)
        self.assertIn("g expects 1 argument, got 2", self.eval_error("fn g(a) { a }\ng(1, 2)").message)

    def test_arguments_are_evaluated_in_the_callers_scope(self) -> None:
        self.assertEqual(run("fn double(x) { return x * 2 }\nlet n = 4\ndouble(n)"), 8)

    def test_calling_a_non_function_is_an_error(self) -> None:
        error = self.eval_error("let x = 3\nx(1)")
        self.assertIn("cannot call int", error.message)

    def test_recursion_depth_limit_is_a_pebble_error(self) -> None:
        error = self.eval_error("fn f() { return f() }\nf()")
        self.assertIn("call stack too deep", error.message)
        self.assertIn("base case", error.fix)

    def test_nested_functions_are_refused(self) -> None:
        error = self.eval_error("fn outer() { fn inner() { return 1 }\nreturn 1 }\nouter()")
        self.assertIn("functions cannot be defined inside functions", error.message)

    # indexing

    def test_indexing_lists_and_strings_with_negative_offsets(self) -> None:
        self.assertEqual(run("[10, 20, 30][1]"), 20)
        self.assertEqual(run("[1, 2, 3][-1]"), 3)
        self.assertEqual(run('"abc"[1]'), "b")
        self.assertEqual(run('"abc"[-1]'), "c")

    def test_index_out_of_range_shows_the_length(self) -> None:
        error = self.eval_error("[1, 2][5]")
        self.assertIn("index 5 is out of range", error.message)
        self.assertIn("2 elements", error.why)
        self.assertIn("3 elements", self.eval_error('"abc"[9]').why)
        self.assertIn("empty", self.eval_error("[][0]").why)

    def test_index_must_be_an_integer_and_a_sequence(self) -> None:
        self.assertIn("cannot index with string", self.eval_error('"abc"["1"]').message)
        self.assertIn("cannot index int", self.eval_error("5[0]").message)

    def test_a_very_deep_expression_chain_is_a_pebble_error(self) -> None:
        error = self.eval_error("1" + " + 1" * 20000)
        self.assertIn("nests too deeply", error.message)


if __name__ == "__main__":
    unittest.main()
