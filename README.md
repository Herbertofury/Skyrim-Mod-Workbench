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
