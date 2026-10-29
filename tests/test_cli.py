"""CLI and REPL tests: argument handling, file and stdin runners, exit codes and error reports."""

import re
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from pebble import __version__
from pebble.cli import main, run_repl


class TtyInput(StringIO):
    """A stdin stand-in that claims to be a terminal, so main() starts the REPL."""

    def isatty(self) -> bool:
        return True


def run_cli(argv, stdin_text: str = ""):
    """Run main() over in-memory streams; returns (exit code, stdout, stderr)."""
    stdout, stderr = StringIO(), StringIO()
    code = main(argv, stdin=StringIO(stdin_text), stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


class CliTests(unittest.TestCase):
    """One behaviour per test; exit codes and the three-line error report are asserted."""

    def test_eval_runs_a_program_and_prints_through_the_builtin(self) -> None:
        code, out, err = run_cli(["-e", 'print("hi")'])
        self.assertEqual((code, out, err), (0, "hi\n", ""))

    def test_eval_reports_positioned_runtime_errors_and_exits_1(self) -> None:
        code, out, err = run_cli(["-e", "1 / 0"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("<command>:1:3: error: division by zero", err)
        self.assertIn("Why:", err)
        self.assertIn("Fix:", err)

    def test_eval_reports_a_parse_error(self) -> None:
        code, _, err = run_cli(["-e", "let = 1"])
        self.assertEqual(code, 1)
        self.assertIn("<command>:1:5: error:", err)

    def test_file_runner_reads_utf8_with_a_bom_and_crlf(self) -> None:
        handle = tempfile.NamedTemporaryFile("w", suffix=".peb", delete=False,
                                             encoding="utf-8-sig", newline="\r\n")
        self.addCleanup(Path(handle.name).unlink)
        with handle:
            handle.write('print("hello")\nprint(1 + 2)\n')
        code, out, err = run_cli([handle.name])
        self.assertEqual(code, 0)
        self.assertEqual(out, "hello\n3\n")
        self.assertEqual(err, "")

    def test_file_errors_name_the_file_and_exit_1(self) -> None:
        handle = tempfile.NamedTemporaryFile("w", suffix=".peb", delete=False, encoding="utf-8")
        self.addCleanup(Path(handle.name).unlink)
        with handle:
            handle.write("1 / 0")
        code, _, err = run_cli([handle.name])
        self.assertEqual(code, 1)
        self.assertIn(f"{handle.name}:1:3: error: division by zero", err)

    def test_a_missing_file_is_a_usage_error_with_a_fix(self) -> None:
        code, out, err = run_cli(["does-not-exist.peb"])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("cannot read file 'does-not-exist.peb'", err)
        self.assertIn("Why:", err)
        self.assertIn("Fix:", err)

    def test_piped_stdin_runs_as_a_program(self) -> None:
        code, out, err = run_cli([], stdin_text="print(2 + 3)\n")
        self.assertEqual((code, out, err), (0, "5\n", ""))

    def test_usage_errors_exit_2(self) -> None:
        for argv in (["--nope"], ["-e"], ["--bad-flag"]):
            with self.subTest(argv=argv):
                code, out, err = run_cli(argv)
                self.assertEqual((code, out), (2, ""))
                self.assertIn("pebble: error:", err)
                self.assertIn("Why:", err)
                self.assertIn("Fix:", err)

    def test_eval_receives_script_arguments(self) -> None:
        code, out, err = run_cli(["-e", "print(args)", "hello", "world"])
        self.assertEqual((code, out, err), (0, '["hello", "world"]\n', ""))

    def test_file_runner_receives_script_arguments(self) -> None:
        handle = tempfile.NamedTemporaryFile("w", suffix=".peb", delete=False, encoding="utf-8")
        self.addCleanup(Path(handle.name).unlink)
        with handle:
            handle.write('print(args[0])\nprint(len(args))\n')
        code, out, err = run_cli([handle.name, "alpha", "beta"])
        self.assertEqual((code, out, err), (0, "alpha\n2\n", ""))

    def test_piped_stdin_receives_script_arguments(self) -> None:
        code, out, err = run_cli(["-", "first", "second"], stdin_text="print(args[0] + args[1])\n")
        self.assertEqual((code, out, err), (0, "firstsecond\n", ""))

    def test_double_dash_terminates_options(self) -> None:
        handle = tempfile.NamedTemporaryFile("w", suffix=".peb", delete=False, encoding="utf-8")
        self.addCleanup(Path(handle.name).unlink)
        with handle:
            handle.write('print(args)\n')
        code, out, err = run_cli(["--", handle.name, "-x", "--opt"])
        self.assertEqual((code, out, err), (0, '["-x", "--opt"]\n', ""))

    def test_help_and_version_exit_0(self) -> None:
        code, out, err = run_cli(["--help"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("usage: pebble", out)
        self.assertIn("exit codes: 0 success, 1 program error, 2 usage or file error", out)
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertEqual(out, f"pebble {__version__}\n")

    def test_the_reported_version_matches_the_packaging_metadata(self) -> None:
        manifest = Path(__file__).resolve().parent.parent / "pyproject.toml"
        declared = re.search(r'^version\s*=\s*"([^"]+)"', manifest.read_text(encoding="utf-8"),
                             re.MULTILINE)
        self.assertIsNotNone(declared, "pyproject.toml declares no project version")
        self.assertEqual(declared.group(1), __version__,
                         "pebble.__version__ and pyproject.toml disagree")

    def test_a_terminal_stdin_starts_the_repl(self) -> None:
        stdout, stderr = StringIO(), StringIO()
        code = main([], stdin=TtyInput("1 + 2\n"), stdout=stdout, stderr=stderr)
        self.assertEqual((code, stderr.getvalue()), (0, ""))
        self.assertIn(">>> ", stdout.getvalue())
        self.assertIn("3\n", stdout.getvalue())


class ReplTests(unittest.TestCase):
    """The REPL keeps one interpreter alive, echoes expression values and survives errors."""

    def repl(self, source: str):
        """Run a non-prompting REPL session over `source`; returns (code, stdout, stderr)."""
        stdout, stderr = StringIO(), StringIO()
        code = run_repl(StringIO(source), stdout, stderr, prompt=False)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_state_persists_and_expression_values_are_echoed(self) -> None:
        code, out, err = self.repl("let x = 2\nx * 3\n")
        self.assertEqual((code, out, err), (0, "6\n", ""))

    def test_print_output_is_not_echoed_twice(self) -> None:
        code, out, _ = self.repl('print("hi")\n')
        self.assertEqual((code, out), (0, "hi\n"))

    def test_a_block_continues_until_it_is_complete(self) -> None:
        code, out, _ = self.repl("fn f() {\nreturn 7\n}\nf()\n")
        self.assertEqual((code, out), (0, "7\n"))

    def test_an_error_is_reported_and_the_session_continues(self) -> None:
        code, out, err = self.repl("1 / 0\n2 + 2\n")
        self.assertEqual((code, out), (0, "4\n"))
        self.assertIn("<repl>:1:3: error: division by zero", err)

    def test_an_incomplete_program_at_eof_is_reported(self) -> None:
        code, _, err = self.repl("fn f() {\n")
        self.assertEqual(code, 0)
        self.assertIn("<repl>:2:1: error:", err)


if __name__ == "__main__":
    unittest.main()
