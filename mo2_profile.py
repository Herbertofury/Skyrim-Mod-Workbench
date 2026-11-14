"""Read-only import of an explicitly selected MO2 modlist.txt export."""
import argparse
import hashlib
import json
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('modlist', help='explicit UTF-8 MO2 modlist.txt export, never modified')
    parser.add_argument('--html', action='store_true', help='render a local static report to stdout')
    args = parser.parse_args(argv)
    try:
        with open(args.modlist, 'rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        result = parse_modlist(raw)
    except (OSError, ValueError) as exc:
        # No personal path/name in the failure output.
        print(json.dumps({'status': 'invalid-mo2-export', 'error_type': type(exc).__name__}), file=sys.stderr)
        return 2
    if args.html:
        from report_html import render_report
        print(render_report(result), end='')
    else:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
