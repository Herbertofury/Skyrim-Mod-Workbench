---
name: plugin-migration-acceptance
description: Plan and validate Skyrim plugin master migration and ESL workflows using actual dependency evidence, supported tool adapters, isolated outputs and separate native acceptance without inventing editing capabilities.
---

# Plugin migration acceptance

Use for Bruma/master updates, ESL candidate analysis, plugin diagnostics and native-tool integration. Read `README.md`, root `AGENTS.md`, the actual CLI help and relevant modules/tests before action. The current Python workbench is read-only except explicitly gated external tool launching; the desired future editor is not already implemented.

## Establish actual state

1. Identify the authorized game/runtime and manager profile. Use actual manifest/header/profile evidence, not a guessed active VFS. Record input hashes, mod versions, enabled state, load order and exact tool versions. Keep originals, saves and personal paths private.
2. Use supported existing operations: `workbench.py` for supplied manifest dependencies, `plugin_headers.py` for real header inventory, `mo2_profile.py` for its documented profile evidence and `asset_audit.py` for loose-file overlap. Inspect each help/output contract first. Header lists are not full record/reference analysis; loose-file precedence is not plugin override semantics.
3. Distinguish incomplete/unreadable/unsupported evidence from a clean result. Do not equate same-size files with same content, missing masters with harmless renames, or proposed ordering with actual deployment.

## Migration preview before writes

For an old-to-new Bruma request, verify both real source versions/archive/plugin hashes and exact Bruma/BSAssets manifests. Treat the user's recalled version as a lead, not established identity. Inventory every dependent plugin, then obtain full record/reference evidence through maintained compatible tooling before mapping old to new forms.

A renamed master does not establish FormID equivalence. xEdit Clean Masters only removes unused dependencies; it is not reference migration. Official new-save warnings and submod compatibility remain explicit. Do not promise an existing-save conversion simply because files reopen.

Separate advisory compatibility warnings from hard evidence failures. Offer source/date/confidence and preserve the user's informed choice rather than blocking an update on speculation. Unknown mappings, failed output validation and unsupported operations cannot be reported as successful repairs.

## Tool and ESL boundaries

- The current `toolchain.py` xEdit view adapter previews pinned arguments and requires native Windows, matching reviewed executable hash and side-effect acknowledgement to execute. Launch/settings/log side effects are not a write-free sandbox; no arbitrary scripting/editing pipeline is implied.
- LOOT auto-sort applies load order. Do not label it read-only diagnostics or invoke it as a harmless verification step.
- Verify actual Creation Kit plus CKPE version/runtime compatibility before integration. A tool offering a GUI is not automatically a full CLI. Respect executable provenance and licensing; no unlicensed bundling.
- ESL candidates require separate no-compaction flag analysis and FormID-compaction analysis. For compaction, map dependents and saved references explicitly. Header flags or small record count alone do not prove save compatibility or zero-error eligibility.

## Future write acceptance

Only when a supported implementation and authorized scope exist: make verified backups, write separate staging outputs, retain exact mapping/change logs, reopen with independent supported tools, validate masters/references and compare intended versus incidental changes. Test interrupted/failed writes and rollback before original replacement or deployment. Keep xEdit, LOOT, CK/CKPE and manager adapters optional and independently testable.

Run `python -m unittest discover -s tests -v` and `python workbench.py examples/plugins.json` for the current foundation. Keep authored fixture passes separate from actual user-plugin tests. Final completion requires correct outputs, actual manager deployment identity and isolated-profile game verification where applicable. Report implementation, fixtures, native editor reopen, game load/save and publication separately; never certify no errors from launch success or synthetic tests.
