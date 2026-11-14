# Repeated MO2 directory reconciliation

Baseline: `0ed4302c46cd0186de986013b6b090b4f0188075`.

`reconcile_mods` mutates a parsed report. Reusing it after a successful inventory
kept the previous `directory_name` on subsequently missing or unreadable mods.
It also retained `profile_assets` marked `audited`, despite that result being
based on the old directory inventory. Even another successful inventory cannot
prove the previous asset hashes and files are still current.

Three authored temporary-directory regressions failed against the baseline:
missing directory retained its name; failed rescan retained its name; successful
rescan retained the old derived asset audit (10 focused tests, 3 failures).

The owner now invalidates the old asset result and directory names at the start
of a new inventory. Successful matches refill their actual names. Asset analysis
remains an explicit optional step, not a mandatory expensive rescan. The tests
exercise successful regeneration and blocked regeneration after failed inventory.

After repair: all 88 Python standard-library tests pass, example workbench CLI
exits 0, and `git diff --check` passes. Only authored temporary directories were
used. No MO2 profile, user mod, plugin, or save was edited. This is not native
Windows, deployed manager, or Skyrim game acceptance. Pending traversal PR #15
is separate and was not included or changed.

## Resumed current-main verification

Reconciled this existing pass with main `2a4717dd503567801be2245942e3dde91a4f7fe1`
without duplicating its header-diagnostics, evidence, or input-reading changes.
The final combined suite runs 134 tests: 133 pass and one Windows-only test is
skipped on Linux. The example CLI exits 0 and the original three repeated-scan
regressions pass. Native MO2 and Skyrim acceptance remains unclaimed.
