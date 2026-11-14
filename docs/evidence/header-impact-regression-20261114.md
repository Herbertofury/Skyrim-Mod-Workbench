# Header impact traversal regression (2026-11-14)

Base: `a42ed68214feedc8837714399ebe464bd8ce9490`.
Scope: `plugin_headers.inventory` transitive impact discovery only. No file reading,
parsing, writes, tool execution, report schema or native acceptance change.

## Reproduced defect

A reverse-ordered dependency chain forces the previous repeated full-inventory
scan to revisit most plugins for every newly reached dependency. At the supported
4,096-plugin bound, an instrumented authored-header fixture counted **25,188,352**
name-normalization calls. The new regression rejects more than **32,768** calls
(eight per supplied plugin), without relying on machine timing.

Before the implementation change, the focused header suite ran nine tests and
failed exactly this assertion:

```text
FAIL: test_reverse_chain_impact_has_bounded_name_normalization
AssertionError: 25188352 not less than or equal to 32768
Ran 9 tests
FAILED (failures=1)
```

## Repair and verification

Build reverse master-to-dependent adjacency once, then traverse reachable edges
with a queue and visited set. Cycles terminate and diamond dependencies are not
reported twice. Direct dependents and transitive results retain supplied input
order and original filename spelling. The requested master stays excluded from
transitive output, even if it participates in a cycle.

New deterministic tests cover the maximum-size reverse chain and a mixed-case
fan-out/diamond/cycle graph with an unrelated plugin. The existing actual-file
fixture, incomplete input, aggregate byte budget and CLI tests remain unchanged.

After repair:

```text
python -m unittest discover -s tests -v
Ran 84 tests
OK
```

This is synthetic regression/operation-count evidence for the actual inventory
algorithm, not a user-mod/native-game benchmark. It does not establish game
compatibility, record migration correctness, ESL eligibility or whole-app speed.
`game_verified`, `applied`, incomplete-scope and record-mapping flags retain
existing semantics. Original plugins remain untouched.
