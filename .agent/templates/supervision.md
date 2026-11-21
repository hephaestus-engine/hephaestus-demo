# Supervision policy

How the supervisor rules when a run of this project stops and asks. This file is on the live check's branch only
(engine issue 135): the project's owner has delegated every decision an issue here can raise.

## What the owner reserves

The owner reserves nothing. No question in this project is a person's alone, so the verdict is never `ask`.

## How to decide

- **A choice between ways to print, round, name or order output.** Choose the option a person can check by hand and
  that never shows more time than was logged: a number that is shortened drops its remainder (it is rounded toward
  zero, as integer division of its size gives), and text keeps the order of the log. `release`, with the decision
  written as what to build and the cases to test.
- **A choice the issue writes out in full on both sides.** That is a decision the issue asks for, not a gap in it:
  pick one by the rule above, say why in one sentence, and `release`.
- **Two statements of an issue that disagree.** The rule above decides which stands. `release`, naming the
  statement that is corrected and the value it should have held.
- **Work that already shipped, that another open issue replaces, or that could only be settled by changing how a
  log file is written (`src/durasum/store.py`).** `close`, saying where the work went or why it is not wanted.

## The verdicts this project uses

`release` or `close`, and nothing else.

- Never `ask`: nothing is reserved for the owner.
- Never `defer`: no issue of this project waits on another.
- Never `split`: nothing here needs what a worktree lacks; the tests, the lint check and the format check all run
  in one.
