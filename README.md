# Skyrim Mod Workbench

Dedicated general Skyrim SE mod creation, diagnosis, repair and management workbench. **Early read-only foundation, not a finished editor or manager.**

## Runnable foundation

Python 3.11+; standard library only, no installation or game files needed:

```sh
python workbench.py examples/plugins.json
python -m unittest discover -s tests -v
```

The CLI validates a supplied JSON plugin inventory and detects missing/disabled masters, masters loaded after their dependents, and cycles. Plugin identity is case-insensitive. Disabled dependents are excluded. Duplicate keys/names, invalid types and path-shaped names fail closed. Input is bounded to 2 MB / 4096 plugins. By default it never writes files, launches tools, accesses the network or changes a game/profile.

Exit codes: `0` no dependency issue in the supplied manifest; `1` diagnostic findings; `2` invalid/unreadable input. Array order is the proposed load order. The example uses invented author-owned fixture names, not a real game inventory. `game_verified: false` is always explicit: this does not parse ESP/ESM binaries, discover implicit official masters, understand ESL limits, sort with LOOT or prove the game will load. JSON output includes supplied plugin names; review it before sharing.

## Scope and reuse

[Wiki](https://github.com/Herbertofury/Skyrim-Mod-Workbench/wiki) · [24-tool primary-source research](https://github.com/Herbertofury/Skyrim-Animation-Research/wiki/Skyrim-Tooling-and-Integration)

This is the dedicated application project; Skyrim-Animation-Research remains the research hub. Coordinate manager integration with [Modhunter](https://github.com/Herbertofury/Modhunter), without replacing or duplicating its deployment/VFS responsibilities. No private code is copied. No third-party tool is vendored, and no redistribution license clearance is implied.

## Backlog with acceptance gates

- [x] Read-only manifest validator, deterministic dependency diagnostics, CLI and regression tests.
- [ ] Import actual manager/plugin metadata through a maintained, licensed upstream adapter; verify master lists against xEdit/Mutagen output and actual profile state.
- [ ] Creation workflows: supported Creation Kit / patcher / mesh / animation handoffs with pinned versions and isolated outputs.
- [ ] Repair planning: precise diagnostics, proposed changes, copies/backups, transactional writes and rollback tests before any apply feature.
- [ ] UI: dense readable records, keyboard navigation, status/access distinctions, latency/memory measurement.
- [ ] Native Windows + Skyrim acceptance on permitted fixtures; actual game load/save/reload and playback evidence where applicable.

Do not interpret manifest-only success as a healthy install or automatically clean a save. Preserve originals and failures. No credentials, personal saves, private/paywalled fixtures or Bethesda assets in this public repository. New integrations require exact license/dependency review and target-project correctness/performance comparison before promotion.

## Dependency repair preview

`python workbench.py inventory.json --plan` adds a non-mutating candidate order and zero-based move list. It refuses to propose a partial repair if any enabled plugin has a missing/disabled master or a dependency cycle. It never enables a plugin, removes a plugin or writes a load-order file. Disabled entries retain their slots; available nodes use their original order as the deterministic tie-breaker. Already valid dependency orders are unchanged.

The plan includes a SHA-256 of the canonical validated manifest as its basis identity, not an authorization token or proof of actual file contents. Input changes invalidate that identity. CLI exit status still describes the original input: a preview does not turn unresolved findings into success.

**This is not LOOT sorting or an executable repair plan.** Plugin type ordering, implicit official plugins, load limits, user rules, masterlist constraints, record conflicts and real manager state are outside this manifest-only preview. A future supported adapter must revalidate all these before any apply capability. No apply capability exists. Regression tests cover all 120 permutations of a five-node dependency graph, cycles, missing/disabled masters, stable order, disabled slots, basis identity and a 2,000-node reverse chain.

## Read-only loose-asset overlap audit

```sh
python asset_audit.py /path/to/mod-a/Data /path/to/mod-b/Data
```

This separate CLI inventories actual supplied loose-file trees (metadata only, no file content reads) and groups case-insensitive relative-path overlaps. Input order is a **hypothetical** low-to-high precedence, not an assertion about the active MO2/Vortex profile. Reports list providers, sizes and proposed winning root indexes. Equal sizes never imply identical content. Case collisions within one root are ambiguous and have no proposed winner. Any incomplete audit suppresses all proposed winners.

Roots must be distinct non-nested directories. Symlinks/special files, inaccessible entries and resource limits produce an explicit incomplete result, never a clean bill of health. Default global limits are 20,000 entries, 5,000 directories and 128 roots. Exit codes are `0` complete/no overlaps, `1` complete/overlaps and `2` invalid or incomplete. Output omits absolute root paths but includes relative asset names: review before sharing. Stop external modifications while inventorying; this is not a transactional filesystem snapshot or hardened scanner against concurrent malicious changes.

No deployment, deletion, copying, archive inspection, content-equivalence check or repair is performed. BSA/BA2 members, plugin-record overrides, manager VFS state, game load rules and native visual correctness require supported upstream adapters and separate acceptance. A proposed loose-file winner is not a recommendation to overwrite anything.

### Optional bounded content comparison

`python asset_audit.py --compare-content mod-a/Data mod-b/Data` explicitly opts into reading **overlapping files only** and reporting SHA-256 fingerprints. It distinguishes `sha256-equal`, `different` and `unknown`; equal sizes alone are never considered equal contents. The default audit remains metadata-only.

Comparison reads at most 16 MiB per provider and 128 MiB total, in 64 KiB chunks. Larger/unreadable/changed files leave an incomplete report with unknown equivalence and no proposed winners. Incomplete inventories skip comparison entirely. Symlinks/reparse points are refused and before/after file identity checks detect ordinary concurrent modifications. This remains a best-effort snapshot, not protection against hostile concurrent filesystem manipulation; stop external edits first. Digests do not imply mod compatibility or permission to redistribute. No data is uploaded, deleted or changed, and there is no deduplication/apply action.

Platform note: [CPython #157671](https://github.com/python/cpython/issues/157671) documents Windows stat/fstat ctime differences. The comparator matches common identity fields across APIs and checks ctime changes within each API separately; it does not remove the during-read change check. Initial Windows 3.13 CI exposed this issue before merge.

## Offline readable reports

Add `--html` to either CLI to emit a standalone, script-free HTML report to standard output. For example:

```sh
python workbench.py examples/plugins.json --plan --html > report.html
python asset_audit.py mod-a/Data mod-b/Data --compare-content --html > assets.html
```

The shell creates the chosen HTML report file; the application still does not modify its inputs. An explicit --save-report separately creates its requested evidence file. Exit codes are unchanged, including findings/incomplete results, so a nonzero status can still accompany a useful report. HTML output contains readable finding/provider tables, keyboard-accessible expandable evidence and the complete original JSON. Dynamic strings are escaped; a restrictive content-security policy disallows scripts/network requests. No remote fonts, telemetry, external assets or apply controls exist. Relative filenames and plugin names may be personal: keep reports local unless intentionally shared. HTML structure/escaping and CLI regression tests are automated; visual/native-game acceptance remains separate.

## Explicit evidence snapshots

Both analysis CLIs accept `--save-report NEW_FILE` to save the complete JSON report, including failures and incomplete evidence, in a SHA-256 envelope. Saving is opt-in, create-only and never overwrites an existing receipt or backup. The temporary file is flushed/fsynced before atomic same-directory hard-link publication; a concurrent existing destination wins safely. Filesystems without hard-link support fail without replacing anything.

`python evidence.py receipt.json` verifies bounded input, strict envelope/version and checksum, then returns the saved report explicitly labeled **historical**, not current-file or authenticity verification. A checksum detects corruption, not a malicious party who can rewrite both data and digest. Reports include names/digests, so keep them private unless intentionally shared.

Save receipts are emitted to stderr, leaving JSON/HTML stdout intact. Save failure makes the analysis exit `2` while preserving its useful report output. A POSIX directory-fsync failure reports `published: true` with durability **unconfirmed** and exit `2`; do not blindly retry as if no file exists. Windows reports directory fsync unsupported, while confirming the file flush. No platform-independent power-loss guarantee is claimed. No input/game files are modified; only the explicitly requested new evidence file is published.

If temporary cleanup fails after publication, the receipt still reports `published: true`, includes `temporary_removed: false` and exits `2`. The saved evidence is retained; a temporary hard-link may remain for later manual cleanup.

## MO2 profile export adapter

```sh
python mo2_profile.py /path/to/profile/modlist.txt
python mo2_profile.py /path/to/profile/modlist.txt --html > mo2-export.html
```

This read-only adapter imports an actual explicitly selected UTF-8/BOM MO2 `modlist.txt`, including CRLF, comments, enabled/disabled/foreign markers and source-byte SHA-256. It reverses the serialized order into low-to-high exported priority, retains original line numbers and reports regular/separator/foreign/overwrite-reference categories. It does not discover profiles, read account settings, toggle mods or write to MO2. No private implementation was reused.

Format behavior was checked against maintained upstream [Profile::doWriteModlist / refreshModStatus at 4ba22f0](https://github.com/ModOrganizer2/modorganizer/blob/4ba22f0d8b6f9e08e44008b8395cd774551b4ebe/src/profile.cpp) and [separator classification](https://github.com/ModOrganizer2/modorganizer/blob/4ba22f0d8b6f9e08e44008b8395cd774551b4ebe/src/modinfo.cpp). This is a narrow text-format adapter, not copied MO2 code or a replacement for its plugin/VFS implementation. Its strict subset deliberately rejects legacy unmarked rows, malformed/path-shaped names and case-insensitive duplicates instead of silently repairing them. Bounds: 2 MB, 4,096 mods and 4,096 characters per entry.

**An export is not live manager state.** MO2 reconciles installed metadata and missing/new mods, including automatic-priority entries. This adapter does not reconstruct that state, foreign files, overwrite contents, archives or plugin load order. `enabled_regular_names_low_to_high` is an inventory aid, not deployable instructions or proof of actual asset winners. Name-based separator classification is a format hint only. Tests use authored fixtures matching upstream format; acceptance against a populated user profile and native MO2 remains pending.

### Reconcile a profile export with installed mod directories

`python mo2_profile.py profile/modlist.txt --mods-directory /path/to/MO2/mods --html > reconciliation.html` reads only the explicit directory's direct children. It reports missing enabled/inactive entries, directories absent from the export, case ambiguities and unreadable/link/reparse entries. Matching is case-insensitive; foreign/overwrite entries remain outside regular-mod scope rather than being falsely declared missing. Non-directory metadata is counted but not opened.

An incomplete directory inventory produces unknown states, never invented missing-mod conclusions. Exit codes: `0` reconciled within this narrow scope, `1` findings, `2` incomplete/unreadable/invalid; exporting without reconciliation keeps its existing behavior. Inventory is capped at 8,192 direct entries. This is not live profile selection, metadata validation, asset deployment or game acceptance. It does not automatically add, enable, remove or repair any mod. Stop external changes for a consistent observation; outputs omit absolute roots but retain mod names.

### Audit loose files selected by an MO2 export

`python mo2_profile.py profile/modlist.txt --mods-directory /path/to/MO2/mods --audit-assets --html > profile-assets.html`

This explicitly composes reconciliation with the existing bounded loose-file auditor: only enabled regular directories are scanned, in low-to-high **exported** order. Root indexes map back to mod names and export priorities. Disabled mods, separators, foreign entries and overwrite references are excluded. Incomplete reconciliation, unresolved enabled directories or more than 128 enabled roots block scanning entirely; no partial substitute selection is silently audited. An empty enabled selection is explicitly reported, not treated as a completed filesystem audit.

Add `--compare-content` only when bounded content reads are wanted; it requires `--audit-assets`. Default scanning remains metadata-only. Existing global inventory/content limits and incomplete-result winner suppression apply. CLI exits `2` for blocked/incomplete audits and `1` for overlaps or reconciliation findings. Reports retain reconciliation, per-root mappings and full asset evidence together.

This does **not** emulate MO2 VFS: it inventories on-disk loose files, including manager metadata files if present. Hidden-file rules, archive priority, foreign/overwrite contents and active profile state remain unverified. Export-derived proposed winners are hypotheses, not deployment or repair instructions. Stop external changes during observation. No files are changed and no game/native acceptance is claimed.

## Supported external tool control: first adapter

```sh
python toolchain.py loot /path/to/LOOT.exe
# Review preview, verify this is your trusted official LOOT binary, then explicitly opt in:
python toolchain.py loot /path/to/LOOT.exe --execute --expected-sha256 SHA_FROM_PREVIEW --acknowledge-tool-side-effects
```

The implemented LOOT adapter launches an explicitly selected installed executable with the documented `--game=Skyrim Special Edition` argument. Preview is the default and does not run anything. Execution requires both a matching SHA-256 and acknowledgement that the external tool may write settings/logs or perform configured network activity. No executable discovery, installation, update, download, elevation, shell, arbitrary arguments, `--game-path` setting override or `--auto-sort` is supplied. Native Windows EXE and Linux ELF formats are supported, not scripts, Flatpak URIs or Wine wrappers. Fingerprinting is bounded to 512 MiB and rechecked before launch; a fingerprint is **not** publisher authentication or a hostile-race guarantee.

A successful receipt says only `process_started`, not tool readiness, selected profile, completed analysis or game acceptance. An existing Windows LOOT instance can simply focus its window and ignore arguments. Output is not parsed and the launcher does not manage the GUI lifecycle. Review the tool UI and its own diagnostics. Subsequent manual GUI actions are outside the launch receipt. Preview/receipt includes the explicit executable path: keep it private if personal.

Contract verified against LOOT [initialisation documentation](https://github.com/loot/loot/blob/03f22e99f037c08778731319a6bae0276e7464a0/docs/app/usage/initialisation.rst) and [Qt entry point](https://github.com/loot/loot/blob/03f22e99f037c08778731319a6bae0276e7464a0/src/gui/qt/main.cpp). Upstream `--auto-sort` sorts **and applies** load order then quits; it is deliberately not disguised as read-only analysis. Future apply integration needs validated backups, output verification and recovery contracts. LOOT is GPL-3.0; no upstream code or binaries are vendored here. Adapter tests use authored non-executable byte fixtures and mocked process creation, not a native LOOT acceptance test.

### Toolchain roadmap and non-equivalence boundaries

- **xEdit/SSEEdit:** maintained source [0f3f6fb](https://github.com/TES5Edit/TES5Edit/blob/0f3f6fb2181783cad9c0cd4106ad0ff79ae7bb23/xEdit/xeInit.pas) supports SSE/view modes; [official Tome](https://tes5edit.github.io/docs/2-overview.html) documents switches and GUI workflows. `-DontCache` controls reference caching; quick-auto-clean writes plugin changes. Current source LICENSE is MPL-2.0. Next candidate is explicit view-mode launch; full unattended editing is **not implemented or inferred** from launch switches.
- **ESLifier:** [upstream](https://github.com/MaskPlague/ESLifier) warns its README may be outdated. Its application entry point is GUI-based, not verified full CLI. Upstream advises selecting MO2 mode inside ESLifier, **not launching through MO2**; keep generated output separate instead of copying over originals. Scanning can write extracted caches and FormID compaction can invalidate saves. No explicit root license was identified in this review: no vendoring/redistribution clearance claimed. Integration remains research-only.
- **Other editors/creation/management tools:** evaluate exact supported operations, runtime compatibility, licenses, changed files and acceptance individually. Existing research matrix is not proof of “best” for a user's installation. The goal is integrated control where upstream actually supports it, not invented universal CLI coverage.

## Real plugin headers and migration impact inventory

```sh
python plugin_headers.py /staging/PatchA.esp /staging/PatchB.esp --master OldMaster.esm
```

The read-only adapter reads the actual TES4 header from each explicitly supplied plugin, extracts paired MAST/DATA dependencies, ESM/ESL flags, form version and HEDR declarations, and fingerprints **header bytes only**. It traces direct and transitive dependents of an explicitly named master within that supplied set. It does not assume those are every installed mod or that supplied order is the active load order. Missing/malformed/duplicate inputs leave an explicitly incomplete report instead of quietly disappearing.

Bounds: 4,096 explicit files, 16 MiB per TES4 payload, 64 MiB aggregate attempted header bytes (failed parsing also consumes budget). Regular files only; symlink/reparse inputs refused. Standard 24-byte record headers and ordinary six-byte subrecord headers are supported. Compressed TES4 and extended `XXXX` header subrecords are rejected, not guessed. Header-only scanning leaves record bodies unread and unvalidated. Stop concurrent file edits. Header fields follow [xEdit Skyrim definitions](https://github.com/TES5Edit/TES5Edit/blob/0f3f6fb2181783cad9c0cd4106ad0ff79ae7bb23/Core/wbDefinitionsTES5.pas); implementation is independent, no upstream code copied.

**Flags and declared counts are not ESL eligibility.** Every inventory explicitly marks ESL eligibility unassessed. Record-ID ranges, overrides, new CELL records, dependent plugins, scripts/SEQ/assets, runtime support and save compatibility require deeper supported-tool inspection. Setting an ESL flag or compacting FormIDs based on this header report alone is not supported. All tests currently use authored binary fixtures, not user plugins or native acceptance.

### Bruma migration and ESLification acceptance milestones

The requested end state is discover affected mods, build a backed-up migration preview, edit verified master/record references through supported tooling, save separate outputs, reopen and validate in xEdit/compatible Creation Kit plus evaluated addon, and validate in game. The header inventory delivers the first actual-file dependency-discovery step only. No automatic migration, cleaning, compaction, original replacement or deployment exists yet.

For Bruma specifically, verify the actual old archive/plugin hashes and versions (the recalled 1.6.7 version is not independently established), obtain the exact new Bruma/BSAssets manifests, and compare record identities before proposing mappings. Do not equate renamed/removed masters with interchangeable FormIDs. Bruma 2.0's official release warning requires a **new save** and says most submods require updates; do not promise migration of existing saves. xEdit Clean Masters removes unused dependencies, not reference migration. CK/addon version compatibility and licenses must be verified independently; newest is not automatically compatible.

For ESLification, separate no-compaction flag candidates from compaction candidates; retain originals and dependent/reference mapping evidence. Require supported-tool validation and save-compatibility review before writing isolated outputs, then reopen those outputs and test the actual game. Zero-error native acceptance is a target, never an inference from header flags or fixture tests. No private plugin data is bundled or published by this repository.

### xEdit / SSEEdit plugin-view adapter

```sh
python toolchain.py xedit-view /path/to/SSEEdit.exe
python toolchain.py xedit-view /path/to/SSEEdit.exe --execute --expected-sha256 SHA_FROM_PREVIEW --acknowledge-tool-side-effects
```

This second adapter builds the source-verified arguments `-sse -plugins -view -DontCache`. In the pinned upstream [mode selection/initialisation](https://github.com/TES5Edit/TES5Edit/blob/0f3f6fb2181783cad9c0cd4106ad0ff79ae7bb23/xEdit/xeInit.pas), explicit command-line modes precede executable-name detection; view mode sets editing disallowed and saving disabled. `-DontCache` disables reference caching. Settings/log side effects can still occur, so this is not a general write-free sandbox.

Preview accepts an explicitly selected Windows EXE on either host; actual execution requires native Windows, the reviewed executable hash and side-effect acknowledgement. It never adds scripts, quick-auto-clean, load-order edits, master renames, ESL flags, FormID compaction, arbitrary switches or a Wine wrapper. xEdit discovers configured game paths and presents its plugin-selection UI; no active MO2 VFS/profile association is inferred. Installation/version authenticity, actual view-mode behavior and game acceptance must be checked on the user's native setup. Launch success alone never marks analysis complete. Automated tests cover command construction and platform/execution gates with byte fixtures and mocked process creation, not actual xEdit execution.

### Integration knowledge and user-directed decisions

Compatibility research is advisory evidence, not an automatic veto based on speculation. Future Bruma/ESL workflows should retain source, version, confidence, observed failures and the user's override decision without silently disabling authorized updates. Explicit input-integrity checks and destructive-operation safeguards remain separate: an unreadable file or unknown FormID mapping cannot truthfully be reported as a successful repair.

The planned Bethesda knowledge store should preserve compact searchable tool/version/license/format/operation evidence and refresh provenance. SQLite and Rust/rusqlite are candidates to benchmark against representative ingestion, search, durable-write/recovery and application workloads; neither is declared fastest or selected without measurement. CKPE integration must match the exact Creation Kit build and native CPU/runtime constraints. These database and CKPE items are roadmap work, not implemented capabilities in this adapter.

### Save plugin-header and MO2 evidence

Both commands can now persist the same create-only, checksummed report envelope
as manifest and loose-asset diagnostics:

```console
python plugin_headers.py Patch.esp --master Old.esm --save-report headers.json
python mo2_profile.py modlist.txt --mods-directory mods --save-report profile.json
python evidence.py profile.json
```

`--save-report` is opt-in and writes only the named new report, never a plugin,
modlist, existing report, or backup. It also works with MO2 `--html`: HTML goes to
stdout, the save receipt to stderr, and the complete machine-readable evidence
to the new file. Incomplete header inventories and reconciliation findings can
be saved without claiming success. Existing diagnostic exit codes remain; save
failure or unconfirmed durability returns 2. Integrity verification is historical,
not proof that current files or the native game match the saved report.

### Readable plugin header evidence

`python plugin_headers.py Explicit.esp Another.esp --master OldMaster.esm --html > headers.html`

The optional offline, script-free HTML view presents declared masters, header flags/counts/hashes, rejected inputs and direct/transitive dependents. JSON remains the default. Add `--save-report NEW_FILE` to save the same create-only integrity envelope; its receipt stays on stderr, separate from HTML stdout. Incomplete inputs or save warnings still exit2. Header flags/counts do not establish ESL eligibility, FormID compatibility or game acceptance. This scans only explicit files, not an entire manager installation; nothing is edited or deployed.

### Review saved evidence without rescanning

`python evidence.py saved-report.json --html > saved-report.html`

Verifies the existing snapshot checksum before generating an offline, script-free view with an explicit **historical snapshot** notice. It does not rescan files, establish authenticity, or confirm current manager/game state. JSON verification remains the default. Invalid evidence produces no HTML and exits2; an integrity-valid report with an unsupported presentation shape produces a separate `unsupported-report-view` diagnostic rather than a traceback or misleading current-status claim. The saved evidence is never modified.
