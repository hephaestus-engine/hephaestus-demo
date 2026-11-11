# Working rules

These rules are appended to every run's system prompt, in the order of their
numeric prefixes.

## The project

`durasum` totals the durations in a plain-text work log. It is a small
library under `src/durasum/` and one command, `durasum`:

- `parse.py` reads a duration a person wrote; `fmt.py` writes one back.
- `log.py` reads a log, one entry a line, and totals it.
- `store.py` is the only code that writes a person's log file.
- `cli.py` is the command.

## How to work here

- Work only on what the issue asks. A change outside its scope is said in the
  report as a follow-up, not made in passing.
- Python 3.10 and later, standard library only at run time. Public functions
  carry type hints and a docstring that says what they return and what they
  refuse.
- Input the tool cannot read raises `ValueError` naming the input; the
  command turns it into one line on standard error and exit status 2. Nothing
  unreadable is read as zero or guessed.
- Every behaviour change comes with a test in `tests/` that fails without it.
  Never weaken, skip or delete a test to make a gate pass.
- An `xfail` marker in `tests/` stands for a known defect with an open issue.
  It is removed only by the change that fixes that defect, and the suite
  fails if it is left on a test that passes.
- The gates are `python -m pytest -q`, `python -m ruff check .` and
  `python -m ruff format --check .`; run them before you finish.
- A log file is a person's only copy of what they recorded. Nothing writes it
  except `store.py`, and `store.py` never truncates it in place.
- User-facing behaviour that changes is changed in `README.md` too.
- Say plainly in the report what was not done, and why.
