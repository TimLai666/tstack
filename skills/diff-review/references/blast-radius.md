# Blast-radius check

Find what a change breaks somewhere else before it ships. Use it on a change that looks small, on a fix, before a refactoring, and when the user asks what a change could affect.

Listing the callers is not the result. The result is the breakage a search would not show, and proof of the one or two facts the change's safety rests on.

## What to look for beyond the diff

- **Consumers of what changed.** Callers of a changed function, readers of a changed field, configuration key, environment variable, file format, database column, or output that another program parses.
- **Things that depend on it without naming it.** Ordering, timing, default values, the type of error raised, what is cached, what happens when the value is empty.
- **Other processes.** Services, scheduled jobs, hooks, CI steps and scripts that run the changed code or read what it writes.
- **Words that describe it.** Documentation, agent instructions, skills and examples that tell someone to use the old behavior.

## Do not trust the write-up

A write-up that sounds right reads the same whether or not it is true. For each fact the change's safety depends on, take it as far down this list as is cheap, and say where it stopped:

1. Stated, with nothing behind it. Worth nothing on its own.
2. Pointed at: the file and line, or the library's own source.
3. Walked through: the failure traced step by step and shown not to reach.
4. Run: a script or test that calls the real code and fails loudly if the fact is wrong.
5. Reproduced in the running application.

Level 4 is usually one small script that imports what the application ships and calls the function in question.

## Report

- What the change touches outside the diff, with file and line.
- The facts its safety rests on, each with the level it reached and the command and output when it was run.
- What could not be checked, and what is missing to check it.
