"""Pebble's command line: a file runner, `-e`, a batch stdin mode and an interactive REPL.

Exit codes are part of the contract: 0 success, 1 a program error, 2 a usage or file error.
Every report keeps the project's Why/Fix shape, so a user never sees a Python traceback.
"""

import sys
from pathlib import Path

from . import __version__, nodes
from .errors import ParseError, PebbleError, format_error
from .evaluator import Interpreter
from .formatting import format_value
from .lexer import tokenize
from .parser import parse

HELP = """usage: pebble [--version] [-h] [-e SOURCE] [FILE] [ARGS...]

Run a Pebble program from a file, evaluate one program from the command line,
or start the REPL. With no arguments, a terminal starts the REPL and piped
input runs as a program. Arguments following FILE, -e SOURCE, or - are passed
to the program as strings in the 'args' list.

positional arguments:
  FILE               run the program in FILE
  ARGS               arguments passed to the program in 'args'

options:
  -e, --eval SOURCE  run SOURCE as a program
  -h, --help         show this help and exit
  --version          show the version and exit
  --                 stop option processing; following arguments are FILE and ARGS

exit codes: 0 success, 1 program error, 2 usage or file error
"""



class CliError(Exception):
    """A usage or file failure, rendered with the same Why/Fix shape as Pebble errors."""

    def __init__(self, message: str, why: str, fix: str) -> None:
        super().__init__(message)
        self.message = message
        self.why = why
        self.fix = fix


def main(argv=None, stdin=None, stdout=None, stderr=None) -> int:
    """Run the command line; every argument defaults to the matching process stream."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    try:
        return _dispatch(arguments, stdin, stdout, stderr)
    except CliError as error:
        stderr.write(f"pebble: error: {error.message}\n"
                     f"  Why: {error.why}\n"
                     f"  Fix: {error.fix}\n")
        return 2
    except Exception as error:
        _report_internal(error, stderr)
        return 1


def _report_internal(error: Exception, stderr) -> None:
    """Last-resort report: a host failure is still explained, and never shown as a traceback."""
    stderr.write("pebble: internal error: the interpreter failed unexpectedly\n"
                 f"  Why: {type(error).__name__}: {error}\n"
                 "  Fix: this is a Pebble bug; report the program and this message\n")


def _dispatch(arguments: list, stdin, stdout, stderr) -> int:
    """Route the arguments to one of the four interfaces."""
    if not arguments:
        if _is_terminal(stdin):
            return run_repl(stdin, stdout, stderr)
        return _run_source(stdin.read(), "<stdin>", stdout, stderr, args=[])
    first = arguments[0]
    if first in ("-h", "--help"):
        stdout.write(HELP)
        return 0
    if first == "--version":
        stdout.write(f"pebble {__version__}\n")
        return 0
    if first == "--":
        rest = arguments[1:]
        if not rest:
            if _is_terminal(stdin):
                return run_repl(stdin, stdout, stderr)
            return _run_source(stdin.read(), "<stdin>", stdout, stderr, args=[])
        if rest[0] == "-":
            return _run_source(stdin.read(), "<stdin>", stdout, stderr, args=rest[1:])
        return _run_file(rest[0], stdout, stderr, args=rest[1:])
    if first in ("-e", "--eval"):
        if len(arguments) < 2:
            raise CliError("option '-e' needs a source string",
                           "-e runs the program given after it, but nothing follows",
                           'write pebble -e "print(1)"')
        return _run_source(arguments[1], "<command>", stdout, stderr, args=arguments[2:])
    if first.startswith("-") and first != "-":
        raise CliError(f"unknown option '{first}'",
                       "this option is not part of the pebble command line",
                       "run pebble --help to see the available options")
    if first == "-":
        return _run_source(stdin.read(), "<stdin>", stdout, stderr, args=arguments[1:])
    return _run_file(first, stdout, stderr, args=arguments[1:])


def _is_terminal(stream) -> bool:
    """Whether the stream is an interactive terminal."""
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


def _run_file(name: str, stdout, stderr, args=None) -> int:
    """Read a UTF-8 file (a BOM is tolerated) and run it."""
    try:
        source = Path(name).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise CliError(f"cannot read file '{name}'",
                       "the file does not exist at this path",
                       "check the spelling, or create the file first") from None
    except IsADirectoryError:
        raise CliError(f"cannot read file '{name}'",
                       "this path is a directory, not a program file",
                       "pass the path of a .peb file inside it") from None
    except UnicodeDecodeError:
        raise CliError(f"cannot read file '{name}'",
                       "the file is not valid UTF-8 text",
                       "save the file as UTF-8, then run it again") from None
    except OSError as error:
        raise CliError(f"cannot read file '{name}'",
                       f"the operating system refused the read: {error.strerror}",
                       "check the path and its permissions") from None
    return _run_source(source, name, stdout, stderr, args=args)


def _run_source(source: str, filename: str, stdout, stderr, args=None) -> int:
    """Tokenize, parse and run one program; program errors exit 1 after the report."""
    try:
        program = parse(tokenize(source))
        Interpreter(out=stdout, args=args).run(program)
    except PebbleError as error:
        stderr.write(format_error(error, filename) + "\n")
        return 1
    return 0


def run_repl(stdin, stdout, stderr, prompt: bool = True, args=None) -> int:
    """Read programs line by line, sharing one interpreter; prompt only when interactive."""
    interpreter = Interpreter(out=stdout, args=args)

    if prompt:
        _write(stdout, f"Pebble {__version__} (Ctrl-D to exit)\n")
    buffer = ""
    while True:
        if prompt:
            _write(stdout, "... " if buffer else ">>> ")
        line = stdin.readline()
        if line == "":
            if buffer.strip():
                _execute_repl(buffer, interpreter, stdout, stderr)
            return 0
        buffer += line
        if not buffer.strip():
            buffer = ""
            continue
        try:
            program = parse(tokenize(buffer))
        except ParseError as error:
            if error.at_eof:
                continue
            _report_repl(error, stderr)
            buffer = ""
            continue
        except PebbleError as error:
            _report_repl(error, stderr)
            buffer = ""
            continue
        _run_repl_program(program, interpreter, stdout, stderr)
        buffer = ""


def _execute_repl(source: str, interpreter, stdout, stderr) -> None:
    """Run the buffered input at end of file, reporting rather than discarding a failure."""
    try:
        program = parse(tokenize(source))
    except PebbleError as error:
        _report_repl(error, stderr)
        return
    _run_repl_program(program, interpreter, stdout, stderr)


def _run_repl_program(program, interpreter, stdout, stderr) -> None:
    """Execute one REPL input and echo the last expression's value when it is not none."""
    try:
        value = interpreter.run(program)
    except PebbleError as error:
        _report_repl(error, stderr)
        return
    if program and isinstance(program[-1], nodes.ExprStmt) and value is not None:
        _write(stdout, format_value(value) + "\n")


def _report_repl(error: PebbleError, stderr) -> None:
    """A REPL error keeps the session alive, so it is reported and forgotten."""
    stderr.write(format_error(error, "<repl>") + "\n")


def _write(stream, text: str) -> None:
    """Write and flush, so prompts appear before the next read."""
    stream.write(text)
    flush = getattr(stream, "flush", None)
    if flush is not None:
        flush()
