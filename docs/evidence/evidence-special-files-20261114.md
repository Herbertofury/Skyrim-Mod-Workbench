# Bounded evidence input must also be a regular file

The byte-limited verifier could wait indefinitely when given a POSIX FIFO with no writer. A subprocess regression reproduced the hang and was terminated by its two-second test timeout. A directory-before-open check also failed before this repair.

Reject non-regular sources before open. Use nonblocking open where POSIX supports it, then verify the opened descriptor is regular as well, covering a FIFO substitution after preflight. Ordinary regular files and links to regular files retain support. This is not a general race-free filesystem or network-filesystem timeout guarantee.

110 local tests:109 passed, one native Windows junction test skipped. FIFO preflight and post-preflight substitution, directory rejection and ordinary saved-snapshot verification are covered. Existing byte cap, integrity contract, JSON/HTML diagnostics and read-only semantics remain. No user data or real tools were involved. Windows/Linux CI is separate from these local results.
