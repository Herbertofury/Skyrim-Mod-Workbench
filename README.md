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
