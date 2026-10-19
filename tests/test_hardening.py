"""Hardening tests: error-format contract, resource guards, platform parity and performance."""

import unittest
from io import StringIO
from time import perf_counter
from unittest.mock import patch

from pebble.cli import main
from pebble.errors import EvalError, LexError, ParseError, PebbleError, format_error
from pebble.evaluator import Interpreter
from pebble.lexer import tokenize
from pebble.parser import parse

HUGE_LITERAL = "9" * 5000
HUGE_STRING = "9" * 5000

LEX_ERRORS = (
    "@",
    '"abc',
    "1x",
    '"a\\q"',
    HUGE_LITERAL,
)

PARSE_ERRORS = (
    "let = 1",
    "if true {",
    "1 +",
    "fn f( {",
    "while { }",
    "break",
    "xs[1:2:3:4]",
)

RUNTIME_ERRORS = (
    "zzz",
    "1 / 0",
    '1 + "a"',
    "len(1)",
    "return 1",
    "x = 1",
    "fn f(a) { a }\nf()",
    "5[0]",
    "min()",
    "range(1.5)",
    "int(true)",
    "0 ^ -1",
    "(10 ^ 400) / 1",
    "10 ^ 10000",
    "[1][0:2:0]",
    '"abc"[1.5:]',
    "range(0, 5, 0)",
    'float("x")',
    "args()",
)


def evaluate(source: str, out=None):
    """Evaluate `source` with a fresh interpreter; the last statement's value comes back."""
    return Interpreter(out=out if out is not None else StringIO()).run(parse(tokenize(source)))


def run_cli(argv, stdin_text: str = ""):
    """Run main() over in-memory streams; returns (exit code, stdout, stderr)."""
    stdout, stderr = StringIO(), StringIO()
    code = main(argv, stdin=StringIO(stdin_text), stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


class ErrorFormatTests(unittest.TestCase):
    """Every error kind carries a position, a reason and a fix, and renders as three lines."""

    def assert_reported(self, source: str, expected: type) -> None:
        with self.assertRaises(expected) as caught:
            evaluate(source)
        error = caught.exception
        self.assertTrue(error.message, source)
        self.assertTrue(error.why, source)
        self.assertTrue(error.fix, source)
        self.assertGreaterEqual(error.line, 1, source)
        self.assertGreaterEqual(error.col, 1, source)
        self.assertNotIn("\n", error.why, source)
        self.assertNotIn("\n", error.fix, source)
        rendered = format_error(error, "test.peb")
        self.assertRegex(rendered, r"^test\.peb:\d+:\d+: error: .+\n  Why: .+\n  Fix: .+$")
        code, out, err = run_cli(["-e", source])
        self.assertEqual((code, out), (1, ""), source)
        self.assertNotIn("Traceback", err, source)
        self.assertEqual(err.strip(), format_error(error, "<command>"))

    def test_every_lexer_error_path_is_formatted(self) -> None:
        for source in LEX_ERRORS:
            with self.subTest(source=source[:40]):
                self.assert_reported(source, LexError)

    def test_every_parser_error_path_is_formatted(self) -> None:
        for source in PARSE_ERRORS:
            with self.subTest(source=source):
                self.assert_reported(source, ParseError)

    def test_every_runtime_error_path_is_formatted(self) -> None:
        for source in RUNTIME_ERRORS:
            with self.subTest(source=source):
                self.assert_reported(source, EvalError)

    def test_an_unexpected_interpreter_failure_never_leaks_a_traceback(self) -> None:
        with patch.object(Interpreter, "run", side_effect=RuntimeError("boom")):
            code, out, err = run_cli(["-e", "1"])
        self.assertEqual((code, out), (1, ""))
        self.assertIn("internal error", err)
        self.assertIn("RuntimeError: boom", err)
        self.assertIn("Why:", err)
        self.assertIn("Fix:", err)
        self.assertNotIn("Traceback", err)


class ResourceGuardTests(unittest.TestCase):
    """Hostile or accidental programs fail as positioned Pebble errors, not host exceptions."""

    def eval_error(self, source: str) -> EvalError:
        with self.assertRaises(EvalError) as caught:
            evaluate(source)
        return caught.exception

    def lex_error(self, source: str) -> LexError:
        with self.assertRaises(LexError) as caught:
            tokenize(source)
        return caught.exception

    def test_zero_to_a_negative_power_is_refused(self) -> None:
        error = self.eval_error("0 ^ -1")
        self.assertIn("zero cannot be raised to a negative power", error.message)
        self.assertIn("no reciprocal", error.why)

    def test_a_division_result_too_large_for_a_float_is_refused(self) -> None:
        error = self.eval_error("(10 ^ 400) / 1")
        self.assertIn("the result is too large for a float", error.message)

    def test_an_int_result_over_the_digit_cap_is_refused(self) -> None:
        error = self.eval_error("10 ^ 10000")
        self.assertIn("integer result is too large", error.message)
        self.assertIn("integer result is too large", self.eval_error("(10 ^ 3999) * (10 ^ 3999)").message)

    def test_a_power_within_the_cap_still_works(self) -> None:
        self.assertEqual(len(str(evaluate("2 ^ 10000"))), 3011)

    def test_an_oversized_integer_literal_is_a_lex_error(self) -> None:
        error = self.lex_error(HUGE_LITERAL)
        self.assertIn("integer literal is too large", error.message)
        self.assertIn("4000", error.why)
        self.assertEqual((error.line, error.col), (1, 1))

    def test_an_oversized_float_literal_is_a_lex_error(self) -> None:
        error = self.lex_error("9" * 400 + ".0")
        self.assertIn("float literal is too large", error.message)
        self.assertIn("largest float", error.why)

    def test_an_oversized_numeric_string_cannot_become_an_int(self) -> None:
        error = self.eval_error(f'int("{HUGE_STRING}")')
        self.assertIn("cannot convert a 5000-digit string to int", error.message)
        self.assertIn("4000", error.why)

    def test_range_length_is_capped(self) -> None:
        error = self.eval_error("range(1000001)")
        self.assertIn("range would produce 1000001 values", error.message)
        self.assertIn("1000000", error.why)
        self.assertIn("range would produce 2000000 values",
                      self.eval_error("range(0, 2000000)").message)

    def test_sequence_repetition_length_is_capped(self) -> None:
        error = self.eval_error('"x" * 1000001')
        self.assertIn("repeating a string 1000001 times is too large", error.message)
        self.assertIn("characters", error.why)
        error = self.eval_error("[1] * 1000001")
        self.assertIn("repeating a list 1000001 times is too large", error.message)
        self.assertIn("elements", error.why)


class PlatformTests(unittest.TestCase):
    """Positions and string lengths use characters and tolerate CRLF sources."""

    def test_crlf_source_keeps_line_and_column_positions(self) -> None:
        with self.assertRaises(EvalError) as caught:
            evaluate("let x = 1\r\n1 / 0")
        self.assertEqual((caught.exception.line, caught.exception.col), (2, 3))

    def test_unicode_strings_count_characters_not_bytes(self) -> None:
        self.assertEqual(evaluate('len("héllo")'), 5)
        self.assertEqual(evaluate('"héllo"[1]'), "é")

    def test_a_unicode_string_does_not_shift_a_later_error_position(self) -> None:
        with self.assertRaises(EvalError) as caught:
            evaluate('print("é")\n1 / 0')
        self.assertEqual((caught.exception.line, caught.exception.col), (2, 3))


class PerformanceTests(unittest.TestCase):
    """The tree walker and parser stay usable; the whole suite stays far under a second."""

    def test_a_50k_iteration_loop_finishes_quickly(self) -> None:
        source = ("let i = 0\nlet total = 0\n"
                  "while i < 50000 { total = total + i\ni = i + 1 }\ntotal")
        started = perf_counter()
        self.assertEqual(evaluate(source), 1_249_975_000)
        self.assertLess(perf_counter() - started, 2.0)

    def test_parsing_10k_statements_finishes_quickly(self) -> None:
        source = "\n".join(str(number) for number in range(10_000))
        started = perf_counter()
        self.assertEqual(len(parse(tokenize(source))), 10_000)
        self.assertLess(perf_counter() - started, 2.0)


if __name__ == "__main__":
    unittest.main()
