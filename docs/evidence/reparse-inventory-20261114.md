# Reparse boundaries in loose-file evidence

Baseline: `1354b79feeef1144695442f4e192dafe06ce7e6f`.

The loose-file inventory rejected symbolic links but did not inspect Windows
`FILE_ATTRIBUTE_REPARSE_POINT` on roots or directory entries. This differs from
its own bounded digest reader and MO2 reconciliation. Resolving a root first
could also lose the original junction identity before content inspection.

Three mocked-attribute tests failed before repair: root traversal, regular-file
reparse inclusion, and resolving a content root before rejecting its reparse
attribute. The repair checks root attributes before resolving, skips reparse
entries, and rechecks queued directories before scanning. Existing symlink
error codes and non-reparse paths are preserved. Reparse evidence stays
incomplete and does not offer a winner or hash instead of being guessed valid.

All 90 Python tests and example CLI pass locally; whitespace check passes.
Tests emulate Windows attribute bits on authored temporary paths, not an actual
Windows junction or cloud-file provider. Native junction behavior and hostile
concurrent replacement remain unverified; this is not a race-proof sandbox.
No user mod, profile, save, or installed tool was changed. PR #17's independent
reconciliation changes are not included.
