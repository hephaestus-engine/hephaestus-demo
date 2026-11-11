---
title: Total a log per tag
labels: [enhancement]
---
## Problem / why

A log mixes work on several things, and `durasum total` gives one number for
all of it. People already mark entries with words such as `+docs` or
`+release`, but nothing reads them, so the time spent on one thing has to be
added up by hand.

## Current state

- `read_entries` (`src/durasum/log.py:29`) splits each line into its duration
  and its description (line 41); `Entry` keeps the description as one string
  and reads no tags.
- `durasum total` (`src/durasum/cli.py:33`) prints one total, as text or, with
  `--seconds` (line 24), as a number of seconds.

## The change

1. A tag is a word in an entry's description that starts with `+` followed
   by one or more letters, digits, `-` or `_`: `+docs`, `+release-2`. `Entry`
   gains `tags`, the entry's tags in the order written, each once, without
   the `+`.
2. `durasum total --by-tag LOG` prints one line per tag, sorted by tag name,
   each the tag and its total, then a line `(untagged)` for the entries with
   no tag, then a line `total` for the whole log. The totals are printed as
   `durasum total` prints them, or in seconds with `--seconds`.
3. An entry with two tags counts towards both tags' lines, and once towards
   `total`. A correction counts against its tags as it counts against the
   total.
4. The README documents tags and `--by-tag`.

## Done when

- [ ] `read_entries` gives each entry its tags as described, and a `+` alone
      or inside a word (`C++`, `a+b`) is not a tag.
- [ ] `durasum total --by-tag --seconds` on the log below prints exactly:

      ```
      docs 2700
      release 1800
      (untagged) 600
      total 3300
      ```

      for the log

      ```
      30m  draft the notes +docs +release
      15m  fix a link +docs
      10m  stand-up
      ```

- [ ] Without `--by-tag`, `durasum total` prints what it prints today.
- [ ] Tests in `tests/test_log.py` and `tests/test_cli.py` cover the above,
      corrections included.
- [ ] The gates pass: tests, lint and format.

## What not to touch

- `src/durasum/parse.py` and `src/durasum/store.py`.
- The log format: a log that reads today reads the same, tags or not.

## Dependencies

Blocked by: none
