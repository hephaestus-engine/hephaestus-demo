---
title: A total of an hour or more prints the hour again in its minutes, as 1h 90m
labels: [bug]
---
## Problem / why

`durasum total` prints a log's total. Every total of an hour or more comes out
wrong: an hour and a half prints as `1h 90m`, and an exact hour as `1h 60m`.
The minutes are counted over the whole duration instead of over what is left
after the hours, so the hours appear twice in what a person reads. Totals
under an hour print correctly, which is why nothing caught it.

## Current state

- `format_duration` (`src/durasum/fmt.py:4`) splits a number of seconds into
  hours, minutes and seconds. Line 13 takes the hours and leaves the rest in
  `rest`; line 14 then takes the minutes and seconds from `remaining`, the
  whole duration, instead of from `rest`.
- `test_hours_and_minutes` (`tests/test_fmt.py:40`) states the right output
  for four durations and fails today. It is marked `xfail` (line 30) so the
  suite stays green until this issue is done; `xfail_strict` in
  `pyproject.toml` fails the suite if the test passes with the marker still
  on.

## The change

1. Take the minutes and seconds from what is left after the hours.
2. Remove the `xfail` marker from `test_hours_and_minutes`, and the comment
   above it that explains the marker.

## Done when

- [ ] `format_duration(3600)` is `1h`, `format_duration(5400)` is `1h 30m`,
      `format_duration(3661)` is `1h 1m 1s` and `format_duration(-5400)` is
      `-1h 30m`.
- [ ] `test_hours_and_minutes` runs without its `xfail` marker and passes.
- [ ] No other test changes.
- [ ] The gates pass: tests, lint and format.

## Tests expected

`test_hours_and_minutes` as it stands is the test: it fails before the change
and passes after it. Sabotage: put line 14 back as it was and the test fails.

## What not to touch

- `src/durasum/parse.py`, `src/durasum/log.py`, `src/durasum/store.py` and the
  command: the defect is in formatting only.
- The other tests.

## Dependencies

Blocked by: none
