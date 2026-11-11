# What a reviewer refuses

Every change is reviewed before it lands, against these rules and the working
rules in `.agent/rules/`. A reviewer refuses:

- A change that does not do what the issue asks, or does more.
- A behaviour change without a test that would fail without it.
- A test weakened, skipped, deleted or marked `xfail` to make a gate pass; an
  `xfail` marker taken off a test without the fix it was waiting for.
- A change that lets a gate check less: the tests' or the linter's settings
  in `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.ruff]` and its
  tables) loosened, or a `conftest.py` that skips or deselects tests.
- A change to input parsing - `src/durasum/parse.py`, or how
  `src/durasum/log.py` splits a line - that does not handle negative values
  the way the forms already read do, with a test for them. A log records a
  correction as a negative entry, so every form a person can write a
  duration in can be written negative.
- Input read as zero, or guessed, where it should be refused with
  `ValueError` naming it.
- A write to a log file anywhere but `src/durasum/store.py`, or a change
  there that could truncate, reorder or re-encode the lines a log already
  holds.
- User-facing behaviour changed without the README saying so.
- A secret, a credential or a personal detail in the diff.
- A write to a protected path.
