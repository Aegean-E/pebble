"""Parser tests: AST shapes for precedence and statements, and every parse-error path."""

import unittest

from pebble import nodes
from pebble.errors import ParseError
from pebble.lexer import tokenize
from pebble.parser import parse


def render(node) -> str:
    """A compact parenthesised form of one AST node, for readable assertions."""
    if isinstance(node, nodes.Literal):
        return _literal(node.value)
    if isinstance(node, nodes.ListLiteral):
        return "[" + " ".join(render(element) for element in node.elements) + "]"
    if isinstance(node, nodes.Name):
        return node.identifier
    if isinstance(node, (nodes.Unary, nodes.Binary, nodes.Logical)):
        if isinstance(node, nodes.Unary):
            return f"({node.op} {render(node.operand)})"
        return f"({node.op} {render(node.left)} {render(node.right)})"
    if isinstance(node, nodes.Call):
        args = "".join(" " + render(arg) for arg in node.args)
        return f"(call {render(node.callee)}{args})"
    if isinstance(node, nodes.Index):
        return f"(index {render(node.target)} {render(node.index)})"
    if isinstance(node, nodes.Slice):
        return (f"(slice {render(node.target)} {_optional(node.start)} "
                f"{_optional(node.stop)} {_optional(node.step)})")
    if isinstance(node, nodes.Let):
        return f"(let {node.name} {render(node.value)})"
    if isinstance(node, nodes.Assign):
        return f"(set {node.name} {render(node.value)})"
    if isinstance(node, nodes.ExprStmt):
        return render(node.expr)
    if isinstance(node, nodes.IfStmt):
        return f"(if {render(node.condition)} {_body(node.then_body)} {_body(node.else_body)})"
    if isinstance(node, nodes.WhileStmt):
        return f"(while {render(node.condition)} {_body(node.body)})"
    if isinstance(node, nodes.ForStmt):
        return f"(for {node.name} {render(node.iterable)} {_body(node.body)})"
    if isinstance(node, nodes.FnStmt):
        return f"(fn {node.name} ({' '.join(node.params)}) {_body(node.body)})"
    if isinstance(node, nodes.ReturnStmt):
        return "(return)" if node.value is None else f"(return {render(node.value)})"
    if isinstance(node, nodes.BreakStmt):
        return "break"
    if isinstance(node, nodes.ContinueStmt):
        return "continue"
    raise AssertionError(f"unhandled node type: {type(node).__name__}")


def _literal(value) -> str:
    """How a literal renders in the sexpr form."""
    if value is None:
        return "none"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return repr(value)


def _optional(node) -> str:
    """A slice part that may be omitted renders as `_`."""
    return "_" if node is None else render(node)


def _body(statements: tuple) -> str:
    """A block renders as { statement statement }."""
    inner = " ".join(render(statement) for statement in statements)
    return "{ " + inner + " }" if inner else "{ }"


def render_all(source: str) -> list[str]:
    """Every statement of `source` in sexpr form."""
    return [render(statement) for statement in parse(tokenize(source))]


class ParserTests(unittest.TestCase):
    """AST shape and error position, one behaviour per test."""

    def parse_error(self, source: str) -> ParseError:
        """The ParseError `source` raises."""
        with self.assertRaises(ParseError) as caught:
            parse(tokenize(source))
        return caught.exception

    def test_empty_program(self) -> None:
        self.assertEqual(render_all(""), [])

    def test_multiplication_binds_tighter_than_addition(self) -> None:
        self.assertEqual(render_all("1 + 2 * 3"), ["(+ 1 (* 2 3))"])
        self.assertEqual(render_all("(1 + 2) * 3"), ["(* (+ 1 2) 3)"])

    def test_power_is_right_associative(self) -> None:
        self.assertEqual(render_all("2 ^ 3 ^ 2"), ["(^ 2 (^ 3 2))"])

    def test_unary_minus_binds_looser_than_power(self) -> None:
        self.assertEqual(render_all("-2 ^ 2"), ["(- (^ 2 2))"])

    def test_not_binds_looser_than_comparison(self) -> None:
        self.assertEqual(render_all("not a == b"), ["(not (== a b))"])

    def test_or_binds_looser_than_and(self) -> None:
        self.assertEqual(render_all("a or b and c"), ["(or a (and b c))"])

    def test_comparison_chains_are_rejected(self) -> None:
        error = self.parse_error("1 < 2 < 3")
        self.assertIn("chained", error.message)
        self.assertEqual((error.line, error.col), (1, 7))

    def test_let_and_assignment(self) -> None:
        self.assertEqual(render_all("let x = 1\nx = x + 1"),
                         ["(let x 1)", "(set x (+ x 1))"])

    def test_list_literals_and_indexing(self) -> None:
        self.assertEqual(render_all("[1, 2][0] + 3"), ["(+ (index [1 2] 0) 3)"])

    def test_calls_chain(self) -> None:
        self.assertEqual(render_all("f(1)(2)[3]"), ["(index (call (call f 1) 2) 3)"])

    def test_slices_parse_with_omitted_parts(self) -> None:
        self.assertEqual(render_all("xs[:]"), ["(slice xs _ _ _)"])
        self.assertEqual(render_all("xs[1:]"), ["(slice xs 1 _ _)"])
        self.assertEqual(render_all("xs[:2]"), ["(slice xs _ 2 _)"])
        self.assertEqual(render_all("xs[1:2]"), ["(slice xs 1 2 _)"])
        self.assertEqual(render_all("xs[1:2:3]"), ["(slice xs 1 2 3)"])
        self.assertEqual(render_all("xs[::2]"), ["(slice xs _ _ 2)"])
        self.assertEqual(render_all("xs[1::2]"), ["(slice xs 1 _ 2)"])

    def test_a_subscript_without_a_colon_stays_an_index(self) -> None:
        self.assertEqual(render_all("xs[1]"), ["(index xs 1)"])
        self.assertEqual(render_all("xs[1:2][0]"), ["(index (slice xs 1 2 _) 0)"])

    def test_a_slice_has_at_most_three_parts(self) -> None:
        error = self.parse_error("xs[1:2:3:4]")
        self.assertIn("at most three", error.fix)
        self.assertEqual((error.line, error.col), (1, 9))

    def test_if_else_and_else_if(self) -> None:
        self.assertEqual(render_all("if a { 1 } else if b { 2 } else { 3 }"),
                         ["(if a { 1 } { (if b { 2 } { 3 }) })"])

    def test_if_without_else(self) -> None:
        self.assertEqual(render_all("if a { 1 }"), ["(if a { 1 } { })"])

    def test_while_loop(self) -> None:
        self.assertEqual(render_all("while x < 3 { x = x + 1 }"),
                         ["(while (< x 3) { (set x (+ x 1)) })"])

    def test_for_in_loop(self) -> None:
        self.assertEqual(render_all('for c in "ab" { c }'), ["(for c 'ab' { c })"])

    def test_break_and_continue_inside_loops(self) -> None:
        self.assertEqual(render_all("while true { break }"), ["(while true { break })"])
        self.assertEqual(render_all("for x in [1] { continue }"), ["(for x [1] { continue })"])
        self.assertEqual(render_all("while true { if a { break } else { continue } }"),
                         ["(while true { (if a { break } { continue }) })"])

    def test_break_and_continue_outside_a_loop_are_rejected(self) -> None:
        error = self.parse_error("break")
        self.assertIn("break outside a loop", error.message)
        self.assertEqual((error.line, error.col), (1, 1))
        error = self.parse_error("if true { continue }")
        self.assertIn("continue outside a loop", error.message)
        self.assertEqual((error.line, error.col), (1, 11))

    def test_a_function_body_is_not_inside_the_enclosing_loop(self) -> None:
        error = self.parse_error("while true { fn f() { break } }")
        self.assertIn("break outside a loop", error.message)

    def test_break_in_a_nested_loop_is_allowed(self) -> None:
        self.assertEqual(render_all("while a { for x in xs { break } }"),
                         ["(while a { (for x xs { break }) })"])

    def test_function_definition_and_return(self) -> None:
        self.assertEqual(render_all("fn add(a, b) { return a + b }"),
                         ["(fn add (a b) { (return (+ a b)) })"])

    def test_bare_return_renders_without_a_value(self) -> None:
        self.assertEqual(render_all("fn f() { return }"), ["(fn f () { (return) })"])

    def test_statements_need_no_separator(self) -> None:
        self.assertEqual(render_all("let a = 1 let b = 2 a + b"),
                         ["(let a 1)", "(let b 2)", "(+ a b)"])

    def test_equality_is_not_assignment(self) -> None:
        self.assertEqual(render_all("x == 1"), ["(== x 1)"])

    def test_missing_close_group_at_eof_marks_at_eof(self) -> None:
        error = self.parse_error("let x = (1 + 2")
        self.assertEqual(error.line, 1)
        self.assertTrue(error.at_eof)

    def test_unexpected_token_inside_a_block_is_not_at_eof(self) -> None:
        error = self.parse_error("if a { 1 ]")
        self.assertIn("']'", error.message)
        self.assertFalse(error.at_eof)

    def test_let_without_equals(self) -> None:
        error = self.parse_error("let x 1")
        self.assertIn("expected '='", error.message)

    def test_stray_else_is_reported(self) -> None:
        error = self.parse_error("else { 1 }")
        self.assertIn("else", error.message)
        self.assertIn("cannot start a statement", error.message)

    def test_duplicate_parameter_is_rejected(self) -> None:
        error = self.parse_error("fn f(a, a) { a }")
        self.assertIn("duplicate parameter", error.message)

    def test_trailing_comma_gets_a_hint(self) -> None:
        error = self.parse_error("[1, 2,]")
        self.assertIn("comma", error.fix)

    def test_eof_inside_a_call_marks_at_eof(self) -> None:
        error = self.parse_error("fn f(")
        self.assertTrue(error.at_eof)

    def test_if_requires_braces(self) -> None:
        error = self.parse_error("if a 1 else 2")
        self.assertIn("expected '{'", error.message)

    def test_deeply_nested_expression_is_a_parse_error_not_a_crash(self) -> None:
        error = self.parse_error("(" * 300 + "1" + ")" * 300)
        self.assertIn("nests too deeply", error.message)
        self.assertIn("let", error.fix)


if __name__ == "__main__":
    unittest.main()
