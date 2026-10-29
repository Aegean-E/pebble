"""Text helpers: split, join, trim and replace, with their arity and type guards."""

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
    """Call one builtin directly, for guards that plain source reaches only with big text."""
    return BUILTINS[name].impl(None, BUILTIN_CALL, list(args))


class TextHelperTests(unittest.TestCase):
    """One behaviour per test; messages, positions and return values are asserted."""

    def eval_error(self, source: str) -> EvalError:
        """The EvalError `source` raises."""
        with self.assertRaises(EvalError) as caught:
            evaluate(source)
        return caught.exception

    # split

    def test_split_without_a_separator_splits_on_whitespace_runs(self) -> None:
        self.assertEqual(evaluate('split("a b  c")'), ["a", "b", "c"])
        self.assertEqual(evaluate('split("  a\\tb\\nc  ")'), ["a", "b", "c"])
        self.assertEqual(evaluate('split("   ")'), [])
        self.assertEqual(evaluate('split("")'), [])

    def test_split_with_a_separator_keeps_empty_fields(self) -> None:
        self.assertEqual(evaluate('split("a,b", ",")'), ["a", "b"])
        self.assertEqual(evaluate('split("a,,b", ",")'), ["a", "", "b"])
        self.assertEqual(evaluate('split(",a,", ",")'), ["", "a", ""])
        self.assertEqual(evaluate('split("abc", ",")'), ["abc"])
        self.assertEqual(evaluate('split("", ",")'), [""])
        self.assertEqual(evaluate('split("a b c", " ")'), ["a", "b", "c"])

    def test_split_rejects_a_non_string_or_an_empty_separator(self) -> None:
        error = self.eval_error("split(42)")
        self.assertIn("split needs a string, got int", error.message)
        self.assertIn("text", error.why)
        self.assertEqual((error.line, error.col), (1, 6))
        error = self.eval_error('split("a", "")')
        self.assertIn("split separator cannot be empty", error.message)
        self.assertIn("never advance", error.why)
        self.assertIn("split needs a string, got bool",
                      self.eval_error("split(true)").message)
        self.assertIn("split needs a string, got int",
                      self.eval_error('split("a", 1)').message)

    def test_a_split_result_is_capped_at_the_sequence_limit(self) -> None:
        with mock.patch("pebble.stdlib.MAX_SEQUENCE_LENGTH", 3):
            self.assertEqual(call_builtin("split", "a,b,c", ","), ["a", "b", "c"])
            with self.assertRaises(EvalError) as caught:
                call_builtin("split", "a,b,c,d", ",")
        self.assertIn("split would produce 4 pieces", caught.exception.message)
        self.assertIn("at most 3 values", caught.exception.why)
        self.assertIn("shorter piece of text", caught.exception.fix)

    def test_split_arity_is_one_to_two(self) -> None:
        self.assertIn("split expects 1 to 2 arguments, got 0",
                      self.eval_error("split()").message)
        self.assertIn("split expects 1 to 2 arguments, got 3",
                      self.eval_error('split("a", "b", "c")').message)

    # join

    def test_join_places_the_separator_between_strings(self) -> None:
        self.assertEqual(evaluate('join(["a", "b", "c"], ",")'), "a,b,c")
        self.assertEqual(evaluate('join(["a"], "-")'), "a")
        self.assertEqual(evaluate("join([], \"-\")"), "")
        self.assertEqual(evaluate('join(["", ""], ",")'), ",")
        self.assertEqual(evaluate('join(["a\\nb", "c"], "")'), "a\nb" + "c")

    def test_join_needs_a_list_of_strings_and_a_string_separator(self) -> None:
        error = self.eval_error("join(\"abc\", \",\")")
        self.assertIn("join needs a list, got string", error.message)
        self.assertIn("values", error.why)
        self.assertEqual((error.line, error.col), (1, 5))
        self.assertIn("join needs a list, got int", self.eval_error("join(5, 6)").message)

    def test_join_refuses_a_non_string_element(self) -> None:
        error = self.eval_error('join(["a", 2], ",")')
        self.assertIn("join needs a list of strings", error.message)
        self.assertIn("separator must both be strings", error.why)
        self.assertIn("index 1", error.message)
        self.assertIn("join needs a list of strings", self.eval_error('join(["a", true], ",")').message)

    def test_join_refuses_a_non_string_separator(self) -> None:
        error = self.eval_error("join([], 1)")
        self.assertIn("join needs a string, got int", error.message)
        self.assertIn("separator must both be strings", error.why)

    def test_a_join_result_is_capped_at_the_sequence_limit(self) -> None:
        with mock.patch("pebble.stdlib.MAX_SEQUENCE_LENGTH", 5):
            self.assertEqual(call_builtin("join", ["a", "b"], ","), "a,b")
            with self.assertRaises(EvalError) as caught:
                call_builtin("join", ["abc", "de"], ",")
        self.assertIn("joining these strings is too large", caught.exception.message)
        self.assertIn("the result would have 6 characters", caught.exception.why)

    def test_join_arity_is_two(self) -> None:
        self.assertIn("join expects 2 arguments, got 1",
                      self.eval_error('join(["a"])').message)
        self.assertIn("join expects 2 arguments, got 3",
                      self.eval_error('join([], ",", "x")').message)

    # trim

    def test_trim_removes_whitespace_from_both_ends_only(self) -> None:
        self.assertEqual(evaluate('trim("  a b  ")'), "a b")
        self.assertEqual(evaluate('trim("\\t\\na\\r")'), "a")
        self.assertEqual(call_builtin("trim", "\f\v a \f\v"), "a")
        self.assertEqual(evaluate('trim("a\\tb")'), "a\tb")
        self.assertEqual(evaluate('trim("   ")'), "")
        self.assertEqual(evaluate('trim("")'), "")

    def test_trim_rejects_other_types(self) -> None:
        error = self.eval_error("trim(5)")
        self.assertIn("trim needs a string, got int", error.message)
        self.assertIn("both ends", error.why)
        self.assertEqual((error.line, error.col), (1, 5))
        self.assertIn("trim needs a string, got list",
                      self.eval_error("trim([])").message)

    def test_trim_arity_is_one(self) -> None:
        self.assertIn("trim expects 1 argument, got 0", self.eval_error("trim()").message)
        self.assertIn("trim expects 1 argument, got 2",
                      self.eval_error('trim("a", "b")').message)

    # replace

    def test_replace_rewrites_every_occurrence_left_to_right(self) -> None:
        self.assertEqual(evaluate('replace("a-b-c", "-", "+")'), "a+b+c")
        self.assertEqual(evaluate('replace("aaa", "aa", "b")'), "ba")
        self.assertEqual(evaluate('replace("a-b", "-", "")'), "ab")
        self.assertEqual(evaluate('replace("abc", "z", "y")'), "abc")
        self.assertEqual(evaluate('replace("", "a", "b")'), "")

    def test_replace_needs_three_strings_and_a_non_empty_search(self) -> None:
        error = self.eval_error("replace(1, \"a\", \"b\")")
        self.assertIn("replace needs a string, got int", error.message)
        self.assertIn("text, the search text and the replacement", error.why)
        self.assertEqual((error.line, error.col), (1, 8))
        self.assertIn("replace needs a string, got int",
                      self.eval_error('replace("a", 2, "b")').message)
        self.assertIn("replace needs a string, got bool",
                      self.eval_error('replace("a", "b", true)').message)
        error = self.eval_error('replace("abc", "", "x")')
        self.assertIn("replace search text cannot be empty", error.message)
        self.assertIn("between every character", error.why)

    def test_a_replace_result_is_capped_at_the_sequence_limit(self) -> None:
        with mock.patch("pebble.stdlib.MAX_SEQUENCE_LENGTH", 5):
            self.assertEqual(call_builtin("replace", "ab", "a", "X"), "Xb")
            with self.assertRaises(EvalError) as caught:
                call_builtin("replace", "abc", "a", "XYZW")
        self.assertIn("replacing this text is too large", caught.exception.message)
        self.assertIn("the result would have 6 characters", caught.exception.why)

    def test_replace_arity_is_three(self) -> None:
        self.assertIn("replace expects 3 arguments, got 2",
                      self.eval_error('replace("a", "b")').message)
        self.assertIn("replace expects 3 arguments, got 4",
                      self.eval_error('replace("a", "b", "c", "d")').message)
