# Preserve publication truth during directory close errors

Baseline d3ab2add069a5f487c87ce29dde610fd3e52f2d8.

A directory descriptor close error escaped after a new evidence file had been
atomically published and file-fsynced. CLI callers would report `evidence-not-saved`
even though the target existed. A regression reproduces that failure by closing
the descriptor, then raising an I/O error. It failed before the repair.

Finalization now preserves `published: true` and marks directory durability
`unconfirmed`, matching other post-publication directory failures. It never
retries close because the descriptor may already have been released/reused.
Existing CLI warning handling returns exit 2 without denying publication.
The receipt remains readable and a second save still refuses to overwrite it.

Local full suite: 94 tests, 93 pass, one native-Windows junction skip. Example
CLI and whitespace checks pass. This is injected filesystem failure coverage,
not a power-loss durability test. User files are untouched; PR #17 excluded.
