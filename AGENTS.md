# Repository instructions

Read `.agents/foundry/AGENTS-adapter.md` for the pinned shared engineering core.
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
