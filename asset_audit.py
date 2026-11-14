"""Read-only loose-file overlap inventory. No archive parsing or deployment."""
import argparse
import hashlib
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
            root_info = root.lstat()
            if stat.S_ISLNK(root_info.st_mode):
                error("root-symlink", root_index)
                continue
            if getattr(root_info, "st_file_attributes", 0) & 0x400:
                error("root-reparse-point", root_index)
                continue
            canonical = root.resolve(strict=True)
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
                info = directory.lstat()
                if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
                        or not directory.resolve().is_relative_to(canonical)):
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
                            elif getattr(info, "st_file_attributes", 0) & 0x400:
                                error("reparse-point-skipped", root_index, path)
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



def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _version(info):
    # ctime semantics differ between stat/fstat on Windows (CPython #157671).
    # Compare it only between successive observations through the same API.
    return (*_identity(info), info.st_ctime_ns)


def _digest(path, root, expected_size, budget):
    # Refuse symlink/reparse traversal, including intermediate directories.
    relative = path.relative_to(root)
    current = root
    for part in (None, *relative.parts):
        if part is not None:
            current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("link-or-reparse-point")
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("path-escape")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size != expected_size:
        raise ValueError("file-changed-before-read")
    if before.st_size > budget["per_file"] or before.st_size > budget["remaining"]:
        raise ValueError("content-byte-limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if _identity(opened) != _identity(before):
            raise ValueError("file-changed-before-read")
        digest = hashlib.sha256()
        remaining = before.st_size
        while remaining:
            chunk = stream.read(min(65536, remaining))
            if not chunk:
                raise ValueError("file-changed-during-read")
            budget["remaining"] -= len(chunk)
            remaining -= len(chunk)
            digest.update(chunk)
        if _version(os.fstat(stream.fileno())) != _version(opened):
            raise ValueError("file-changed-during-read")
    if _version(path.lstat()) != _version(before):
        raise ValueError("file-changed-after-read")
    return digest.hexdigest()


def compare_contents(report, roots, *, per_file_limit=16 * 1024 * 1024,
                     total_limit=128 * 1024 * 1024):
    """Explicit opt-in for collision providers only; enrich the in-memory report."""
    if any(type(n) is not int or n < 0 for n in (per_file_limit, total_limit)):
        raise ValueError("content limits must be nonnegative integers")
    report["content_comparison"] = {"algorithm": "sha256", "bytes_read": 0,
                                    "per_file_limit": per_file_limit, "total_limit": total_limit}
    # This report is mutable and may already contain a previous comparison.
    # Hashes/equivalence must describe this attempt, never a stale successful read.
    for overlap in report["overlaps"]:
        overlap["content_equivalence"] = "unknown"
        for provider in overlap["providers"]:
            provider.pop("sha256", None)
    # An incomplete inventory cannot justify content/precedence conclusions.
    if not report["complete"]:
        for overlap in report["overlaps"]:
            overlap["proposed_winner_root"] = None
        report["content_comparison"]["status"] = "skipped-incomplete-inventory"
        return report
    budget = {"remaining": total_limit, "per_file": per_file_limit}
    for overlap in report["overlaps"]:
        digests = []
        for provider in overlap["providers"]:
            try:
                raw_root = Path(roots[provider["root_index"]])
                root_info = raw_root.lstat()
                if stat.S_ISLNK(root_info.st_mode) or getattr(root_info, "st_file_attributes", 0) & 0x400:
                    raise ValueError("root-changed-to-link")
                root = raw_root.resolve(strict=True)
                digest = _digest(root / provider["path"], root, provider["size_bytes"], budget)
                provider["sha256"] = digest
                digests.append(digest)
            except (OSError, RuntimeError, ValueError) as exc:
                reason = str(exc) if type(exc) is ValueError and str(exc) in {
                    "link-or-reparse-point", "path-escape", "file-changed-before-read",
                    "content-byte-limit", "file-changed-during-read", "file-changed-after-read",
                    "root-changed-to-link"} else type(exc).__name__
                report["errors"].append({"code": "content-unavailable-changed-or-limited", "reason": reason,
                                         "root_index": provider["root_index"], "path": provider["path"]})
        overlap["content_equivalence"] = ("unknown" if len(digests) != len(overlap["providers"])
                                           else "sha256-equal" if len(set(digests)) == 1 else "different")
    report["content_comparison"]["bytes_read"] = total_limit - budget["remaining"]
    report["content_comparison"]["status"] = "incomplete" if report["errors"] else "complete"
    if report["errors"]:
        report["complete"] = False
        report["status"] = "incomplete"
        for overlap in report["overlaps"]:
            overlap["proposed_winner_root"] = None
    report["errors"].sort(key=lambda e: (e["root_index"], e["path"], e["code"]))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", help="loose Data trees in hypothetical low-to-high priority")
    parser.add_argument("--compare-content", action="store_true",
                        help="opt in to bounded SHA-256 reads of overlapping files only")
    parser.add_argument("--html", action="store_true", help="emit an offline HTML report to stdout")
    parser.add_argument("--save-report", metavar="NEW_FILE", help="explicitly save a create-only evidence snapshot")
    args = parser.parse_args(argv)
    try:
        report = audit(args.roots)
        if args.compare_content:
            report = compare_contents(report, args.roots)
    except (ValueError, OSError):
        print(json.dumps({"status": "invalid-input"}), file=sys.stderr)
        return 2
    save_warning = False
    if args.save_report:
        from evidence import save_report
        try:
            receipt = save_report(report, args.save_report)
            print(json.dumps({"evidence_save": receipt}), file=sys.stderr)
            save_warning = receipt["directory_fsync"] == "unconfirmed" or not receipt["temporary_removed"]
        except (OSError, ValueError, RecursionError) as exc:
            print(json.dumps({"status": "evidence-not-saved", "error_type": type(exc).__name__}), file=sys.stderr)
            save_warning = True
    if args.html:
        from report_html import render_report
        print(render_report(report), end="")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    return 2 if save_warning or not report["complete"] else (1 if report["overlaps"] else 0)


if __name__ == "__main__":
    sys.exit(main())
