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
