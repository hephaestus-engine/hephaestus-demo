---
name: log-file
description: How a person's log file is written, and what a change to that code must keep.
paths: ["src/durasum/store.py", "tests/test_store.py"]
keywords: ["log file", "append", "durasum add"]
capability: log_file
---
# Writing the log file

`src/durasum/store.py` is the only code that writes a log file, and the
manifest's `log_file` floor sends every change to it to the strongest model.
A change there keeps every one of these:

- **Never in place.** New content goes to a temporary file in the log's own
  directory, is flushed and synced, and replaces the log with `os.replace`.
  A crash, a full disk or a refused entry leaves the old log whole, and no
  temporary file behind.
- **Byte for byte.** The lines a log already holds are kept exactly: their
  order, their encoding and their line endings. A new line uses the line
  ending the log already uses.
- **Checked before written.** An entry the log could not read back - a
  duration `parse_duration` refuses, a description with a line break - is
  refused before the file is touched.
- **Same permissions.** The replaced log keeps the permissions it had; a new
  log gets the permissions any new file would; a log the person may not
  write is refused, not replaced.
- **One writer at a time.** A write holds the lock on `.NAME.lock` beside
  the log from reading it to replacing it, so two writes at once both land.
- **Where the link points.** A log reached through a symbolic link is
  written at its target, and the link stays a link.

`tests/test_store.py` holds each of these; a change that alters one changes
its test in the same change, and says why in the report.
