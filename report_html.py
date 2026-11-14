"""Offline, script-free HTML presentation of workbench reports."""
from html import escape
import json


def text(value):
    return escape(str(value), quote=True)


def table(headers, rows):
    rows = list(rows)
    if not rows:
        return '<p class="empty">None reported in this scope.</p>'
    head = ''.join(f'<th scope="col">{text(h)}</th>' for h in headers)
    body = ''.join('<tr>' + ''.join(f'<td>{text(v)}</td>' for v in row) + '</tr>' for row in rows)
    return f'<div class="table-scroll" tabindex="0" role="region" aria-label="Scrollable report table"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render_report(report):
    """Render only; never load external assets, submit data or apply a plan."""
    sections = []
    if 'mods' in report:
        sections.append('<h2>MO2 exported mod priority</h2><p>Low to high export order only. Active manager state is not verified.</p>' + table(
            ['Export priority', 'Name', 'Enabled marker', 'Kind', 'Original line'],
            ((m['export_priority'], m['name'], m['enabled'], m['kind'], m['file_line']) for m in report['mods'])))
        sections.append('<h2>Unresolved integration boundaries</h2><ul>' +
                        ''.join('<li>' + text(item) + '</li>' for item in report['unresolved']) + '</ul>')
    if 'findings' in report:
        sections.append('<h2>Plugin dependency findings</h2>' + table(
            ['Finding', 'Plugin', 'Master'],
            ((f.get('code', ''), f.get('plugin', ''), f.get('master', '')) for f in report['findings'])))
    if 'plan' in report:
        plan = report['plan']
        sections.append('<h2>Dependency-only plan preview</h2><p>Status: <strong>' + text(plan['status']) +
                        '</strong>. No changes applied. External validation required.</p>')
        sections.append('<p>Input basis SHA-256: <code>' + text(plan['basis_sha256']) + '</code></p>')
        sections.append(table(['Plugin', 'Original index (zero-based)', 'Proposed index (zero-based)'],
                              ((m['plugin'], m['from_index'], m['to_index']) for m in plan['moves'])))
        sections.append('<details><summary>Plan blockers and full proposed order</summary><pre>' +
                        text(json.dumps({'blockers': plan['blockers'], 'candidate_order': plan['candidate_order']},
                                        indent=2, ensure_ascii=True)) + '</pre></details>')
    if 'overlaps' in report:
        sections.append('<h2>Loose asset overlaps</h2>')
        sections.append('<p>Inventory completeness: <strong>' + ('complete' if report['complete'] else 'INCOMPLETE') +
                        '</strong>. Priority is hypothetical input order, not verified manager state.</p>')
        for overlap in report['overlaps']:
            winner = overlap['proposed_winner_root']
            sections.append('<details open><summary>' + text(overlap['path_key']) + '</summary><p>' +
                            text(overlap['kind']) + ' | Content: ' + text(overlap['content_equivalence']) +
                            ' | Proposed root: ' + text('unknown / withheld' if winner is None else winner) + '</p>')
            sections.append(table(['Root index', 'Relative path', 'Bytes', 'SHA-256 (if tested)'],
                                  ((p['root_index'], p['path'], p['size_bytes'], p.get('sha256', 'not tested'))
                                   for p in overlap['providers'])))
            sections.append('</details>')
        sections.append('<h2>Incomplete or unavailable evidence</h2>' + table(
            ['Code', 'Root index', 'Relative path', 'Reason'],
            ((e['code'], e['root_index'], e['path'], e.get('reason', '')) for e in report['errors'])))
    raw = text(json.dumps(report, indent=2, ensure_ascii=True))
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Skyrim Mod Workbench report</title>
<style>
:root{color-scheme:light dark;font-family:system-ui,sans-serif;line-height:1.5}
body{margin:0 auto;padding:1.2rem;max-width:1000px}h1{margin-bottom:.3rem}
.notice{border:2px solid #b78d30;padding:1rem;border-radius:.5rem}
.table-scroll{overflow:auto;max-width:100%;margin:.8rem 0}table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{text-align:left;padding:.5rem;border:1px solid #888;vertical-align:top;overflow-wrap:anywhere}
summary{cursor:pointer;font-weight:600;overflow-wrap:anywhere}details{padding:.8rem;border:1px solid #888;border-radius:.4rem;margin:1rem 0}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.8rem}code{overflow-wrap:anywhere}
:focus-visible{outline:3px solid #d99300;outline-offset:3px}.empty{font-style:italic}
@media print{details{break-inside:avoid}.table-scroll{overflow:visible}}
</style></head><body><main><h1>Skyrim Mod Workbench</h1>
<p>Offline diagnostic report. No scripts, network requests or apply controls.</p>
<div class="notice"><strong>Not native game acceptance.</strong> This report covers only the supplied inputs.
A clean result does not prove a healthy installation. Nothing has been repaired, deployed or changed.</div>
''' + '<p>Status: <strong>' + text(report['status']) + '</strong><br>Scope: ' + text(report['scope']) + '</p>' + \
        ''.join(sections) + '<details><summary>Complete machine-readable evidence (JSON)</summary><pre>' + raw + \
        '</pre></details><p>Review relative filenames and plugin names before sharing this report.</p></main></body></html>\n'
