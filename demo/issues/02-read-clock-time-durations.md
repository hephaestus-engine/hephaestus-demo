---
title: Read durations written as clock time, such as 1:30
labels: [enhancement]
---
## Problem / why

Timesheets write a duration as hours and minutes on a clock: `1:30` for an
hour and a half. `durasum` refuses that form today (`not a duration: '1:30'`),
so a log copied from a timesheet has to be rewritten by hand, line by line,
before it can be totalled.

## Current state

- `parse_duration` (`src/durasum/parse.py:10`) reads one form, the unit form
  (`2h`, `45m`, `1h30m`, `90s`, `1h5m30s`), through the pattern at line 7, and
  raises `ValueError` naming the input for anything else.
- `read_entries` (`src/durasum/log.py:29`) reads the first word of each log
  line with `parse_duration` (line 43), and `append_entry`
  (`src/durasum/store.py:18`) checks a new entry's duration with it, so the
  log, `durasum total` and `durasum add` all take whatever it reads.
- `tests/test_parse.py:38` lists `1:30` among the inputs refused today.
- The README's "Log format" section lists the forms a duration may take.

## The change

1. `parse_duration` also reads the clock form `H:MM`: one or more digits of
   hours, a colon, then exactly two digits of minutes from `00` to `59`.
   `1:30` is 5400 seconds, `0:45` is 2700 and `12:05` is 43500.
2. A clock form whose minutes are not two digits or are 60 or more (`1:5`,
   `1:75`), and one with seconds (`1:30:00`), are refused with `ValueError`
   naming the input, as any other unreadable duration is.
3. `durasum total` and `durasum add` take the clock form through
   `parse_duration`; neither changes otherwise.
4. The README's "Log format" section lists the clock form.

## Done when

- [ ] `parse_duration` returns the values above, and refuses the inputs above
      with `ValueError` naming them.
- [ ] `durasum total --seconds` on a log whose entries are `1:30` and `45m`
      prints `8100`.
- [ ] `tests/test_parse.py` covers each accepted and each refused form above;
      `1:30` is no longer among the refused inputs.
- [ ] A test in `tests/test_cli.py` totals a log that mixes both forms.
- [ ] The README lists the clock form.
- [ ] The gates pass: tests, lint and format.

## Tests expected

Each case above as its own test case, failing before the change. Sabotage:
make the clock form accept `1:75`, and a test fails.

## What not to touch

- The unit form: every input it reads today reads the same afterwards.
- `src/durasum/fmt.py`: totals are still printed in the unit form.
- `src/durasum/store.py`.

## Dependencies

Blocked by: none
