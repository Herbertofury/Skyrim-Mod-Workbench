# Header reader descriptor identity

Baseline: 6582c2051d5c46c4510bb910ec1e483bfa5a8058.

Pathname metadata before/after reading did not prove the opened stream belonged
to that file. A deterministic replacement stream with a valid but different
master list was accepted under the original plugin name. A second regression
shows changed descriptor metadata was not observed. Both tests fail before the
repair (11 focused tests, 2 failures).

The reader now verifies opened descriptor identity before reading or charging
the byte budget and verifies descriptor metadata again before closing. Like
the existing asset reader, ctime comparisons remain within the same stat API
to avoid Windows stat/fstat differences. Pathname checks remain in place.
No additional file-content reads, optional-tool dependency, or writes were added.

Local suite: 93 tests, 92 pass and the real Windows junction test explicitly
skipped on Linux. Example CLI and whitespace checks pass. These are authored
fixtures and injected changes, not a hostile-race guarantee or real-game/plugin
migration acceptance. Pending reconciliation PR #17 is not included.
