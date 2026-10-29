"""Deterministic crash fuzz: random and mutated source is a Pebble error, never a host crash.

ADR-001 and ADR-003 promise that a program's failure is always a positioned Pebble report. These
tests attack that promise with a fixed seed, so a failure is reproducible: generated token streams
and single-token mutations of every example must either run or raise PebbleError. Resource caps are
patched down so a hostile sample cannot allocate or loop for long.
"""

import random
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

from pebble.cli import main
from pebble.errors import PebbleError
from pebble.evaluator import Interpreter
from pebble.lexer import tokenize
from pebble.parser import parse

SEED = 20261029
GENERATED_SAMPLES = 150
MUTATED_PROGRAMS = 60
STRUCTURED_SAMPLES = 120
MINIMUM_SUCCESSES = 60
EXAMPLE_DIR = Path(__file__).resolve().parent.parent / "examples"

ALPHABET = (
    "let", "if", "else", "for", "in", "fn", "return", "break", "continue",
    "true", "false", "none", "not", "and", "or",
    "x", "y", "args", "len", "print", "sort", "sum", "split", "join", "range",
    "0", "1", "-", "9999", "1.5",
    '"a"', '"b,c"', '""', "[", "]", "]", "{", "}", "(", ")", ",", ":",
    "+", "-", "*", "/", "%", "^", "==", "<", ">=", "=", "#",
)


def bounded():
    """Patch every resource cap down, so a hostile sample stays cheap."""
    return (
        mock.patch.multiple("pebble.evaluator", MAX_CALL_DEPTH=8,
                            MAX_SEQUENCE_LENGTH=40, MAX_EXPONENT=12),
        mock.patch.multiple("pebble.stdlib", MAX_RANGE_LENGTH=40,
                            MAX_SEQUENCE_LENGTH=40, MAX_INT_DIGITS=40),
    )


RAN, REPORTED = "ran", "reported"


def outcome(source: str) -> str:
    """Run one program and classify it: `ran`, or `reported` as a Pebble error.

    Any exception other than a PebbleError is deliberately not caught here: it escapes to the
    test, which fails with the sample, because a host escape is exactly what this module hunts.
    """
    try:
        Interpreter(out=StringIO()).run(parse(tokenize(source)))
    except PebbleError:
        return REPORTED
    return RAN


def assert_no_host_escape(test: unittest.TestCase, source: str) -> str:
    """The outcome of one sample, with a leaked recursion reported against the sample text."""
    try:
        return outcome(source)
    except RecursionError:
        test.fail(f"sample leaked RecursionError: {source!r}")
    return RAN


NUMBERS = ("0", "1", "2", "7", "9999", "1.5", "-3", "10 ^ 3990")
TEXTS = ('"a"', '"b,c"', '""', '"banana"')
NUMBER_LISTS = ("[1, 2, 3]", "[]", "range(3)", "sort([3, 1])")
TEXT_LISTS = ('split("a b")', 'split("a,b", ",")', "[]")
ARITHMETIC = ("+", "-", "*", "%", "^")
COMPARISONS = ("<", ">", "==", ">=")


def number(rng: random.Random, depth: int) -> str:
    """A numeric expression, so the sample usually reaches the evaluator instead of the parser."""
    if depth <= 0:
        return rng.choice(NUMBERS)
    kind = rng.randrange(6)
    if kind == 0:
        return rng.choice(NUMBERS)
    if kind == 1:
        return f"{number(rng, depth - 1)} {rng.choice(ARITHMETIC)} {number(rng, depth - 1)}"
    if kind == 2:
        name = rng.choice(("int", "float", "floor", "abs", "round"))
        if name == "round" and rng.random() < 0.5:
            return f"round({number(rng, depth - 1)}, {rng.randint(0, 3)})"
        return f"{name}({number(rng, depth - 1)})"
    if kind == 3:
        return f"len({text(rng, depth - 1)})"
    if kind == 4:
        return f"sum({rng.choice(NUMBER_LISTS)})"
    return (f"{rng.choice(('min', 'max'))}({number(rng, depth - 1)}, "
            f"{number(rng, depth - 1)})")


def text(rng: random.Random, depth: int) -> str:
    """A string expression over the text builtins."""
    if depth <= 0:
        return rng.choice(TEXTS)
    kind = rng.randrange(5)
    if kind == 0:
        return rng.choice(TEXTS)
    if kind == 1:
        return f"{rng.choice(('upper', 'lower', 'trim'))}({text(rng, depth - 1)})"
    if kind == 2:
        return f"str({number(rng, depth - 1)})"
    if kind == 3:
        return f'replace({text(rng, depth - 1)}, "a", "b")'
    return f'join({rng.choice(TEXT_LISTS)}, "-")'


def boolean(rng: random.Random, depth: int) -> str:
    """A boolean expression, which the if and predicate branches consume."""
    kind = rng.randrange(5)
    if kind == 0:
        return f"{number(rng, depth)} {rng.choice(COMPARISONS)} {number(rng, depth)}"
    if kind == 1:
        return f'contains({text(rng, depth)}, "a")'
    if kind == 2:
        return f'starts_with({text(rng, depth)}, "a")'
    if kind == 3:
        return f'ends_with({text(rng, depth)}, "a")'
    if depth > 0:
        return f"not {boolean(rng, depth - 1)}"
    return "true"


def generated_source(rng: random.Random) -> str:
    """A short token soup; it is rarely a valid program, which is the point."""
    size = rng.randint(1, 12)
    return " ".join(rng.choice(ALPHABET) for _ in range(size))


def any_expression(rng: random.Random, depth: int) -> str:
    """One expression of any type, for print and for the loop source."""
    kind = rng.randrange(4)
    if kind == 0:
        return number(rng, depth)
    if kind == 1:
        return text(rng, depth)
    if kind == 2:
        return boolean(rng, depth)
    return rng.choice(NUMBER_LISTS + TEXT_LISTS)


def structured_program(rng: random.Random) -> str:
    """One to three plausible statements, which usually run instead of failing to parse."""
    statements = []
    for _ in range(rng.randint(1, 3)):
        kind = rng.randrange(6)
        if kind == 0:
            statements.append(f"let x = {number(rng, 2)}")
        elif kind == 1:
            statements.append(f"x = {number(rng, 1)}")
        elif kind == 2:
            statements.append(f"print({any_expression(rng, 2)})")
        elif kind == 3:
            first, second = any_expression(rng, 1), any_expression(rng, 1)
            statements.append(f"if {boolean(rng, 1)} {{ print({first}) }} else {{ print({second}) }}")
        elif kind == 4:
            statements.append(f"for x in {rng.choice(NUMBER_LISTS + TEXT_LISTS)} {{ print(x) }}")
        else:
            statements.append(f"print({number(rng, 2)})")
    return "\n".join(statements)


def example_sources():
    """Every tracked example program's text, so the corpus grows with the project."""
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(EXAMPLE_DIR.glob("*.peb"))}


def mutated_source(rng: random.Random, source: str) -> str:
    """One token replaced, dropped or duplicated in a real program."""
    words = source.split(" ")
    if not words:
        return source
    index = rng.randrange(len(words))
    action = rng.choice(("replace", "drop", "duplicate"))
    if action == "replace":
        words[index] = rng.choice(ALPHABET)
    elif action == "drop":
        del words[index]
    else:
        words.insert(index, words[index])
    return " ".join(words)


class FuzzTests(unittest.TestCase):
    """Every corpus is seeded, so a failure names a sample that always reproduces."""

    def test_generated_token_soup_never_crashes_the_host(self) -> None:
        rng = random.Random(SEED)
        overseer, caps = bounded()
        with overseer, caps:
            for number in range(GENERATED_SAMPLES):
                source = generated_source(rng)
                with self.subTest(sample=number, source=source):
                    self.assertIn(assert_no_host_escape(self, source), (RAN, REPORTED))

    def test_structured_programs_run_or_report_a_pebble_error(self) -> None:
        rng = random.Random(SEED)
        successes = 0
        overseer, caps = bounded()
        with overseer, caps:
            for number in range(STRUCTURED_SAMPLES):
                source = structured_program(rng)
                with self.subTest(sample=number, source=source):
                    if assert_no_host_escape(self, source) == RAN:
                        successes += 1
        self.assertGreaterEqual(successes, MINIMUM_SUCCESSES,
                                "the corpus stopped exercising the runtime")

    def test_every_example_runs_under_reduced_caps(self) -> None:
        overseer, caps = bounded()
        samples = example_sources()
        self.assertTrue(samples, "no example programs were found to fuzz")
        with overseer, caps:
            for name, source in samples.items():
                with self.subTest(example=name):
                    self.assertIn(assert_no_host_escape(self, source), (RAN, REPORTED))

    def test_every_example_runs_at_the_real_caps(self) -> None:
        samples = example_sources()
        for name, source in samples.items():
            with self.subTest(example=name):
                self.assertEqual(assert_no_host_escape(self, source), RAN,
                                 "a shipped example must run, not report")

    def test_a_mutated_example_never_crashes_the_host(self) -> None:
        rng = random.Random(SEED)
        samples = example_sources()
        names = sorted(samples)
        overseer, caps = bounded()
        with overseer, caps:
            for number in range(MUTATED_PROGRAMS):
                name = names[number % len(names)]
                source = mutated_source(rng, samples[name])
                with self.subTest(sample=number, example=name, source=source):
                    self.assertIn(assert_no_host_escape(self, source), (RAN, REPORTED))

    def test_the_cli_shield_is_never_needed(self) -> None:
        rng = random.Random(SEED)
        overseer, caps = bounded()
        with overseer, caps:
            for number in range(GENERATED_SAMPLES):
                source = generated_source(rng)
                stdout, stderr = StringIO(), StringIO()
                with self.subTest(sample=number, source=source):
                    code = main(["-e", source], stdin=StringIO(), stdout=stdout, stderr=stderr)
                    self.assertIn(code, (0, 1, 2))
                    self.assertNotIn("internal error", stderr.getvalue())
