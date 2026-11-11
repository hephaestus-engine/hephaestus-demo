# durasum

`durasum` totals the durations in a plain-text work log.

```console
$ cat week.log
# monday
1h30m  write the release notes
45m    review the parser change
-15m   correction: the review ran short
$ durasum total week.log --seconds
7200
$ durasum add week.log 20m stand-up
```

It is also a **demo project** for Hephaestus, an engine that runs coding
agents on a repository's issues: it scores each issue, routes it to a model,
builds the change in a worktree of its own, runs the project's gates, has the
change reviewed, and opens a pull request a person merges. This repository is
small, synthetic and made up for that purpose, so anyone can watch the engine
work on code that carries nothing private. See [What the demo holds](#what-the-demo-holds).

## Install

Python 3.10 or later, no run-time dependencies.

```console
$ python -m pip install .
```

## Usage

```text
durasum total LOG [--seconds]          print the log's total
durasum add LOG DURATION DESCRIPTION   add an entry to the end of the log
```

`total` prints the total as `1h 30m`, or as a number of seconds with
`--seconds`. `add` creates the log if it is missing, and takes everything
after LOG as the entry, so a correction is written as it is:
`durasum add week.log -15m correction`. Input that cannot be read exits with
status 2 and one line on standard error naming the input, and for a log, the
line.

## Log format

One entry a line: a duration, then what the time was spent on. A line
starting with `#` is a comment, and blank lines are skipped.

A duration is written in the unit form: hours, minutes and seconds, each
optional but in that order - `2h`, `45m`, `1h30m`, `90s`, `1h5m30s`. Case does
not matter. A leading `-` makes it negative: a correction to an earlier entry
is recorded as a negative entry, such as `-15m`, and subtracts from the total.

`durasum add` never rewrites a log in place: it writes the new content beside
the log and replaces it in one step, keeping every existing line byte for
byte. Two adds at once take turns on an empty lock file it keeps beside the
log, `.NAME.lock`, so both entries land. A log reached through a symbolic link
is written where the link points, and a read-only log is refused.

## Development

```console
$ python -m pip install -e ".[dev]"
$ python -m pytest -q
$ python -m ruff check .
$ python -m ruff format --check .
```

These three checks are the engine's gates for this repository and the CI's
jobs on both forges. The suite reports one test, in four cases, as **expected
to fail** (`4 xfailed`): it is the planted defect of the first demo, below.
The install needs the package index, so an engine that runs the gates needs
a way out to it or to a mirror.

## What the demo holds

| Path | What it is |
|---|---|
| `.agent/` | The rules pack the engine reads: the manifest; the working rules and the scoring rubric (`rules/`, handed to every run); the review rules (`review/rules.md`, the reviewer's); the report template; and one module. |
| `demo/issues/NN-slug.md` | The demo issues, as files: a title and labels in front matter, a body written to the engine's issue standard. |
| `demo/issues/later/` | An issue kept for a possible later demo; not filed by default, and no recording of it is planned. |
| `scripts/seed.py` | Files the demo issues on a forge. Standard library only. |
| `docs/demos/` | How each demo is recorded, and the recordings. |

The pack holds the demo to what a real project would use:

- **Gates:** the tests, the lint check and the format check, on every change.
- **A model floor:** `src/durasum/store.py` is the only code that writes a
  person's log file, so any change to it, or to its tests, goes to the
  strongest model (`capabilities.log_file`, `min_model: opus`).
- **Protected paths:** no run may write the pack, either forge's CI files,
  environment files, the demo issues or the recordings (`.agent/**`,
  `.github/**`, `.gitlab-ci.yml`, `.env*`, `demo/**`, `docs/demos/**`).
- **Review rules for the reviewer:** the rules a reviewer refuses on are in
  `.agent/review/rules.md` (`pack.review_rules`). Every review prompt points
  at them; the build is handed the working rules and the issue, not them.
- **Landing:** manual dispatch (a person releases each issue by adding the
  `agent:go` label), and every change lands as a pull request a person merges
  (`dispatch.land: pr`, `dispatch.land_pr_label: null`).

The demos:

1. **A plain fix** (`demo/issues/01-hours-print-their-minutes-twice.md`). A
   one-line defect is planted in `src/durasum/fmt.py`: a total of an hour or
   more prints as `1h 90m`. Its test, `test_hours_and_minutes`, fails today
   and is marked `xfail` so the default branch stays green; the fix removes
   the marker, and `xfail_strict` fails the suite if a fix forgets to.
2. **Review says no** (`demo/issues/02-read-clock-time-durations.md`). A
   small feature, reading `1:30` as a duration. The issue is complete as an
   issue, but it does not repeat one of the pack's review rules, which the
   build is not handed, and a first attempt that follows the issue alone is
   likely to be refused on it. The retry is reviewed on what it fixed.

A third issue, a moderate feature (`demo/issues/later/03-total-a-log-per-tag.md`),
is kept for a possible later demo. It is not in the current set.

What each demo shows, and how it is recorded, is in
[docs/demos/README.md](docs/demos/README.md).

## Resetting a demo

A demo runs on a fresh copy of this repository, never on one an earlier run
has changed. Nothing force-pushes: a reset is a new repository.

1. Create an empty repository on the forge: no README, no licence, no issues.
2. Start from the demo's starting point, and name the new repository in the
   manifest. The engine works on the repository its manifest names, and
   `repo` in `.agent/manifest.yaml` is a placeholder no forge account can
   hold, so a copy that skips this step fails on its first tracker call
   instead of reaching someone else's repository:

   ```console
   $ git clone <this repository> durasum-demo && cd durasum-demo
   $ git switch --detach demo-start
   ```

   Set `repo: OWNER/NAME` in `.agent/manifest.yaml`, then push, as the new
   repository's default branch, the starting point with that one line, and
   the tag that marks the starting point:

   ```console
   $ git commit -am "The manifest names this copy's repository"
   $ git push <new repository URL> HEAD:refs/heads/main demo-start
   ```

3. From the same checkout, file the demo issues, with a token that may create
   issues and labels there in `GITHUB_TOKEN` (or `GH_TOKEN`):

   ```console
   $ python scripts/seed.py --forge github --repo OWNER/NAME --dry-run
   $ python scripts/seed.py --forge github --repo OWNER/NAME
   ```

   A GitHub Enterprise Server adds `--base-url https://HOST/api/v3`. The
   script refuses a repository the manifest does not name. An issue whose
   title the repository already has is not filed again, so running it twice
   files nothing twice; the labels it lacks are added.
4. Point the engine at a clone of the new repository, run
   `agentctl check <clone>`, and release one demo issue for a run by adding
   the `agent:go` label to it.
