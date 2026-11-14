# Repeated content comparison evidence regression

Base: `39ae8fc72135f383a81dd2d13dc02a11de4dd195`.

## Reproduction

`compare_contents` enriches a mutable report. A successful comparison previously
left provider SHA-256 fields behind when a later comparison of the same report
could not read those providers. A later skipped comparison could also retain an
old `sha256-equal` conclusion while its new attempt status said skipped.

Three authored, temporary-directory regressions reproduce the problem:

1. Compare equal files, delete one provider, compare again: the missing provider
   must not retain its previous hash; the successfully reread provider may have
   a current hash, equivalence is unknown and precedence is withheld.
2. Compare successfully, retry with zero read budget: no prior hashes may appear
   as results of the zero-byte attempt.
3. Compare successfully, mark the inventory incomplete, retry: no reads occur,
   no prior hashes/equivalence/winner can survive as fresh evidence.

Before repair, all three new tests failed (13 focused tests, three failures).

## Repair

After validating the requested limits and before reading/skipping, clear prior
provider hashes and reset equivalence to unknown. Incomplete inventory explicitly
withholds winners. Fresh successful reads populate only this attempt's hashes;
existing budget, error retention and protected-read behavior are unchanged.

After repair the full suite passes: `python -m unittest discover -s tests -v`,
85 tests, OK. `git diff --check` also passes.

This repairs in-memory report reuse; it does not introduce file writes, repair,
deduplication or deployment. Tests use authored fixtures, not user assets or
native Skyrim. It does not certify content licensing or game compatibility.
Keep a saved copy of prior evidence if historical comparison records are needed;
the mutable report represents its current attempt, not an append-only history.
