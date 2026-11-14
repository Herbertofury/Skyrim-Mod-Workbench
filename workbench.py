"""Read-only, dependency-free diagnostics for explicitly supplied plugin manifests."""
import argparse
import hashlib
import heapq
import json
import re
import sys

MAX_BYTES = 2_000_000
MAX_PLUGINS = 4096
NAME = re.compile(r"[^/\\\x00-\x1f:]+\.(?:esm|esp|esl)", re.IGNORECASE)


def plugin_name(value):
    if not isinstance(value, str) or value != value.strip() or not NAME.fullmatch(value):
        raise ValueError("plugin names must be bare .esm/.esp/.esl names, without paths")
    return value.casefold()


def validate(data):
    if not isinstance(data, dict) or set(data) != {"schema_version", "plugins"}:
        raise ValueError("expected only schema_version and plugins")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("unsupported schema_version")
    plugins = data["plugins"]
    if not isinstance(plugins, list) or len(plugins) > MAX_PLUGINS:
        raise ValueError("plugins must be a bounded list")
    names = set()
    for item in plugins:
        if not isinstance(item, dict) or set(item) != {"name", "enabled", "masters"}:
            raise ValueError("each plugin requires only name, enabled and masters")
        key = plugin_name(item["name"])
        if key in names:
            raise ValueError("duplicate case-insensitive plugin name")
        names.add(key)
        if type(item["enabled"]) is not bool:
            raise ValueError("enabled must be boolean")
        masters = item["masters"]
        if not isinstance(masters, list) or len(masters) > 4096:
            raise ValueError("masters must be a bounded list")
        keys = [plugin_name(m) for m in masters]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate case-insensitive master")
    return plugins


def diagnose(data):
    plugins = validate(data)
    index = {p["name"].casefold(): (i, p) for i, p in enumerate(plugins)}
    findings = []
    edges = {}
    for i, p in enumerate(plugins):
        if not p["enabled"]:
            continue
        key = p["name"].casefold()
        edges[key] = []
        for master in p["masters"]:
            target = index.get(master.casefold())
            code = None
            if target is None:
                code = "missing-master"
            elif not target[1]["enabled"]:
                code = "disabled-master"
            else:
                edges[key].append(master.casefold())
                if target[0] >= i:
                    code = "master-not-before-dependent"
            if code:
                findings.append({"code": code, "plugin": p["name"], "master": master})
    # Iterative DFS avoids recursion failure on long but valid dependency chains.
    color = {}
    for start in edges:
        if color.get(start):
            continue
        color[start] = 1
        stack = [(start, iter(edges[start]))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                color[node] = 2
                stack.pop()
            elif color.get(child) == 1:
                findings.append({"code": "dependency-cycle", "plugin": index[node][1]["name"],
                                 "master": index[child][1]["name"]})
            elif not color.get(child):
                color[child] = 1
                stack.append((child, iter(edges[child])))
    return {"schema_version": 1, "scope": "supplied-manifest-only", "game_verified": False,
            "plugin_count": len(plugins), "findings": findings,
            "status": "issues-found" if findings else "no-manifest-dependency-issues"}



def dependency_plan(data):
    """Preview only: no LOOT rules, plugin type ordering, or game validity implied."""
    report = diagnose(data)
    plugins = data["plugins"]
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=True).encode()).hexdigest()
    blockers = [f for f in report["findings"] if f["code"] != "master-not-before-dependent"]
    plan = {"status": "blocked" if blockers else "preview", "applied": False,
            "basis_sha256": digest, "scope": "manifest-master-dependencies-only",
            "requires_external_validation": True, "blockers": blockers,
            "candidate_order": None, "moves": []}
    if blockers:
        return plan
    active = {p["name"].casefold(): i for i, p in enumerate(plugins) if p["enabled"]}
    dependents = {key: [] for key in active}
    indegree = {key: len(plugins[i]["masters"]) for key, i in active.items()}
    for key, i in active.items():
        for master in plugins[i]["masters"]:
            dependents[master.casefold()].append(key)
    ready = [(active[key], key) for key in active if indegree[key] == 0]
    heapq.heapify(ready)
    ordered = []
    while ready:
        _, key = heapq.heappop(ready)
        ordered.append(plugins[active[key]])
        for child in dependents[key]:
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(ready, (active[child], child))
    # Defense in depth: never offer a partial order if cycle detection changes.
    if len(ordered) != len(active):
        plan["status"] = "blocked"
        plan["blockers"] = [{"code": "incomplete-dependency-order"}]
        return plan
    iterator = iter(ordered)
    candidate = [next(iterator) if p["enabled"] else p for p in plugins]
    plan["candidate_order"] = [p["name"] for p in candidate]
    for position, p in enumerate(candidate):
        if p["enabled"] and active[p["name"].casefold()] != position:
            plan["moves"].append({"plugin": p["name"], "from_index": active[p["name"].casefold()],
                                  "to_index": position})
    if not plan["moves"]:
        plan["status"] = "no-dependency-reorder-needed"
    return plan


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="UTF-8 JSON inventory; read only, never a game directory")
    parser.add_argument("--plan", action="store_true", help="preview a dependency-only reorder; never apply")
    parser.add_argument("--html", action="store_true", help="emit an offline HTML report to stdout")
    parser.add_argument("--save-report", metavar="NEW_FILE", help="explicitly save a create-only evidence snapshot")
    args = parser.parse_args(argv)
    try:
        with open(args.manifest, "rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("manifest exceeds byte limit")
        data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object)
        result = diagnose(data)
        if args.plan:
            result["plan"] = dependency_plan(data)
    except (OSError, ValueError, RecursionError) as error:
        # No raw input or filesystem path in default diagnostic output.
        print(json.dumps({"status": "invalid-input", "error_type": type(error).__name__}), file=sys.stderr)
        return 2
    save_warning = False
    if args.save_report:
        from evidence import save_cli_report
        save_warning = save_cli_report(result, args.save_report)
    if args.html:
        from report_html import render_report
        print(render_report(result), end="")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    return 2 if save_warning else (1 if result["findings"] else 0)


if __name__ == "__main__":
    sys.exit(main())
