"""Lexer tests: token streams, positions, and every lex-error path (PRINCIPLE-014 R2)."""

import unittest

from pebble.errors import LexError
from pebble.lexer import Token, tokenize


def pairs(source: str) -> list[tuple[str, object]]:
    """Every (kind, value) in `source`, the trailing EOF token excluded."""
    return [(token.kind, token.value) for token in tokenize(source)[:-1]]


class LexerTests(unittest.TestCase):
    """One behaviour per test; every failure message is asserted, not just raised."""

    def lex_error(self, source: str) -> LexError:
        """The LexError `source` raises."""
        with self.assertRaises(LexError) as caught:
            tokenize(source)
        return caught.exception

    def test_empty_source_yields_a_single_eof_token(self) -> None:
        self.assertEqual(tokenize(""), [Token("EOF", None, 1, 1)])

    def test_eof_token_marks_the_end_position(self) -> None:
        self.assertEqual(tokenize("42")[-1], Token("EOF", None, 1, 3))

    def test_integers_and_floats_keep_their_types(self) -> None:
        values = [value for _, value in pairs("42 3.5 0 10.25")]
        self.assertEqual(values, [42, 3.5, 0, 10.25])
        self.assertIs(type(values[0]), int)
        self.assertIs(type(values[1]), float)
        self.assertIs(type(values[2]), int)
        self.assertIs(type(values[3]), float)

    def test_leading_dot_is_rejected(self) -> None:
        error = self.lex_error(".5")
        self.assertIn("'.'", error.message)
        self.assertEqual((error.line, error.col), (1, 1))

    def test_trailing_dot_is_rejected_with_a_float_hint(self) -> None:
        error = self.lex_error("1.")
        self.assertIn("digit", error.message)
        self.assertEqual((error.line, error.col), (1, 2))

    def test_number_followed_by_a_letter_is_rejected(self) -> None:
        error = self.lex_error("12abc")
        self.assertIn("letter", error.message)
        self.assertEqual((error.line, error.col), (1, 3))

    def test_strings_single_and_double_quotes(self) -> None:
        self.assertEqual(pairs("\"hi\" 'yo'"), [("STRING", "hi"), ("STRING", "yo")])

    def test_string_escapes(self) -> None:
        self.assertEqual(pairs('"a\\nb\\tc\\\\d\\"e"'), [("STRING", 'a\nb\tc\\d"e')])

    def test_unknown_escape_reports_its_position(self) -> None:
        error = self.lex_error('"a\\qb"')
        self.assertIn("unknown escape", error.message)
        self.assertIn("\\q", error.message)
        self.assertEqual((error.line, error.col), (1, 3))

    def test_unterminated_string_points_at_the_opening_quote(self) -> None:
        error = self.lex_error('x = "abc\ny = 1')
        self.assertIn("unterminated string", error.message)
        self.assertEqual((error.line, error.col), (1, 5))
        self.assertIn("close", error.fix)

    def test_unterminated_string_at_eof(self) -> None:
        error = self.lex_error('"abc')
        self.assertIn("unterminated string", error.message)
        self.assertEqual((error.line, error.col), (1, 1))

    def test_comments_run_to_the_end_of_the_line(self) -> None:
        self.assertEqual(pairs("# note\n42 # trailing\n# last"), [("NUMBER", 42)])
        self.assertEqual(tokenize("1 # x")[-1], Token("EOF", None, 1, 6))
        self.assertEqual(tokenize("# x")[-1], Token("EOF", None, 1, 4))

    def test_two_char_operators_lex_as_one_token(self) -> None:
        self.assertEqual(pairs("== != <= >= < ="),
                         [("OP", "=="), ("OP", "!="), ("OP", "<="), ("OP", ">="),
                          ("OP", "<"), ("OP", "=")])

    def test_keywords_and_names_are_distinguished(self) -> None:
        self.assertEqual(pairs("let letter _x true trueish"),
                         [("KEYWORD", "let"), ("NAME", "letter"), ("NAME", "_x"),
                          ("KEYWORD", "true"), ("NAME", "trueish")])

    def test_break_and_continue_are_keywords(self) -> None:
        self.assertEqual(pairs("break continue breaker"),
                         [("KEYWORD", "break"), ("KEYWORD", "continue"), ("NAME", "breaker")])

    def test_positions_track_lines_and_columns(self) -> None:
        tokens = tokenize("1\n 2")
        self.assertEqual(tokens[1], Token("NUMBER", 2, 2, 2))
        self.assertEqual(tokens[-1], Token("EOF", None, 2, 3))

    def test_crlf_sources_count_lines(self) -> None:
        tokens = tokenize("let a = 1\r\nif a")
        self.assertEqual(tokens[4], Token("KEYWORD", "if", 2, 1))
        self.assertEqual(tokens[5], Token("NAME", "a", 2, 4))

    def test_identifiers_are_ascii_only(self) -> None:
        error = self.lex_error("\u00e9 = 1")
        self.assertIn("unexpected character", error.message)
        self.assertIn("ASCII", error.fix)

    def test_semicolon_gets_a_separator_hint(self) -> None:
        error = self.lex_error("1;")
        self.assertIn("';'", error.message)
        self.assertIn("separator", error.fix)


if __name__ == "__main__":
    unittest.main()
