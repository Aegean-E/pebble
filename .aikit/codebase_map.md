# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `18`
- **Total Classes**: `44`
- **Total Top-Level Functions**: `51`
- **Total Class Methods**: `272`
- **Total Source Lines**: `3279`

---

## 📦 Modules & Exported Symbols

### [`pebble/__init__.py`](pebble/__init__.py)
> *Pebble: a tiny, dependency-free scripting language built as an AIKit evaluation project.*

**Size**: `3` lines (`118` bytes)

---

### [`pebble/__main__.py`](pebble/__main__.py)
> *Run Pebble with `python -m pebble`.*

**Size**: `6` lines (`122` bytes)

---

### [`pebble/cli.py`](pebble/cli.py)
> *Pebble's command line: a file runner, `-e`, a batch stdin mode and an interactive REPL.*

**Size**: `217` lines (`8493` bytes)

**Classes:**
- `class CliError` - *A usage or file failure, rendered with the same Why/Fix shape as Pebble errors.*
  - Method `.__init__(message, why, fix)`

**Functions:**
- `def main(argv, stdin, stdout, stderr)` - *Run the command line; every argument defaults to the matching process stream.*
- `def _report_internal(error, stderr)` - *Last-resort report: a host failure is still explained, and never shown as a traceback.*
- `def _dispatch(arguments, stdin, stdout, stderr)` - *Route the arguments to one of the four interfaces.*
- `def _is_terminal(stream)` - *Whether the stream is an interactive terminal.*
- `def _run_file(name, stdout, stderr, args)` - *Read a UTF-8 file (a BOM is tolerated) and run it.*
- `def _run_source(source, filename, stdout, stderr, args)` - *Tokenize, parse and run one program; program errors exit 1 after the report.*
- `def run_repl(stdin, stdout, stderr, prompt, args)` - *Read programs line by line, sharing one interpreter; prompt only when interactive.*
- `def _execute_repl(source, interpreter, stdout, stderr)` - *Run the buffered input at end of file, reporting rather than discarding a failure.*
- `def _run_repl_program(program, interpreter, stdout, stderr)` - *Execute one REPL input and echo the last expression's value when it is not none.*
- `def _report_repl(error, stderr)` - *A REPL error keeps the session alive, so it is reported and forgotten.*
- `def _write(stream, text)` - *Write and flush, so prompts appear before the next read.*

---

### [`pebble/errors.py`](pebble/errors.py)
> *Pebble error types and their one report format.*

**Size**: `43` lines (`1477` bytes)

**Classes:**
- `class PebbleError` - *A user-facing failure: a position in the source, a reason and a concrete fix.*
  - Method `.__init__(message, line, col, why, fix)`
- `class LexError` - *The source text is malformed: an unknown character, a broken string or number.*
- `class ParseError` - *Well-formed tokens that do not form a valid program.*
  - Method `.__init__(message, line, col, why, fix, at_eof)`
- `class EvalError` - *A valid program asked for something impossible: an unknown name, a bad type, zero division.*

**Functions:**
- `def format_error(error, filename)` - *The three-line report every Pebble failure renders as.*

---

### [`pebble/evaluator.py`](pebble/evaluator.py)
> *Tree-walking evaluator: the runtime semantics of Pebble.*

**Size**: `545` lines (`27479` bytes)

**Classes:**
- `class _Return` - *Internal signal carrying a `return` value out of nested blocks; never escapes run().*
  - Method `.__init__(value)`
- `class _Break` - *Internal signal carrying `break` out of nested blocks to the innermost loop.*
- `class _Continue` - *Internal signal carrying `continue` out of nested blocks to the innermost loop.*
- `class PebbleFunction` - *A function defined with `fn`: a name, parameters and a body; no closures in v1.*
  - Method `.__init__(name, params, body)`
- `class Interpreter` - *Runs a parsed program; `out` is the stream the builtins write to.*
  - Method `.__init__(out, args)`
  - Method `.run(program)` - *Execute a whole program; returns the last statement's value (none for most).*
  - Method `.execute(statement)` - *One statement; only expression statements carry a value.*
  - Method `.evaluate(expression)` - *One expression, recursively; every failure is an EvalError with the node's position.*
  - Method `._execute_block(body)` - *Statements in order, in a fresh or existing scope.*
  - Method `._execute_while(statement)` - *A while loop; break and continue affect this innermost loop only.*
  - Method `._execute_for(statement)` - *`for name in ...`, walking a list or the characters of a string.*
  - Method `._define_function(statement)` - *A function definition; nested definitions are refused because v1 has no closures.*
  - Method `._define(name, value)` - *`let` semantics: bind or rebind the name in the current scope.*
  - Method `._assign(name, value, node)` - *`=` semantics: the name must already exist somewhere visible.*
  - Method `._lookup(node)` - *Resolve a name through the frame chain, then the globals.*
  - Method `._declaration_fix(name)` - *Suggest a close visible name, or how to declare the name being looked for.*
  - Method `._evaluate_unary(expression)` - *`-x` on a number, `not x` on any value.*
  - Method `._evaluate_logical(expression)` - *`and` / `or` short-circuit and return an operand, so `x or fallback` works.*
  - Method `._evaluate_binary(expression)` - *Arithmetic, power, comparison and equality, each with its own message.*
  - Method `._add(expression, left, right)` - *Numbers add, strings join, lists join; nothing else mixes.*
  - Method `._concatenate(expression, left, right, kind, unit)` - *Join two sequences within the shared length cap (ADR-009).*
  - Method `._numeric(expression, left, right, word, operation)` - *A binary operation over two numbers, with a shared type error.*
  - Method `._multiply(expression, left, right)` - *Numbers multiply; a string or list repeats by a whole count.*
  - Method `._divide(expression, left, right)` - *Always a float; a zero divisor and an overflowing result are refused with a position.*
  - Method `._remainder(expression, left, right)` - *The Python remainder: its sign follows the divisor.*
  - Method `._power(expression, left, right)` - *Right-associative `^`, with guards for huge, unreal and undefined results.*
  - Method `._check_result(expression, value)` - *Refuse a result outside Pebble's representable values: a huge int or a non-finite float.*
  - Method `._check_float(expression, value)` - *Refuse inf and nan, which have no literal form in Pebble (ADR-006).*
  - Method `._check_int(expression, value)` - *Refuse an int above the digit cap so arithmetic and printing stay bounded.*
  - Method `._order(expression, left, right)` - *`< <= > >=` on two numbers or two strings.*
  - Method `._evaluate_index(expression)` - *`target[index]` on lists and strings, with negative offsets and length in errors.*
  - Method `._evaluate_slice(expression)` - *`target[start:stop:step]` on lists and strings, with Python-style bounds.*
  - Method `._slice_part(node, role)` - *One optional slice part: an int, evaluated only when it is present.*
  - Method `._evaluate_call(expression)` - *A builtin or a defined function can be called.*
  - Method `._call_builtin(expression, builtin)` - *Check the builtin's arity, evaluate its arguments, then run it.*
  - Method `._call_function(expression, function)` - *Arity check, depth check, a fresh frame for the parameters, then the body.*
  - Method `._truth(value)` - *Pebble truthiness: false, none, zero and empties are falsy; everything else is truthy.*
  - Method `._fail(node, message, why, fix)` - *Raise the positioned EvalError; every runtime failure goes through here.*

**Functions:**
- `def _equal(left, right)` - *Pebble equality: ints and floats mix, bools do not, everything else compares within its type.*

---

### [`pebble/formatting.py`](pebble/formatting.py)
> *How Pebble names and displays values in messages and in print.*

**Size**: `53` lines (`1819` bytes)

**Functions:**
- `def is_number(value)` - *True for int and float, but not for bool: Pebble keeps booleans out of arithmetic.*
- `def type_name(value)` - *The name Pebble uses for this value's type: int, string, list, none, function.*
- `def format_value(value)` - *The text a value shows as: strings bare at the top, quoted inside a list.*
- `def _format_element(value)` - *An element inside a list: strings are quoted so their boundaries stay visible.*

---

### [`pebble/lexer.py`](pebble/lexer.py)
> *Pebble lexer: source text to tokens carrying 1-based line and column positions.*

**Size**: `201` lines (`8640` bytes)

**Classes:**
- `class Token` - *One lexical unit; `value` is the payload for numbers and strings, else the token text.*
- `class _Scanner` - *One pass over the source, appending tokens with exact positions.*
  - Method `.__init__(source)`
  - Method `.scan()` - *Every token in the source, ending with one EOF token.*
  - Method `._skip(count)` - *Advance the cursor `count` characters on the same line.*
  - Method `._newline()` - *Advance past a line break, resetting the column.*
  - Method `._comment()` - *Skip from `#` to the end of the line.*
  - Method `._number()` - *Lex an int or a float; a directly following letter is reported as a typo.*
  - Method `._string()` - *Lex a single- or double-quoted string; strings never cross a line.*
  - Method `._escape()` - *The character the escape at the cursor produces, with the cursor moving past it.*
  - Method `._name()` - *Lex an identifier and mark whether it is a reserved word.*
  - Method `._operator()` - *Lex an operator, or explain the character that is not one.*

**Functions:**
- `def _is_name_start(ch)` - *ASCII letter or underscore (v1 identifiers are ASCII on purpose).*
- `def _is_name_part(ch)` - *ASCII letter, digit or underscore.*
- `def tokenize(source)` - *Every token in `source`, ending with one EOF token.*

---

### [`pebble/limits.py`](pebble/limits.py)
> *Resource limits that keep v1 predictable on any host.*

**Size**: `12` lines (`371` bytes)

---

### [`pebble/nodes.py`](pebble/nodes.py)
> *Pebble's abstract syntax tree: frozen nodes, each carrying the position it started at.*

**Size**: `199` lines (`3813` bytes)

**Classes:**
- `class Literal` - *A constant: int, float, bool, string, or none (stored as None).*
- `class ListLiteral` - *A [a, b, c] list constructor.*
- `class Name` - *A reference to a variable, function or builtin.*
- `class Unary` - *A prefix operator: `-x` or `not x`.*
- `class Binary` - *An infix operator: arithmetic, `^`, or a single comparison.*
- `class Logical` - *`and` / `or`, kept apart from Binary so the evaluator can short-circuit.*
- `class Call` - *Calling a function or builtin; the position is the opening parenthesis.*
- `class Index` - *Indexing a list or string; the position is the opening bracket.*
- `class Slice` - *A `target[start:stop:step]` subsequence; None marks an omitted part.*
- `class Let` - *`let name = value`, declaring or rebinding in the current scope.*
- `class Assign` - *`name = value`, rebinding a name that already exists.*
- `class ExprStmt` - *An expression used as a statement; its value is the REPL's echo.*
- `class IfStmt` - *`if` with optional `else` (an `else if` chain is a one-statement else body).*
- `class WhileStmt` - *A `while` loop; the body repeats as long as the condition is truthy.*
- `class ForStmt` - *`for name in iterable { ... }`, iterating a list or a string.*
- `class FnStmt` - *A named function definition; v1 has recursion but no closures.*
- `class ReturnStmt` - *`return` with an optional value; None here means a bare return.*
- `class BreakStmt` - *`break`, leaving the innermost while or for loop.*
- `class ContinueStmt` - *`continue`, starting the innermost while or for loop's next iteration.*

---

### [`pebble/parser.py`](pebble/parser.py)
> *Pebble's recursive-descent parser: tokens in, AST out, positioned errors throughout.*

**Size**: `411` lines (`18753` bytes)

**Classes:**
- `class _Parser` - *One parse of one token stream; every error carries the offending token's position.*
  - Method `.__init__(tokens)`
  - Method `.parse_program()` - *Every statement up to the EOF token.*
  - Method `.parse_statement()` - *One statement: a keyword form, an assignment, or an expression statement.*
  - Method `._assignment_follows()` - *Whether the token after the name at the cursor is a lone `=`.*
  - Method `.parse_let()` - *`let name = expression`.*
  - Method `.parse_if()` - *`if condition { ... }` with an optional `else` block or `else if` chain.*
  - Method `.parse_while()` - *`while condition { ... }`.*
  - Method `.parse_for()` - *`for name in iterable { ... }`.*
  - Method `.parse_fn()` - *`fn name(parameters) { ... }`.*
  - Method `.parse_return()` - *`return` or `return expression`; a bare return is valid at a block end or EOF.*
  - Method `.parse_break()` - *`break` leaves the innermost loop, so it is only valid inside one.*
  - Method `.parse_continue()` - *`continue` starts the innermost loop's next iteration, so it needs a loop.*
  - Method `._parse_loop_body()` - *A loop body, where break and continue are allowed.*
  - Method `.parse_block()` - *A braced statement list; a missing brace at EOF is what the REPL waits on.*
  - Method `.parse_expression()` - *The loosest expression level: `or`.*
  - Method `.parse_or()` - *`a or b and c` parses as `a or (b and c)`.*
  - Method `.parse_and()` - *`and` binds tighter than `or`, looser than `not`.*
  - Method `.parse_not()` - *`not` binds looser than comparison, so `not a == b` tests `a == b`.*
  - Method `.parse_comparison()` - *One comparison, never a chain; `a < b < c` is refused with advice.*
  - Method `.parse_additive()` - *`+` and `-`, left-associative.*
  - Method `.parse_multiplicative()` - *`*`, `/` and `%`, left-associative.*
  - Method `.parse_unary()` - *A single unary minus; `--x` via recursion, `-2 ^ 2` reads as `-(2 ^ 2)`.*
  - Method `.parse_power()` - *`^`, right-associative: `2 ^ 3 ^ 2` is `2 ^ (3 ^ 2)`.*
  - Method `.parse_postfix()` - *Calls and indexing chain left-to-right: `f(1)(2)[3]`.*
  - Method `._parse_subscript(target, opening)` - *One subscript: an index, or a `start:stop[:step]` slice.*
  - Method `._finish_slice(target, opening, start)` - *The stop and step after the first colon, then the closing bracket.*
  - Method `.parse_primary()` - *Literals, names, calls' heads, groups and list constructors.*
  - Method `.peek()` - *The token at the cursor without consuming it.*
  - Method `.previous()` - *The most recently consumed token.*
  - Method `.advance()` - *The token at the cursor, moving past it (EOF never moves).*
  - Method `.check(kind, value)` - *Whether the token at the cursor has this kind (and value).*
  - Method `.match(kind, value)` - *Consume the token at the cursor when it has this kind (and value).*
  - Method `.expect(kind, what, fix, value)` - *Consume the expected token, or report its absence at the offending token.*
  - Method `.fail(token, message, why, fix)` - *Raise the positioned ParseError; `at_eof` tells the REPL to keep reading.*

**Functions:**
- `def parse(tokens)` - *The program the tokens describe; failures are ParseErrors with a position and a fix.*

---

### [`pebble/stdlib.py`](pebble/stdlib.py)
> *Pebble's ten builtins and their shared argument rules.*

**Size**: `261` lines (`10529` bytes)

**Classes:**
- `class Builtin` - *A callable provided by the language itself; stateless and safe to share.*
  - Method `.__init__(name, impl, expects, min_args, max_args)`

**Functions:**
- `def _fail(node, message, why, fix)` - *Raise the positioned EvalError shared by every builtin failure.*
- `def _print(interpreter, call, args)` - *Write one value in display form, then a newline; returns none.*
- `def _len(interpreter, call, args)` - *The number of characters in a string or elements in a list.*
- `def _range_length(start, stop, step)` - *How many values range(start, stop, step) yields, computed without len().*
- `def _range(interpreter, call, args)` - *A half-open list of ints: range(stop), range(start, stop) or range(start, stop, step).*
- `def _str(interpreter, call, args)` - *The display form of any value, as a string.*
- `def _int(interpreter, call, args)` - *An int from an int, a float truncated toward zero, or a signed decimal string.*
- `def _parse_int(call, text)` - *A strict decimal integer: optional sign, ASCII digits, nothing else.*
- `def _float(interpreter, call, args)` - *A float from an int, a float or a decimal string; booleans are refused.*
- `def _parse_float(call, text)` - *A strict decimal number with an optional fraction and exponent.*
- `def _floor(interpreter, call, args)` - *The greatest int not greater than a number.*
- `def _extreme(call, args, want_max, name)` - *The smallest or largest value, from the arguments or from one list argument.*
- `def _orderable(value)` - *Whether min and max may order this value in isolation.*
- `def _same_kind(left, right)` - *Whether two orderable values are comparable: both numbers or both strings.*
- `def _min(interpreter, call, args)` - *The smallest of the values.*
- `def _max(interpreter, call, args)` - *The largest of the values.*
- `def _abs(interpreter, call, args)` - *The magnitude of a number.*

---

### [`tests/__init__.py`](tests/__init__.py)
> *Pebble's test suite.*

**Size**: `1` lines (`27` bytes)

---

### [`tests/test_builtins.py`](tests/test_builtins.py)
> *Builtin tests: the ten builtins, their errors and the display form of values.*

**Size**: `259` lines (`11448` bytes)

**Classes:**
- `class BuiltinTests` - *One behaviour per test; messages, positions and return values are asserted.*
  - Method `.eval_error(source)` - *The EvalError `source` raises.*
  - Method `.test_print_writes_the_display_form_and_a_newline()`
  - Method `.test_print_returns_none_and_handles_a_string_escape()`
  - Method `.test_lists_display_with_quoted_strings_and_nested_values()`
  - Method `.test_functions_and_builtins_display_by_name()`
  - Method `.test_print_has_a_fixed_arity()`
  - Method `.test_len_counts_lists_and_strings()`
  - Method `.test_len_rejects_other_types()`
  - Method `.test_range_builds_half_open_lists()`
  - Method `.test_range_needs_int_arguments()`
  - Method `.test_range_accepts_a_step()`
  - Method `.test_range_step_must_not_be_zero()`
  - Method `.test_a_stepped_range_is_still_length_capped()`
  - Method `.test_range_arity_is_one_to_three()`
  - Method `.test_str_returns_the_display_form()`
  - Method `.test_int_truncates_floats_toward_zero()`
  - Method `.test_int_parses_signed_decimal_strings()`
  - Method `.test_int_rejects_bad_strings_and_other_types()`
  - Method `.test_int_rejects_non_finite_floats()`
  - Method `.test_float_converts_ints_floats_and_decimal_strings()`
  - Method `.test_float_rejects_bad_strings_and_bools()`
  - Method `.test_float_refuses_a_result_that_is_not_finite()`
  - Method `.test_floor_rounds_down_to_an_int()`
  - Method `.test_floor_rejects_non_numbers_and_non_finite_floats()`
  - Method `.test_min_and_max_compare_numbers_and_strings()`
  - Method `.test_min_and_max_accept_a_single_list()`
  - Method `.test_min_and_max_reject_mixed_or_unorderable_types()`
  - Method `.test_min_and_max_need_at_least_one_argument()`
  - Method `.test_abs_returns_the_magnitude()`
  - Method `.test_abs_rejects_non_numbers()`
  - Method `.test_a_misspelled_builtin_is_suggested()`

**Functions:**
- `def evaluate(source, out)` - *Evaluate `source` with a fresh interpreter; the last statement's value comes back.*
- `def call_builtin(name, *args)` - *Call one builtin directly, for guards that user source can no longer reach.*
- `def printed(source)` - *Everything `source` writes through print.*

---

### [`tests/test_cli.py`](tests/test_cli.py)
> *CLI and REPL tests: argument handling, file and stdin runners, exit codes and error reports.*

**Size**: `159` lines (`6884` bytes)

**Classes:**
- `class TtyInput` - *A stdin stand-in that claims to be a terminal, so main() starts the REPL.*
  - Method `.isatty()`
- `class CliTests` - *One behaviour per test; exit codes and the three-line error report are asserted.*
  - Method `.test_eval_runs_a_program_and_prints_through_the_builtin()`
  - Method `.test_eval_reports_positioned_runtime_errors_and_exits_1()`
  - Method `.test_eval_reports_a_parse_error()`
  - Method `.test_file_runner_reads_utf8_with_a_bom_and_crlf()`
  - Method `.test_file_errors_name_the_file_and_exit_1()`
  - Method `.test_a_missing_file_is_a_usage_error_with_a_fix()`
  - Method `.test_piped_stdin_runs_as_a_program()`
  - Method `.test_usage_errors_exit_2()`
  - Method `.test_eval_receives_script_arguments()`
  - Method `.test_file_runner_receives_script_arguments()`
  - Method `.test_piped_stdin_receives_script_arguments()`
  - Method `.test_double_dash_terminates_options()`
  - Method `.test_help_and_version_exit_0()`
  - Method `.test_a_terminal_stdin_starts_the_repl()`
- `class ReplTests` - *The REPL keeps one interpreter alive, echoes expression values and survives errors.*
  - Method `.repl(source)` - *Run a non-prompting REPL session over `source`; returns (code, stdout, stderr).*
  - Method `.test_state_persists_and_expression_values_are_echoed()`
  - Method `.test_print_output_is_not_echoed_twice()`
  - Method `.test_a_block_continues_until_it_is_complete()`
  - Method `.test_an_error_is_reported_and_the_session_continues()`
  - Method `.test_an_incomplete_program_at_eof_is_reported()`

**Functions:**
- `def run_cli(argv, stdin_text)` - *Run main() over in-memory streams; returns (exit code, stdout, stderr).*

---

### [`tests/test_evaluator.py`](tests/test_evaluator.py)
> *Evaluator tests: semantics, scoping, control flow, functions and runtime errors.*

**Size**: `305` lines (`13781` bytes)

**Classes:**
- `class EvaluatorTests` - *One behaviour per test; messages, positions and types are asserted, not just raised.*
  - Method `.eval_error(source)` - *The EvalError `source` raises.*
  - Method `.test_arithmetic_evaluates_with_precedence()`
  - Method `.test_power_is_right_associative_and_unary_minus_applies_after()`
  - Method `.test_division_always_produces_a_float()`
  - Method `.test_remainder_follows_the_divisor_sign()`
  - Method `.test_float_arithmetic()`
  - Method `.test_string_concatenation_and_repetition()`
  - Method `.test_list_concatenation_repetition_and_deep_equality()`
  - Method `.test_repeat_count_must_not_be_negative()`
  - Method `.test_division_by_zero_is_a_positioned_eval_error()`
  - Method `.test_remainder_by_zero_is_an_eval_error()`
  - Method `.test_type_errors_name_both_types()`
  - Method `.test_ordering_mixed_types_is_an_error()`
  - Method `.test_comparisons_work_on_strings()`
  - Method `.test_equality_across_types_is_false_not_an_error()`
  - Method `.test_power_guards()`
  - Method `.test_logical_operators_short_circuit()`
  - Method `.test_truthiness_rules()`
  - Method `.test_last_statement_value_is_returned()`
  - Method `.test_if_is_a_statement_and_produces_no_value()`
  - Method `.test_if_else_runs_only_the_taken_branch()`
  - Method `.test_while_loop_accumulates()`
  - Method `.test_for_loop_walks_lists_and_strings()`
  - Method `.test_for_over_a_number_is_an_error()`
  - Method `.test_loop_variables_live_in_the_enclosing_scope()`
  - Method `.test_break_exits_the_innermost_loop()`
  - Method `.test_continue_skips_to_the_next_iteration()`
  - Method `.test_continue_in_a_while_reaches_the_condition()`
  - Method `.test_loop_control_inside_a_function_stays_in_its_loop()`
  - Method `.test_let_and_assignment_scope_rules()`
  - Method `.test_unknown_name_suggests_a_close_declared_name()`
  - Method `.test_unknown_name_without_a_close_match_offers_declaration()`
  - Method `.test_position_on_a_type_error_points_at_the_operator()`
  - Method `.test_recursion_works()`
  - Method `.test_function_without_a_return_produces_none()`
  - Method `.test_return_unwinds_nested_blocks()`
  - Method `.test_return_outside_a_function_is_an_error()`
  - Method `.test_arity_mismatch_names_the_function()`
  - Method `.test_arguments_are_evaluated_in_the_callers_scope()`
  - Method `.test_calling_a_non_function_is_an_error()`
  - Method `.test_recursion_depth_limit_is_a_pebble_error()`
  - Method `.test_nested_functions_are_refused()`
  - Method `.test_indexing_lists_and_strings_with_negative_offsets()`
  - Method `.test_index_out_of_range_shows_the_length()`
  - Method `.test_index_must_be_an_integer_and_a_sequence()`
  - Method `.test_slicing_lists_and_strings()`
  - Method `.test_slice_bounds_may_be_negative_and_are_clamped()`
  - Method `.test_slice_step_walks_and_can_reverse()`
  - Method `.test_slice_step_zero_is_an_error()`
  - Method `.test_slice_bounds_must_be_ints_and_bools_are_refused()`
  - Method `.test_only_lists_and_strings_can_be_sliced()`
  - Method `.test_a_very_deep_expression_chain_is_a_pebble_error()`
  - Method `.test_args_defaults_to_empty_list()`
  - Method `.test_args_passed_to_interpreter_are_accessible_as_strings()`
  - Method `.test_args_can_be_iterated_in_for_loop()`
  - Method `.test_calling_args_gives_a_helpful_fix()`

**Functions:**
- `def run(source, out, args)` - *Evaluate `source` with a fresh interpreter; the last statement's value comes back.*

---

### [`tests/test_hardening.py`](tests/test_hardening.py)
> *Hardening tests: error-format contract, resource guards, platform parity and performance.*

**Size**: `256` lines (`10127` bytes)

**Classes:**
- `class ErrorFormatTests` - *Every error kind carries a position, a reason and a fix, and renders as three lines.*
  - Method `.assert_reported(source, expected)`
  - Method `.test_every_lexer_error_path_is_formatted()`
  - Method `.test_every_parser_error_path_is_formatted()`
  - Method `.test_every_runtime_error_path_is_formatted()`
  - Method `.test_an_unexpected_interpreter_failure_never_leaks_a_traceback()`
- `class ResourceGuardTests` - *Hostile or accidental programs fail as positioned Pebble errors, not host exceptions.*
  - Method `.eval_error(source)`
  - Method `.lex_error(source)`
  - Method `.test_zero_to_a_negative_power_is_refused()`
  - Method `.test_a_division_result_too_large_for_a_float_is_refused()`
  - Method `.test_a_non_finite_float_result_is_refused()`
  - Method `.test_finite_extremes_still_compute()`
  - Method `.test_an_int_result_over_the_digit_cap_is_refused()`
  - Method `.test_a_power_within_the_cap_still_works()`
  - Method `.test_an_oversized_integer_literal_is_a_lex_error()`
  - Method `.test_an_oversized_float_literal_is_a_lex_error()`
  - Method `.test_an_oversized_numeric_string_cannot_become_an_int()`
  - Method `.test_range_length_is_capped()`
  - Method `.test_huge_range_bounds_are_capped_not_a_host_overflow()`
  - Method `.test_sequence_repetition_length_is_capped()`
  - Method `.test_sequence_concatenation_is_capped()`
- `class PlatformTests` - *Positions and string lengths use characters and tolerate CRLF sources.*
  - Method `.test_crlf_source_keeps_line_and_column_positions()`
  - Method `.test_unicode_strings_count_characters_not_bytes()`
  - Method `.test_a_unicode_string_does_not_shift_a_later_error_position()`
- `class PerformanceTests` - *The tree walker and parser stay usable; the whole suite stays far under a second.*
  - Method `.test_a_50k_iteration_loop_finishes_quickly()`
  - Method `.test_parsing_10k_statements_finishes_quickly()`

**Functions:**
- `def evaluate(source, out)` - *Evaluate `source` with a fresh interpreter; the last statement's value comes back.*
- `def run_cli(argv, stdin_text)` - *Run main() over in-memory streams; returns (exit code, stdout, stderr).*

---

### [`tests/test_lexer.py`](tests/test_lexer.py)
> *Lexer tests: token streams, positions, and every lex-error path (PRINCIPLE-014 R2).*

**Size**: `114` lines (`4799` bytes)

**Classes:**
- `class LexerTests` - *One behaviour per test; every failure message is asserted, not just raised.*
  - Method `.lex_error(source)` - *The LexError `source` raises.*
  - Method `.test_empty_source_yields_a_single_eof_token()`
  - Method `.test_eof_token_marks_the_end_position()`
  - Method `.test_integers_and_floats_keep_their_types()`
  - Method `.test_leading_dot_is_rejected()`
  - Method `.test_trailing_dot_is_rejected_with_a_float_hint()`
  - Method `.test_number_followed_by_a_letter_is_rejected()`
  - Method `.test_strings_single_and_double_quotes()`
  - Method `.test_string_escapes()`
  - Method `.test_unknown_escape_reports_its_position()`
  - Method `.test_unterminated_string_points_at_the_opening_quote()`
  - Method `.test_unterminated_string_at_eof()`
  - Method `.test_comments_run_to_the_end_of_the_line()`
  - Method `.test_two_char_operators_lex_as_one_token()`
  - Method `.test_keywords_and_names_are_distinguished()`
  - Method `.test_break_and_continue_are_keywords()`
  - Method `.test_positions_track_lines_and_columns()`
  - Method `.test_crlf_sources_count_lines()`
  - Method `.test_identifiers_are_ascii_only()`
  - Method `.test_semicolon_gets_a_separator_hint()`

**Functions:**
- `def pairs(source)` - *Every (kind, value) in `source`, the trailing EOF token excluded.*

---

### [`tests/test_parser.py`](tests/test_parser.py)
> *Parser tests: AST shapes for precedence and statements, and every parse-error path.*

**Size**: `234` lines (`10058` bytes)

**Classes:**
- `class ParserTests` - *AST shape and error position, one behaviour per test.*
  - Method `.parse_error(source)` - *The ParseError `source` raises.*
  - Method `.test_empty_program()`
  - Method `.test_multiplication_binds_tighter_than_addition()`
  - Method `.test_power_is_right_associative()`
  - Method `.test_unary_minus_binds_looser_than_power()`
  - Method `.test_not_binds_looser_than_comparison()`
  - Method `.test_or_binds_looser_than_and()`
  - Method `.test_comparison_chains_are_rejected()`
  - Method `.test_let_and_assignment()`
  - Method `.test_list_literals_and_indexing()`
  - Method `.test_calls_chain()`
  - Method `.test_slices_parse_with_omitted_parts()`
  - Method `.test_a_subscript_without_a_colon_stays_an_index()`
  - Method `.test_a_slice_has_at_most_three_parts()`
  - Method `.test_if_else_and_else_if()`
  - Method `.test_if_without_else()`
  - Method `.test_while_loop()`
  - Method `.test_for_in_loop()`
  - Method `.test_break_and_continue_inside_loops()`
  - Method `.test_break_and_continue_outside_a_loop_are_rejected()`
  - Method `.test_a_function_body_is_not_inside_the_enclosing_loop()`
  - Method `.test_break_in_a_nested_loop_is_allowed()`
  - Method `.test_function_definition_and_return()`
  - Method `.test_bare_return_renders_without_a_value()`
  - Method `.test_statements_need_no_separator()`
  - Method `.test_equality_is_not_assignment()`
  - Method `.test_missing_close_group_at_eof_marks_at_eof()`
  - Method `.test_unexpected_token_inside_a_block_is_not_at_eof()`
  - Method `.test_let_without_equals()`
  - Method `.test_stray_else_is_reported()`
  - Method `.test_duplicate_parameter_is_rejected()`
  - Method `.test_trailing_comma_gets_a_hint()`
  - Method `.test_eof_inside_a_call_marks_at_eof()`
  - Method `.test_if_requires_braces()`
  - Method `.test_deeply_nested_expression_is_a_parse_error_not_a_crash()`

**Functions:**
- `def render(node)` - *A compact parenthesised form of one AST node, for readable assertions.*
- `def _literal(value)` - *How a literal renders in the sexpr form.*
- `def _optional(node)` - *A slice part that may be omitted renders as `_`.*
- `def _body(statements)` - *A block renders as { statement statement }.*
- `def render_all(source)` - *Every statement of `source` in sexpr form.*

---
