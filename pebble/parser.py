"""Pebble's recursive-descent parser: tokens in, AST out, positioned errors throughout.

The grammar, loosest binding first:

    program        := statement*
    statement      := let | assign | if | while | for | fn | return | expression
    expression     := or
    or             := and ("or" and)*
    and            := not ("and" not)*
    not            := "not" not | comparison
    comparison     := additive (comparison additive)?     -- chains are refused
    additive       := multiplicative (("+" | "-") multiplicative)*
    multiplicative := unary (("*" | "/" | "%") unary)*
    unary          := "-" unary | power
    power          := postfix ("^" unary)?                -- right-associative
    postfix        := primary ("(" arguments ")" | "[" expression "]")*
    primary        := NUMBER | STRING | "true" | "false" | "none" | NAME | list | "(" expression ")"
"""

from typing import NoReturn, Optional

from . import nodes
from .errors import ParseError
from .lexer import Token

COMPARISON_OPERATORS = frozenset({"==", "!=", "<", "<=", ">", ">="})


class _Parser:
    """One parse of one token stream; every error carries the offending token's position."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.position = 0

    def parse_program(self) -> tuple:
        """Every statement up to the EOF token."""
        statements = []
        while not self.check("EOF"):
            statements.append(self.parse_statement())
        return tuple(statements)

    def parse_statement(self):
        """One statement: a keyword form, an assignment, or an expression statement."""
        token = self.peek()
        if token.kind == "KEYWORD":
            builders = {"let": self.parse_let, "if": self.parse_if, "while": self.parse_while,
                        "for": self.parse_for, "fn": self.parse_fn, "return": self.parse_return}
            builder = builders.get(token.value)
            if builder is not None:
                return builder()
            if token.value not in ("not", "true", "false", "none"):
                self.fail(token, f"keyword '{token.value}' cannot start a statement",
                          "this word is reserved and only fits inside a specific form",
                          "remove it, or write the statement that needs it")
        if token.kind == "NAME" and self._assignment_follows():
            name = self.advance()
            self.advance()
            value = self.parse_expression()
            return nodes.Assign(name.value, value, name.line, name.col)
        expression = self.parse_expression()
        return nodes.ExprStmt(expression, expression.line, expression.col)

    def _assignment_follows(self) -> bool:
        """Whether the token after the name at the cursor is a lone `=`."""
        following = self.tokens[self.position + 1]
        return following.kind == "OP" and following.value == "="

    def parse_let(self):
        """`let name = expression`."""
        keyword = self.advance()
        name = self.expect("NAME", "a name after 'let'", "write let x = ... to declare x")
        if not self.match("OP", "="):
            self.fail(self.peek(), "expected '=' after the name in let",
                      "a let statement names a variable and then gives it a value",
                      f"write let {name.value} = ... to give it a value")
        value = self.parse_expression()
        return nodes.Let(name.value, value, keyword.line, keyword.col)

    def parse_if(self):
        """`if condition { ... }` with an optional `else` block or `else if` chain."""
        keyword = self.advance()
        condition = self.parse_expression()
        then_body = self.parse_block()
        else_body: tuple = ()
        if self.match("KEYWORD", "else"):
            if self.check("KEYWORD", "if"):
                else_body = (self.parse_if(),)
            else:
                else_body = self.parse_block()
        return nodes.IfStmt(condition, then_body, else_body, keyword.line, keyword.col)

    def parse_while(self):
        """`while condition { ... }`."""
        keyword = self.advance()
        condition = self.parse_expression()
        body = self.parse_block()
        return nodes.WhileStmt(condition, body, keyword.line, keyword.col)

    def parse_for(self):
        """`for name in iterable { ... }`."""
        keyword = self.advance()
        name = self.expect("NAME", "a loop variable name after 'for'",
                           "write for item in items { ... }")
        if not self.match("KEYWORD", "in"):
            self.fail(self.peek(), "expected 'in' after the loop variable",
                      "a for loop reads: for item in collection { ... }",
                      "add 'in' before the collection")
        iterable = self.parse_expression()
        body = self.parse_block()
        return nodes.ForStmt(name.value, iterable, body, keyword.line, keyword.col)

    def parse_fn(self):
        """`fn name(parameters) { ... }`."""
        keyword = self.advance()
        name = self.expect("NAME", "a function name after 'fn'", "write fn name(a, b) { ... }")
        if not self.match("OP", "("):
            self.fail(self.peek(), "expected '(' after the function name",
                      "a function declares its parameters in parentheses",
                      "add () after the name, even when there are no parameters")
        params: list[str] = []
        if not self.check("OP", ")"):
            while True:
                param = self.expect("NAME", "a parameter name",
                                    "parameters are names separated by commas")
                if param.value in params:
                    self.fail(param, f"duplicate parameter '{param.value}'",
                              "the same name would be bound twice in one call",
                              "rename one of the two parameters")
                params.append(param.value)
                if not self.match("OP", ","):
                    break
        self.expect("OP", "')' after the parameters", "close the parameter list with a )",
                    value=")")
        body = self.parse_block()
        return nodes.FnStmt(name.value, tuple(params), body, keyword.line, keyword.col)

    def parse_return(self):
        """`return` or `return expression`; a bare return is valid at a block end or EOF."""
        keyword = self.advance()
        if self.check("OP", "}") or self.check("EOF"):
            return nodes.ReturnStmt(None, keyword.line, keyword.col)
        value = self.parse_expression()
        return nodes.ReturnStmt(value, keyword.line, keyword.col)

    def parse_block(self) -> tuple:
        """A braced statement list; a missing brace at EOF is what the REPL waits on."""
        if not self.match("OP", "{"):
            self.fail(self.peek(), "expected '{' to open a block",
                      "if, while, for and fn bodies live inside braces",
                      "add { after the condition or signature")
        statements = []
        while not self.check("OP", "}") and not self.check("EOF"):
            statements.append(self.parse_statement())
        self.expect("OP", "'}' to close the block", "add the missing closing brace", value="}")
        return tuple(statements)

    # expressions

    def parse_expression(self):
        """The loosest expression level: `or`."""
        return self.parse_or()

    def parse_or(self):
        """`a or b and c` parses as `a or (b and c)`."""
        left = self.parse_and()
        while self.match("KEYWORD", "or"):
            operator = self.previous()
            right = self.parse_and()
            left = nodes.Logical("or", left, right, operator.line, operator.col)
        return left

    def parse_and(self):
        """`and` binds tighter than `or`, looser than `not`."""
        left = self.parse_not()
        while self.match("KEYWORD", "and"):
            operator = self.previous()
            right = self.parse_not()
            left = nodes.Logical("and", left, right, operator.line, operator.col)
        return left

    def parse_not(self):
        """`not` binds looser than comparison, so `not a == b` tests `a == b`."""
        if self.match("KEYWORD", "not"):
            operator = self.previous()
            operand = self.parse_not()
            return nodes.Unary("not", operand, operator.line, operator.col)
        return self.parse_comparison()

    def parse_comparison(self):
        """One comparison, never a chain; `a < b < c` is refused with advice."""
        left = self.parse_additive()
        if self.check("OP") and self.peek().value in COMPARISON_OPERATORS:
            operator = self.advance()
            right = self.parse_additive()
            if self.check("OP") and self.peek().value in COMPARISON_OPERATORS:
                self.fail(self.peek(), "chained comparisons are not allowed",
                          "a < b < c reads ambiguously in Pebble",
                          "combine two tests with 'and': a < b and b < c")
            return nodes.Binary(operator.value, left, right, operator.line, operator.col)
        return left

    def parse_additive(self):
        """`+` and `-`, left-associative."""
        left = self.parse_multiplicative()
        while self.check("OP") and self.peek().value in ("+", "-"):
            operator = self.advance()
            right = self.parse_multiplicative()
            left = nodes.Binary(operator.value, left, right, operator.line, operator.col)
        return left

    def parse_multiplicative(self):
        """`*`, `/` and `%`, left-associative."""
        left = self.parse_unary()
        while self.check("OP") and self.peek().value in ("*", "/", "%"):
            operator = self.advance()
            right = self.parse_unary()
            left = nodes.Binary(operator.value, left, right, operator.line, operator.col)
        return left

    def parse_unary(self):
        """A single unary minus; `--x` via recursion, `-2 ^ 2` reads as `-(2 ^ 2)`."""
        if self.match("OP", "-"):
            operator = self.previous()
            operand = self.parse_unary()
            return nodes.Unary("-", operand, operator.line, operator.col)
        return self.parse_power()

    def parse_power(self):
        """`^`, right-associative: `2 ^ 3 ^ 2` is `2 ^ (3 ^ 2)`."""
        left = self.parse_postfix()
        if self.match("OP", "^"):
            operator = self.previous()
            right = self.parse_unary()
            return nodes.Binary("^", left, right, operator.line, operator.col)
        return left

    def parse_postfix(self):
        """Calls and indexing chain left-to-right: `f(1)(2)[3]`."""
        expression = self.parse_primary()
        while True:
            if self.match("OP", "("):
                opening = self.previous()
                args: list = []
                if not self.check("OP", ")"):
                    while True:
                        args.append(self.parse_expression())
                        if not self.match("OP", ","):
                            break
                self.expect("OP", "')' to close the call", "close the call with a )",
                            value=")")
                expression = nodes.Call(expression, tuple(args), opening.line, opening.col)
            elif self.match("OP", "["):
                opening = self.previous()
                index = self.parse_expression()
                self.expect("OP", "']' to close the index", "close the index with a ]",
                            value="]")
                expression = nodes.Index(expression, index, opening.line, opening.col)
            else:
                return expression

    def parse_primary(self):
        """Literals, names, calls' heads, groups and list constructors."""
        token = self.peek()
        if token.kind in ("NUMBER", "STRING"):
            self.advance()
            return nodes.Literal(token.value, token.line, token.col)
        if token.kind == "KEYWORD":
            literals = {"true": True, "false": False, "none": None}
            if token.value in literals:
                self.advance()
                return nodes.Literal(literals[token.value], token.line, token.col)
        if token.kind == "NAME":
            self.advance()
            return nodes.Name(token.value, token.line, token.col)
        if self.match("OP", "("):
            expression = self.parse_expression()
            self.expect("OP", "')' to close the group", "close the group with a )", value=")")
            return expression
        if self.match("OP", "["):
            opening = self.previous()
            elements: list = []
            if not self.check("OP", "]"):
                while True:
                    elements.append(self.parse_expression())
                    if not self.match("OP", ","):
                        break
            self.expect("OP", "']' to close the list", "close the list with a ]", value="]")
            return nodes.ListLiteral(tuple(elements), opening.line, opening.col)
        found = "the end of the input" if token.kind == "EOF" else f"'{token.value}'"
        fix = "start with a number, string, name, list or parenthesised expression"
        if token.kind == "OP" and token.value in (")", "]", "}"):
            fix = "remove the trailing comma, or add the missing element"
        self.fail(token, f"expected an expression, found {found}",
                  "this position needs a value, a name or a call", fix)

    # token plumbing

    def peek(self) -> Token:
        """The token at the cursor without consuming it."""
        return self.tokens[self.position]

    def previous(self) -> Token:
        """The most recently consumed token."""
        return self.tokens[self.position - 1]

    def advance(self) -> Token:
        """The token at the cursor, moving past it (EOF never moves)."""
        token = self.tokens[self.position]
        if token.kind != "EOF":
            self.position += 1
        return token

    def check(self, kind: str, value: Optional[str] = None) -> bool:
        """Whether the token at the cursor has this kind (and value)."""
        token = self.peek()
        return token.kind == kind and (value is None or token.value == value)

    def match(self, kind: str, value: Optional[str] = None) -> bool:
        """Consume the token at the cursor when it has this kind (and value)."""
        if self.check(kind, value):
            self.advance()
            return True
        return False

    def expect(self, kind: str, what: str, fix: str, value: Optional[str] = None) -> Token:
        """Consume the expected token, or report its absence at the offending token."""
        if self.check(kind, value):
            return self.advance()
        token = self.peek()
        found = "the end of the input" if token.kind == "EOF" else f"'{token.value}'"
        self.fail(token, f"expected {what}, found {found}",
                  f"this position needs {what} before parsing can continue", fix)

    def fail(self, token: Token, message: str, why: str, fix: str) -> NoReturn:
        """Raise the positioned ParseError; `at_eof` tells the REPL to keep reading."""
        raise ParseError(message, token.line, token.col, why, fix, at_eof=token.kind == "EOF")


def parse(tokens: list[Token]) -> tuple:
    """The program the tokens describe; failures are ParseErrors with a position and a fix."""
    parser = _Parser(tokens)
    try:
        return parser.parse_program()
    except RecursionError:
        token = parser.peek()
        raise ParseError("the expression nests too deeply to parse", token.line, token.col,
                         "each bracket and unary operator is one more level for the parser to descend",
                         "split the expression into steps with let, or remove a layer of "
                         "nesting") from None
