# The demos

Each demo is one issue from `demo/issues/`, filed on a fresh copy of this
repository (the README's "Resetting a demo") and worked by the engine as it is
on the day, untuned. A demo shows the engine scoring the issue, routing it,
building the change, running the gates, reviewing it and opening a pull
request a person merges, with what each step cost.

| Demo | Issue file | What it shows | Recording |
|---|---|---|---|
| 1. A plain fix | `demo/issues/01-hours-print-their-minutes-twice.md` | A one-line defect with a failing test: the gates pass, the first review approves, a pull request opens and a person merges it. | TO BE RECORDED |
| 2. Review says no | `demo/issues/02-read-clock-time-durations.md` | A small feature whose first attempt is refused on a rule in the pack's review rules that the issue does not repeat; the findings go back on the issue, the retry is reviewed on what it fixed, a pull request opens and a person merges it. | TO BE RECORDED |
| 3. A moderate feature (later) | `demo/issues/later/03-total-a-log-per-tag.md` | A feature across two modules and the command, landed with the review's notes. Not part of the first set; `scripts/seed.py` files it only when named. | TO BE RECORDED |

## What each demo is expected to do

Expectations are written before a run, so a run can be held to them. They
are expectations, not a script.

**Demo 1, a plain fix.** The pack's rubric (`.agent/rules/20-issue-style.md`)
anchors a wrong variable in `fmt.py` at complexity 1, a printed total at
severity 2, and an issue naming its inputs and outputs at uncertainty 1,
which the engine routes to its lowest tier, T0. The change is one line in
`src/durasum/fmt.py` and the removal of the test's `xfail` marker; the tests,
lint and format gates pass; the first review approves.

**Demo 2, review says no.** A new input form in `parse.py` anchors at
complexity 2, and how a duration is read at severity 3, so the expected tier
is T1. The first attempt is expected to be refused under the review rules
(`.agent/rules/30-review.md`), the findings posted on the issue; the retry
is reviewed on the earlier findings and on what it changed since, and lands
as a pull request. The rules pack is the same one a real project would
write: every run sees the review rules, the builder included. If the first
attempt is approved, that is what the recording shows.

**Demo 3, a moderate feature.** Two modules and the command anchor at
complexity 3; the expected tier is T1, or T2 if triage reads the issue as
leaving its cases unsaid.

## How a demo is recorded

A recording is a directory, `docs/demos/NN-slug/`, named after its issue
file, holding:

| File | What it holds | How it is made |
|---|---|---|
| `README.md` | The header: the date of the run; the engine's commit; the deployment shape (one desktop with Docker, or Kubernetes); the work source (GitHub, or GitLab); and the runtime and model of each job - triage, build, review, and each retry or mend. Then a short account of what happened, including anything that did not go as expected. | Written by hand from the trace and the thread. |
| `thread.md` | The issue thread and the pull or merge request, saved: every comment the engine and people posted, the review findings, the merge. | Saved from the forge after the merge. |
| `trace.jsonl` | The engine's record of the issue: each attempt's tier, routing, gates, verdicts, and each operation's usage and cost. | `agentctl trace export <issue> --repo <checkout> --out trace.jsonl` (JSON Lines). |
| `scorecard.md` | The engine's trial scorecard over the trace, once the engine has one. | The engine's scorecard command over `trace.jsonl`. |
| `dashboard-issue.png` | A screenshot of the engine dashboard's view of the issue. | Taken after the merge. |

### Cost, and what it is not

Costs are shown in tokens and in USD **as the export states them**: the
engine prices each operation at the provider's API list price, an
**API-equivalent** figure. It is not what anyone paid. A run on a
subscription is not billed per token, and no recording shows a person's or
an organisation's real spend: no invoice, no subscription bill, no account
usage page.

Every figure keeps the engine's provenance markers beside it, as the export
records them:

- `source` - where the row came from (`cli_result`, `transcript`,
  `reconstructed`);
- `fidelity` - how much of the truth it is (`exact`, `partial`, `estimated`,
  `lower_bound`);
- `model_source` - whether the model was the one that `served` the call or
  the one routing `requested`;
- on each attempt, `usage_gap_severity`, and on each row,
  `cost_unknown_reason`.

**An unknown cost is shown as unknown**, never as zero, and a total that
holds a `lower_bound` row says so.

### Honest outcomes

A demo is recorded as it ran. A run that does not behave as expected is
recorded, not re-run until it looks right; a second run is a second
recording beside the first, and both are kept. A bug a demo exposes in the
engine is reported to the engine as its own issue, with the recording.

### Nothing private

A recording is scanned for personal data before it is committed. The people
in a thread are named by their role (the maintainer, the reviewer), the
trace export's own redaction stays as it is, and no address, token or
private repository name appears in any file.

## Replaying a demo

1. Reset the demo repository: the README's "Resetting a demo" pushes the
   tag `demo-start` to a fresh, empty repository and files the issues with
   `scripts/seed.py`.
2. Point the engine at a clone of the new repository and check the pack with
   `agentctl check <clone>`.
3. Release the demo's issue for a run, and record it as above.
