# Repository instructions

Read `.agents/athena/AGENTS-adapter.md` for the pinned shared engineering core.
Keep this file and nested instructions project-owned: setup, commands, constraints and acceptance belong here.

## Skyrim Mod Workbench local requirements

- This is a Skyrim SE mod creation/diagnosis/repair/management workbench, currently a read-only Python foundation. Preserve existing output contracts and explicit `game_verified: false` states. Fixture success is not Skyrim or Windows acceptance.
- Python 3.11+ standard library. Run `python -m unittest discover -s tests -v`; smoke-test `python workbench.py examples/plugins.json`. Read README.md and current CLI help for additional supported commands before using them.
- Keep xEdit, LOOT, Creation Kit/CKPE, ESL analysis and manager integrations behind explicit adapters. Do not turn optional tools into mandatory dependencies or infer a real CLI where an upstream only supports interactive use.
- Preserve originals, saves and last-good evidence. Write/apply capabilities require validated copies, backups, transactional recovery and rollback tests; diagnostic output alone is never permission to modify a profile.
- Never publish credentials, private/paywalled fixtures, personal saves or Bethesda assets. Check exact upstream licensing before vendoring or redistributing code/assets.
- Keep project-specific modding knowledge here or scoped documentation, not in Agent-Foundry's shared core. Coordinate VFS/deployment responsibilities with Modhunter; do not duplicate active implementation work.

## Project skill

Use `.agents/skills/plugin-migration-acceptance/SKILL.md` for Bruma/master migrations, ESL candidate analysis, xEdit/LOOT/CKPE integration and evidence review. It distinguishes implemented read-only operations from planned editing and native acceptance.

## Mandatory pre-release optimization gate

Before finalizing every release, follow the owner-mandated [Athena zero-loss pre-release optimization standard](https://github.com/Herbertofury/Athena/blob/main/guidance/PRE_RELEASE_OPTIMIZATION.md). Evaluate shrink-anything, fast-anything and rust-anything using reviewed pinned tools in isolated worktrees; run applicable passes, compare equivalent complete workloads, keep only independently verified improvements, restore rejected changes, and record per-tool evidence or explicit inapplicability/blockers. Never weaken tests, delete required content, force a Rust rewrite or regress functionality, quality, portability, compatibility, security or protected performance metrics. Data/documentation-only releases and existing native Rust paths require honest applicability decisions, not artificial ports. Existing local and pinned governance requirements remain intact.

## Mandatory CLI-first / non-interruptive execution

For every task, follow the owner-mandated [Athena CLI-first execution standard](https://github.com/Herbertofury/Athena/blob/main/guidance/CLI_FIRST_EXECUTION.md). Prefer fast official CLI/headless commands, supported APIs/SDKs/connectors and tested local automation. If a required application has no usable structured interface, discover or build a reviewed [CLI-Anything](https://github.com/HKUDS/CLI-Anything) harness over the real supported backend (or a native command surface for first-party code). Use isolated browser/renderer/test sessions for necessary UI proof. Never take over the user's active desktop, mouse, keyboard, focus or browser profile without explicit authorization for unavoidable foreground interaction. Preserve real runtime acceptance, data, permissions, feature parity and portable mode. Record reusable command coverage and unresolved gaps; no fake CLI parity or unnecessary release delay.
