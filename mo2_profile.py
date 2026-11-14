"""Read-only import of an explicitly selected MO2 modlist.txt export."""
import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
import re
import sys

MAX_BYTES = 2_000_000
MAX_MODS = 4096
SOURCE = 'https://github.com/ModOrganizer2/modorganizer/blob/4ba22f0d8b6f9e08e44008b8395cd774551b4ebe/src/profile.cpp'


def parse_modlist(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError('modlist byte limit or invalid input')
    contents = raw.decode('utf-8-sig')
    entries = []
    seen = set()
    for number, line in enumerate(contents.splitlines(), 1):
        if not line.strip() or line.startswith('#'):
            continue
        if len(line) > 4096 or line[0] not in '+-*':
            raise ValueError(f'line {number}: unsupported or unmarked entry')
        marker, name = line[0], line[1:].strip()
        if (not name or name in {'.', '..'} or name.endswith('.') or
                re.search(r'[\\/:\x00-\x1f\x7f]', name)):
            raise ValueError(f'line {number}: invalid mod name')
        key = name.casefold()
        if key in seen:
            raise ValueError(f'line {number}: duplicate case-insensitive mod name')
        seen.add(key)
        # Name classification is only a format hint, not installed metadata.
        kind = ('foreign' if marker == '*' else 'overwrite-reference' if key == 'overwrite'
                else 'separator' if name.endswith('_separator') else 'regular')
        entries.append({'name': name, 'enabled': marker != '-', 'kind': kind,
                        'file_line': number, 'marker': marker})
        if len(entries) > MAX_MODS:
            raise ValueError('mod count limit')
    # MO2 writes reverse priority order. Low-to-high is the useful import order.
    entries.reverse()
    for priority, entry in enumerate(entries):
        entry['export_priority'] = priority
    return {'schema_version': 1, 'scope': 'mo2-modlist-export-only',
            'status': 'export-parsed', 'game_verified': False, 'manager_state_verified': False,
            'applied': False, 'source_sha256': hashlib.sha256(raw).hexdigest(),
            'format_source': SOURCE, 'mods': entries,
            'enabled_regular_names_low_to_high': [e['name'] for e in entries if e['enabled'] and e['kind'] == 'regular'],
            'unresolved': ['Installed mod metadata and missing/new mods are not reconciled.',
                           'Foreign mods, overwrite, archives, plugin load order and VFS are not reconstructed.',
                           'Export ordering alone does not prove the currently active profile.']}



def reconcile_mods(report, mods_directory):
    """Compare export names to direct children only. Never follow links or edit MO2."""
    root = Path(mods_directory)
    result = {'scope': 'export-vs-direct-mod-directories', 'complete': True,
              'findings': [], 'directory_count': 0, 'ignored_non_directory_count': 0}
    report['reconciliation'] = result
    directories = {}
    blocked = set()
    def finding(code, name=''):
        result['findings'].append({'code': code, 'name': name})
    try:
        info = root.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('root link/reparse point')
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError('root not directory')
        with os.scandir(root) as listing:
            for count, entry in enumerate(listing, 1):
                if count > 8192:
                    finding('directory-entry-limit')
                    result['complete'] = False
                    break
                try:
                    info = entry.stat(follow_symlinks=False)
                    key = entry.name.casefold()
                    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                        blocked.add(key)
                        finding('link-or-reparse-point-unresolved', entry.name)
                        result['complete'] = False
                    elif stat.S_ISDIR(info.st_mode):
                        result['directory_count'] += 1
                        directories.setdefault(key, []).append(entry.name)
                    else:
                        result['ignored_non_directory_count'] += 1
                except OSError:
                    finding('entry-unreadable', entry.name)
                    blocked.add(entry.name.casefold())
                    result['complete'] = False
    except (OSError, ValueError, RuntimeError):
        finding('mods-directory-unavailable')
        result['complete'] = False
    listed = {m['name'].casefold() for m in report['mods']}
    for key, names in directories.items():
        if len(names) > 1:
            finding('ambiguous-case-directories', ' | '.join(sorted(names)))
            result['complete'] = False
        if key not in listed:
            for name in names:
                finding('directory-not-in-export', name)
    for mod in report['mods']:
        key = mod['name'].casefold()
        matches = directories.get(key, [])
        if mod['kind'] in {'foreign', 'overwrite-reference'}:
            mod['directory_state'] = 'outside-regular-mod-directory-scope'
        elif key in blocked or len(matches) > 1:
            mod['directory_state'] = 'unresolved'
        elif matches:
            mod['directory_state'] = 'present'
            mod['directory_name'] = matches[0]
        elif result['complete']:
            mod['directory_state'] = 'missing'
            finding('enabled-mod-directory-missing' if mod['enabled'] and mod['kind'] == 'regular'
                    else 'inactive-or-separator-directory-missing', mod['name'])
        else:
            mod['directory_state'] = 'unknown-incomplete-inventory'
    result['findings'].sort(key=lambda f: (f['code'], f['name']))
    report['status'] = ('reconciliation-incomplete' if not result['complete'] else
                        'reconciliation-findings' if result['findings'] else 'export-directories-reconciled')
    return report


def audit_profile_assets(report, mods_directory, *, compare_content=False):
    """Audit only enabled regular directories, preserving exported order."""
    from asset_audit import audit, compare_contents
    reconciliation = report.get('reconciliation')
    selected = [m for m in report['mods'] if m['enabled'] and m['kind'] == 'regular']
    blockers = []
    if not reconciliation or not reconciliation['complete']:
        blockers.append('incomplete-directory-reconciliation')
    if any(m.get('directory_state') != 'present' for m in selected):
        blockers.append('enabled-directory-unresolved')
    if len(selected) > 128:
        blockers.append('enabled-root-limit')
    result = {'status': 'blocked' if blockers else 'no-enabled-regular-mods' if not selected else 'audited',
              'blockers': blockers, 'root_mods': [], 'audit': None,
              'manager_state_verified': False, 'applied': False}
    report['profile_assets'] = result
    if blockers or not selected:
        return report
    roots = [Path(mods_directory) / m['directory_name'] for m in selected]
    result['root_mods'] = [{'root_index': i, 'name': m['name'], 'export_priority': m['export_priority']}
                           for i, m in enumerate(selected)]
    result['audit'] = audit(roots)
    if compare_content:
        compare_contents(result['audit'], roots)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('modlist', help='explicit UTF-8 MO2 modlist.txt export, never modified')
    parser.add_argument('--html', action='store_true', help='render a local static report to stdout')
    parser.add_argument("--mods-directory", help="opt in to read-only reconciliation with an explicitly selected MO2 mods directory")
    parser.add_argument('--audit-assets', action='store_true', help='audit enabled regular mod loose files in exported priority order')
    parser.add_argument('--compare-content', action='store_true', help='opt in to bounded overlapping-file reads; requires --audit-assets')
    args = parser.parse_args(argv)
    if (args.audit_assets and not args.mods_directory) or (args.compare_content and not args.audit_assets):
        parser.error('--audit-assets requires --mods-directory; --compare-content requires --audit-assets')
    try:
        with open(args.modlist, 'rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        result = parse_modlist(raw)
        if args.mods_directory:
            result = reconcile_mods(result, args.mods_directory)
        if args.audit_assets:
            audit_profile_assets(result, args.mods_directory, compare_content=args.compare_content)
    except (OSError, ValueError) as exc:
        # No personal path/name in the failure output.
        print(json.dumps({'status': 'invalid-mo2-export', 'error_type': type(exc).__name__}), file=sys.stderr)
        return 2
    if args.html:
        from report_html import render_report
        print(render_report(result), end='')
    else:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    assets = result.get('profile_assets')
    if assets:
        if assets['blockers'] or (assets['audit'] and not assets['audit']['complete']):
            return 2
        if assets['audit'] and assets['audit']['overlaps']:
            return 1
    reconciliation = result.get("reconciliation")
    if reconciliation:
        return 2 if not reconciliation["complete"] else (1 if reconciliation["findings"] else 0)
    return 0


if __name__ == '__main__':
    sys.exit(main())
