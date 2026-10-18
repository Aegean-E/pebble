# Decisions

Why this project is built the way it is, oldest first. One entry per decision that changes a
contract, a dependency, a data format or the architecture; IDs are consecutive and never reused.

<!-- Entry format:
### ADR-001: The Pebble v1 language surface is frozen, and every failure carries a position and a fix
- **Date**: 2026-10-18
- **Status**: Accepted
- **Context**: Pebble is built as an AIKit evaluation project: the test is whether the governance process (plan, checkpoints, frozen surface, gates) produces a small language without silent scope creep. A language's surface is a contract, and without a written freeze it grows every session. Separately, the project carries AIKit's error-UX rule: every user-triggered failure must explain why it happened and how to fix it.
- **Decision**: Freeze the v1 surface. Values: int, float, bool, string, list, and none (the absence of a value, added so effectful functions and failed lookups have a representable result; recorded here as the one clarification of the draft plan). Statements: let, assignment, if/else, while, for-in, fn, return, blocks. Operators: + - * / % ^, comparisons, and/or/not, calls, indexing, list literals. Builtins: print, len, range, str, int, floor, min, max, abs. Interfaces: file runner, -e, REPL; exit codes 0/1/2. Every lexer, parser and runtime error renders as file:line:col plus Why and Fix, pinned by a meta test. Non-goals: classes, modules, closures, exceptions, unicode identifiers, break/continue, slices, script arguments. Additions to the surface require a new task and a new ADR.
- **Consequences**: The surface is small enough for one task with six milestone slices, and any silent drift is visible against this record. Error quality is a tested contract rather than a style goal. Cost: unlisted conveniences (slices, break/continue, float()) are refused on purpose; users wait for a later task, and the refusal itself is the evaluation signal.

### ADR-002: Builtin semantics and the value display form are fixed for v1
- **Date**: 2026-10-19
- **Status**: Accepted
- **Context**: ADR-001 lists nine builtin names but not their contracts. Without a written decision, arity, coercion and display details would drift with each edit, and the CLI and REPL would have no stable output to target.
- **Decision**: Builtins are visible in the global scope and may be shadowed by a later `let`. A builtin checks its arity before evaluating arguments and reports the call's position. `print(x)` writes the display form plus a newline and returns none. `len` accepts a string or list. `range` accepts `range(stop)` or `range(start, stop)` with int arguments only (bools excluded), is half-open, and has no step. `str(x)` is the display form. `int(x)` accepts an int, a float truncated toward zero, or a string of an optional `+`/`-` sign and ASCII digits; non-finite floats and bools are refused. `floor(x)` accepts an int or finite float and returns an int. `min`/`max` accept one or more values, or exactly one list of values, and order numbers with numbers or strings with strings; empty input, bools and mixed kinds are errors. `abs(x)` accepts a number. The display form is: `true`/`false`, `none`, `str(float)` for floats, bare text for a top-level string, and `[a, b]` for lists with nested strings double-quoted and `\\`, `"`, newline, tab and carriage return escaped; functions display as `<fn name>` and builtins as `<builtin name>`.
- **Consequences**: All nine names now have testable semantics, so `print` output is a stable CLI/REPL contract rather than an incidental Python `repr`. Costs: no `range` step, no whitespace-tolerant `int(" 42")`, and `min`/`max` deliberately do not order lists; those conveniences wait for a later task.

### ADR-003: v1 caps host-sized resources and turns every host arithmetic failure into a Pebble error
- **Date**: 2026-10-19
- **Status**: Accepted
- **Context**: Hardening found programs that reached Python tracebacks: `0 ^ -1` (ZeroDivisionError), dividing huge ints (OverflowError), printing an int beyond Python's decimal-conversion limit (ValueError), integer literals beyond that limit, and `range`/repetition large enough to exhaust memory. ADR-001 promises that user failures never surface as tracebacks and that errors explain themselves, so the runtime needs explicit limits rather than host behaviour.
- **Decision**: Resource limits live in `limits.py`: call depth 100, integer exponent 10,000, an int of about 4,000 decimal digits (13,280 bits), and a range or repeated sequence of at most 1,000,000 values; a float literal must be finite. An oversized literal or numeric string is a positioned LexError or EvalError, and an arithmetic result over the int cap is an EvalError. `0` raised to a negative power and a division result beyond the largest float are EvalErrors. As a final shield, the CLI converts any unexpected host exception into a three-line internal-error report with a Why and a Fix and exit code 1, never a traceback.
- **Consequences**: Programs have predictable memory and output bounds on every host, and the error-format meta test can assert the three-line form for all three error classes. Costs: arithmetic and ranges beyond the caps are refused (`2 ^ 10000` is allowed, `10 ^ 10000` is not), and larger values wait for a later task.

