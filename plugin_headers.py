"""Bounded, read-only TES4 header inventory and master-impact discovery (not repair)."""
import argparse
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct
import sys
from workbench import plugin_name

MAX_HEADER_BYTES = 16 * 1024 * 1024
MAX_FILES = 4096
MAX_TOTAL_HEADER_BYTES = 64 * 1024 * 1024


def parse_header(raw, name):
    plugin_name(name)
    if len(raw) < 24 or raw[:4] != b'TES4':
        raise ValueError('missing TES4 record header')
    size, flags = struct.unpack_from('<II', raw, 4)
    if size > MAX_HEADER_BYTES or len(raw) != 24 + size or flags & 0x40000:
        raise ValueError('truncated, oversized or compressed TES4 header')
    masters, seen = [], set()
    hedr = None
    waiting_data = False
    offset = 24
    while offset < len(raw):
        if offset + 6 > len(raw):
            raise ValueError('truncated subrecord header')
        tag, length = struct.unpack_from('<4sH', raw, offset)
        offset += 6
        if tag == b'XXXX':
            raise ValueError('extended header subrecords unsupported')
        end = offset + length
        if end > len(raw):
            raise ValueError('truncated subrecord payload')
        payload = raw[offset:end]
        offset = end
        if waiting_data and tag != b'DATA':
            raise ValueError('missing master DATA pair')
        if tag == b'HEDR':
            if hedr is not None or length != 12:
                raise ValueError('invalid duplicate HEDR')
            version, count, next_id = struct.unpack('<fII', payload)
            if not math.isfinite(version):
                raise ValueError('invalid HEDR version')
            hedr = {'version': version, 'declared_record_count': count, 'next_object_id': next_id}
        elif tag == b'MAST':
            if not payload.endswith(b'\0') or b'\0' in payload[:-1]:
                raise ValueError('invalid master name terminator')
            master = payload[:-1].decode('cp1252')
            key = plugin_name(master)
            if key in seen or len(masters) >= 4096:
                raise ValueError('duplicate or excessive masters')
            seen.add(key)
            masters.append(master)
            waiting_data = True
        elif tag == b'DATA':
            if not waiting_data or length != 8:
                raise ValueError('unexpected master DATA')
            waiting_data = False
    if hedr is None or waiting_data:
        raise ValueError('incomplete TES4 header')
    return {'name': name, 'masters': masters, 'flags': flags, 'esm_flag': bool(flags & 1),
            'esl_flag': bool(flags & 0x200), 'form_version': struct.unpack_from('<H', raw, 20)[0],
            'hedr': hedr, 'header_sha256': hashlib.sha256(raw).hexdigest(), 'header_bytes': len(raw),
            'esl_eligibility': 'not-assessed-records-and-references-not-read'}


def read_header(path, *, budget=None):
    budget = [MAX_TOTAL_HEADER_BYTES] if budget is None else budget
    path = Path(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or getattr(before, 'st_file_attributes', 0) & 0x400:
        raise ValueError('regular non-link plugin required')
    identity_fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns')
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or any(
                getattr(before, field) != getattr(opened, field) for field in identity_fields):
            raise ValueError('plugin changed before header read')
        if budget[0] < 24:
            raise ValueError('aggregate header limit exceeded')
        budget[0] -= 24
        prefix = stream.read(24)
        if len(prefix) != 24 or prefix[:4] != b'TES4':
            raise ValueError('missing TES4 record header')
        size = struct.unpack_from('<I', prefix, 4)[0]
        if size > MAX_HEADER_BYTES or size > budget[0]:
            raise ValueError('header limit exceeded')
        budget[0] -= size
        raw = prefix + stream.read(size)
        observed = os.fstat(stream.fileno())
        # Compare ctime only within fstat; Windows stat/fstat semantics differ.
        if any(getattr(opened, field) != getattr(observed, field)
               for field in (*identity_fields, 'st_ctime_ns')):
            raise ValueError('plugin changed during header read')
    after = path.lstat()
    if any(getattr(before, f) != getattr(after, f) for f in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')):
        raise ValueError('plugin changed during header inventory')
    return parse_header(raw, path.name)


def inventory(paths, master=None):
    if not paths or len(paths) > MAX_FILES:
        raise ValueError('supply 1 to 4096 explicit plugins')
    target = plugin_name(master) if master is not None else None
    report = {'schema_version': 1, 'scope': 'explicit-plugin-headers-only', 'complete': True,
              'game_verified': False, 'applied': False, 'plugins': [], 'errors': [],
              'impact': None, 'status': 'headers-read'}
    seen = set()
    budget = [MAX_TOTAL_HEADER_BYTES]
    for path in paths:
        name = Path(path).name
        try:
            key = plugin_name(name)
            if key in seen:
                raise ValueError('duplicate case-insensitive filename')
            seen.add(key)
            header = read_header(path, budget=budget)
            report['plugins'].append(header)
        except (OSError, ValueError) as exc:
            report['errors'].append({'name': name, 'error_type': type(exc).__name__})
            report['complete'] = False
    if target:
        # Build reverse edges once. Repeated rescans are quadratic when the
        # input order is opposite to the dependency chain (up to 4096 files).
        dependents = {}
        for plugin in report['plugins']:
            for dependency in plugin['masters']:
                dependents.setdefault(dependency.casefold(), []).append(plugin['name'])
        direct = list(dependents.get(target, ()))
        affected = {target}
        pending = deque([target])
        while pending:
            for name in dependents.get(pending.popleft(), ()):
                key = name.casefold()
                if key not in affected:
                    affected.add(key)
                    pending.append(key)
        report['impact'] = {'master': master, 'direct_dependents': direct,
                            'transitive_dependents': [p['name'] for p in report['plugins']
                                                     if p['name'].casefold() in affected and p['name'].casefold() != target],
                            'scope_complete': report['complete'], 'all_installed_mods_scanned': False,
                            'record_mapping_verified': False}
    if not report['complete']:
        report['status'] = 'incomplete-header-inventory'
    return report


def diagnose_order(report):
    """Opt-in diagnostics for supplied header order, never inferred active state."""
    from workbench import diagnose
    result = {'scope': 'supplied-header-order-only', 'order_source': 'explicit-argument-order',
              'all_supplied_plugins_assumed_enabled': True, 'manager_state_verified': False,
              'game_verified': False, 'applied': False,
              'status': 'blocked-incomplete-header-inventory', 'findings': [],
              'limits': ['Every supplied plugin is treated as enabled for this hypothetical order.',
                         'Missing means absent from the supplied header set, not absent from the installation.',
                         'Implicit official masters, plugin type rules, LOOT rules and records are not assessed.']}
    report['dependency_diagnostics'] = result
    if not report['complete']:
        return report
    manifest = {'schema_version': 1, 'plugins': [
        {'name': p['name'], 'masters': p['masters'], 'enabled': True} for p in report['plugins']]}
    diagnosed = diagnose(manifest)
    result['findings'] = diagnosed['findings']
    result['status'] = 'dependency-findings' if result['findings'] else 'no-supplied-header-dependency-issues'
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plugins', nargs='+')
    parser.add_argument('--html', action='store_true', help='render an offline script-free HTML report')
    parser.add_argument('--diagnose-order', action='store_true', help='check explicit file order and master dependencies; assume supplied plugins enabled, not manager state')
    parser.add_argument('--master', help='exact old master filename to trace in supplied plugins')
    parser.add_argument('--save-report', metavar='NEW_FILE', help='explicitly save a create-only evidence snapshot')
    args = parser.parse_args(argv)
    try:
        report = inventory(args.plugins, args.master)
        if args.diagnose_order:
            diagnose_order(report)
    except ValueError:
        print(json.dumps({'status': 'invalid-input'}), file=sys.stderr)
        return 2
    save_warning = False
    if args.save_report:
        from evidence import save_cli_report
        save_warning = save_cli_report(report, args.save_report)
    if args.html:
        from report_html import render_report
        print(render_report(report), end='')
    else:
        print(json.dumps(report, indent=2))
    if not report['complete'] or save_warning:
        return 2
    return 1 if report.get('dependency_diagnostics', {}).get('findings') else 0


if __name__ == '__main__':
    sys.exit(main())
