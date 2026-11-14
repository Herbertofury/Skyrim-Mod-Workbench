# Skyrim Mod Workbench

Dedicated general Skyrim SE mod creation, diagnosis, repair and management workbench. **Early read-only foundation, not a finished editor or manager.**

## Runnable foundation

Python 3.11+; standard library only, no installation or game files needed:

```sh
python workbench.py examples/plugins.json
python -m unittest discover -s tests -v
```

The CLI validates a supplied JSON plugin inventory and detects missing/disabled masters, masters loaded after their dependents, and cycles. Plugin identity is case-insensitive. Disabled dependents are excluded. Duplicate keys/names, invalid types and path-shaped names fail closed. Input is bounded to 2 MB / 4096 plugins. It never writes files, launches tools, accesses the network or changes a game/profile.

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

The shell creates the chosen report file; the application still does not modify its inputs. Exit codes are unchanged, including findings/incomplete results, so a nonzero status can still accompany a useful report. HTML output contains readable finding/provider tables, keyboard-accessible expandable evidence and the complete original JSON. Dynamic strings are escaped; a restrictive content-security policy disallows scripts/network requests. No remote fonts, telemetry, external assets or apply controls exist. Relative filenames and plugin names may be personal: keep reports local unless intentionally shared. HTML structure/escaping and CLI regression tests are automated; visual/native-game acceptance remains separate.
