"""Read-only loose-file overlap inventory. No archive parsing or deployment."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys


def audit(roots, *, max_entries=20000, max_directories=5000):
    """Roots are hypothetical low-to-high priority Data trees, never installed state."""
    if not roots or len(roots) > 128:
        raise ValueError("supply 1 to 128 roots")
    if type(max_entries) is not int or max_entries < 1:
        raise ValueError("max_entries must be positive")
    if type(max_directories) is not int or max_directories < 1:
        raise ValueError("max_directories must be positive")
    files, errors, seen_roots = {}, [], set()
    entries_seen = directories_seen = 0
    exhausted = False

    def error(code, root, path=""):
        errors.append({"code": code, "root_index": root, "path": path})

    for root_index, raw_root in enumerate(roots):
        root = Path(raw_root)
        try:
            # Reject aliases and nesting so one mod's tree cannot count as two mods.
            canonical = root.resolve(strict=True)
            if root.is_symlink():
                error("root-symlink", root_index)
                continue
            if any(canonical == old or canonical in old.parents or old in canonical.parents
                   for old in seen_roots):
                error("overlapping-root", root_index)
                continue
            seen_roots.add(canonical)
            if not canonical.is_dir():
                error("root-not-directory", root_index)
                continue
        except (OSError, RuntimeError):
            error("root-unreadable", root_index)
            continue
        stack = [(canonical, "")]
        while stack and not exhausted:
            directory, relative = stack.pop()
            directories_seen += 1
            if directories_seen > max_directories:
                error("directory-limit", root_index, relative)
                exhausted = True
                break
            try:
                # Do not follow a directory swapped to a link after discovery.
                if directory.is_symlink() or not directory.resolve().is_relative_to(canonical):
                    error("directory-link-or-escape", root_index, relative)
                    continue
                with os.scandir(directory) as listing:
                    for entry in listing:
                        entries_seen += 1
                        if entries_seen > max_entries:
                            error("entry-limit", root_index, relative)
                            exhausted = True
                            break
                        path = f"{relative}/{entry.name}" if relative else entry.name
                        try:
                            info = entry.stat(follow_symlinks=False)
                            if stat.S_ISLNK(info.st_mode):
                                error("symlink-skipped", root_index, path)
                            elif stat.S_ISDIR(info.st_mode):
                                stack.append((Path(entry.path), path))
                            elif stat.S_ISREG(info.st_mode):
                                files.setdefault(path.casefold(), []).append(
                                    {"root_index": root_index, "path": path, "size_bytes": info.st_size})
                            else:
                                error("special-file-skipped", root_index, path)
                        except (OSError, RuntimeError):
                            error("entry-unreadable", root_index, path)
            except (OSError, RuntimeError):
                error("directory-unreadable", root_index, relative)
        if exhausted:
            break
    overlaps = []
    for key, providers in sorted(files.items()):
        if len(providers) < 2:
            continue
        providers.sort(key=lambda p: (p["root_index"], p["path"]))
        duplicate_in_root = len({p["root_index"] for p in providers}) != len(providers)
        overlaps.append({"path_key": key, "providers": providers,
                         "kind": "ambiguous-case-collision" if duplicate_in_root else "cross-root-overlap",
                         "proposed_winner_root": None if duplicate_in_root or errors else providers[-1]["root_index"],
                         "content_equivalence": "not-tested"})
    errors.sort(key=lambda e: (e["root_index"], e["path"], e["code"]))
    complete = not errors
    return {"schema_version": 1, "scope": "supplied-loose-data-trees-only", "complete": complete,
            "status": "incomplete" if not complete else ("overlaps-found" if overlaps else "no-loose-overlaps"),
            "game_verified": False, "applied": False, "root_count": len(roots),
            "file_count": sum(map(len, files.values())), "overlaps": overlaps, "errors": errors,
            "precedence": "hypothetical-input-order-low-to-high; not verified manager state"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", help="loose Data trees in hypothetical low-to-high priority")
    args = parser.parse_args(argv)
    try:
        report = audit(args.roots)
    except (ValueError, OSError):
        print(json.dumps({"status": "invalid-input"}), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 2 if not report["complete"] else (1 if report["overlaps"] else 0)


if __name__ == "__main__":
    sys.exit(main())
