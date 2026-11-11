# Scoring an issue

Triage scores every issue on four axes, each a whole number from 1 (low) to
5 (high), and the engine routes it from the scores. The anchors are this
project's own.

- **C - complexity:** how hard the change is.
  1: one function, an obvious edit (a wrong variable in `fmt.py`).
  2: one module and its tests (a new input form in `parse.py`).
  3: two modules and the command (a new kind of report).
  4: a change to the log format that every module reads.
  5: a redesign of how the log is stored.
- **V - value:** the benefit if it lands right. Orders the queue only; it
  never picks the model.
  1: tidiness nobody sees. 3: a wrong output a person would notice.
  5: a log a person cannot use today.
- **S - severity:** the damage if it lands wrong.
  1: a comment or the README.
  2: text a person reads and can check by eye, such as how a total is
  printed.
  3: a value computed wrongly without anything saying so: how a duration is
  read, or what a total adds up.
  4: logs that read today stop reading.
  5: anything that can lose or corrupt a person's log file (`store.py`).
- **U - uncertainty:** how much the issue leaves unsaid.
  1: the issue names the inputs and the outputs it expects.
  3: the behaviour is named, the cases are not.
  5: the issue states a goal and nothing else. A high score asks for a
  clarification first.
