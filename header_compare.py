"""Compare saved header inventories without opening plugins or inferring record mappings."""
import argparse
import hashlib
import json
import re
import sys
from evidence import canonical, load_report, save_cli_report
from workbench import plugin_name

FIELDS = ('name', 'masters', 'flags', 'esm_flag', 'esl_flag', 'form_version', 'hedr', 'header_sha256', 'header_bytes')


def _index(report):
    if (not isinstance(report, dict) or report.get('scope') != 'explicit-plugin-headers-only'
            or report.get('game_verified') is not False or type(report.get('complete')) is not bool
            or not isinstance(report.get('errors'), list) or not isinstance(report.get('plugins'), list)
            or len(report['plugins']) > 4096):
        raise ValueError('expected explicit header inventory')
    if report['complete'] and report['errors']:
        raise ValueError('inconsistent inventory completeness')
    result = {}
    for p in report['plugins']:
        if not isinstance(p, dict) or any(f not in p for f in FIELDS):
            raise ValueError('incomplete plugin header evidence')
        key = plugin_name(p['name'])
        if key in result or not isinstance(p['masters'], list) or len(p['masters']) > 4096:
            raise ValueError('duplicate plugin or invalid masters')
        masters = [plugin_name(m) for m in p['masters']]
        if len(set(masters)) != len(masters):
            raise ValueError('duplicate master evidence')
        if not isinstance(p['header_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', p['header_sha256']):
            raise ValueError('invalid header digest')
        for field in ('flags', 'form_version', 'header_bytes'):
            if type(p[field]) is not int or p[field] < 0:
                raise ValueError('invalid numeric header evidence')
        if type(p['esm_flag']) is not bool or type(p['esl_flag']) is not bool or not isinstance(p['hedr'], dict):
            raise ValueError('invalid header fields')
        result[key] = p
    return result


def compare(before, after):
    old, new = _index(before), _index(after)
    complete = before['complete'] and after['complete']
    changed = []
    for key in sorted(old.keys() & new.keys()):
        fields = {f: {'before': old[key][f], 'after': new[key][f]} for f in FIELDS if old[key][f] != new[key][f]}
        if fields:
            changed.append({'name': new[key]['name'], 'changes': fields})
    added = [new[k]['name'] for k in sorted(new.keys() - old.keys())]
    removed = [old[k]['name'] for k in sorted(old.keys() - new.keys())]
    return {'schema_version': 1, 'scope': 'saved-plugin-header-comparison-only',
            'status': 'incomplete-comparison' if not complete else ('header-differences-found' if added or removed or changed else 'no-header-differences'),
            'complete': complete, 'game_verified': False, 'applied': False, 'historical': True,
            'current_files_verified': False, 'authenticity_verified': False, 'record_mapping_verified': False,
            'renames_inferred': False, 'whole_plugin_content_compared': False,
            'before_report_sha256': hashlib.sha256(canonical(before)).hexdigest(),
            'after_report_sha256': hashlib.sha256(canonical(after)).hexdigest(),
            'added_in_supplied_evidence': added, 'removed_from_supplied_evidence': removed,
            'changed': changed, 'unchanged_headers': len(old.keys() & new.keys()) - len(changed),
            'input_errors': {'before': before['errors'], 'after': after['errors']},
            'limits': ['Added/removed means absence in supplied evidence, not verified installation changes.',
                       'Equal headers do not prove equal plugin records or assets.',
                       'Changed master names do not establish FormID equivalence or safe migration.',
                       'ESL flags and declared header counts are not ESL eligibility tests.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', help='saved integrity envelope from plugin_headers.py --save-report')
    parser.add_argument('after', help='saved integrity envelope from plugin_headers.py --save-report')
    parser.add_argument('--save-report', metavar='NEW_FILE')
    args = parser.parse_args(argv)
    try:
        report = compare(load_report(args.before), load_report(args.after))
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        print(json.dumps({'status': 'invalid-comparison-input', 'error_type': type(exc).__name__}), file=sys.stderr)
        return 2
    warning = save_cli_report(report, args.save_report) if args.save_report else False
    print(json.dumps(report, indent=2))
    return 2 if not report['complete'] or warning else (1 if report['status']=='header-differences-found' else 0)


if __name__ == '__main__':
    sys.exit(main())
