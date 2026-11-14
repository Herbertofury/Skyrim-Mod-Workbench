from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from asset_audit import audit
from workbench import diagnose, dependency_plan
from report_html import render_report
from test_workbench import manifest, plugin


class Inspect(HTMLParser):
    def __init__(self):
        super().__init__(); self.tags=[]; self.content=[]; self.pre=[]; self.in_pre=False
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == 'pre': self.in_pre=True; self.pre.append('')
    def handle_endtag(self, tag):
        if tag == 'pre': self.in_pre=False
    def handle_data(self, data):
        self.content.append(data)
        if self.in_pre: self.pre[-1] += data


class ReportTests(unittest.TestCase):
    def parse(self, report):
        document = render_report(report)
        parser = Inspect(); parser.feed(document)
        self.assertEqual(report, json.loads(parser.pre[-1]))
        self.assertFalse(any(t in {'script','iframe','img','form','object','embed','link'} for t,a in parser.tags))
        self.assertFalse(any(k.startswith('on') or k in {'src','href'} for t,a in parser.tags for k in a))
        self.assertIn("default-src 'none'", document)
        return document, parser

    def test_dependency_plan_escaping_and_full_evidence(self):
        name = '<script>alert("x")</script>.esp'
        # Renderer treats report values as untrusted, even when supplied outside CLI validation.
        report = diagnose(manifest(plugin('A.esp', ['B.esm']), plugin('B.esm')))
        report['plan'] = dependency_plan(manifest(plugin('A.esp', ['B.esm']), plugin('B.esm')))
        report['findings'][0]['plugin'] = name
        document, parsed = self.parse(report)
        self.assertIn('&lt;script&gt;', document)
        self.assertIn(name, ''.join(parsed.content))
        self.assertIn('No changes applied', document)

    def test_incomplete_asset_no_winner_and_raw_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            a=Path(directory)/'a';b=Path(directory)/'b';a.mkdir();b.mkdir()
            for r in [a,b]: (r/'same.txt').write_text('x')
            report = audit([a,b,Path(directory)/'missing'])
            doc, _ = self.parse(report)
            self.assertIn('INCOMPLETE', doc)
            self.assertIn('unknown / withheld', doc)
            self.assertIn('root-unreadable', doc)

    def test_empty_results_not_healthy_claim(self):
        doc, _ = self.parse(diagnose(manifest()))
        self.assertIn('does not prove a healthy installation', doc)
        self.assertIn('None reported in this scope', doc)

    def test_cli_preserves_original_exit_and_input(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'manifest.json'
            data=manifest(plugin('A.esp',['B.esm']),plugin('B.esm'))
            p.write_text(json.dumps(data));before=p.read_bytes()
            r=subprocess.run([sys.executable,'workbench.py',str(p),'--plan','--html'],capture_output=True)
            self.assertEqual(1,r.returncode)
            self.assertTrue(r.stdout.startswith(b'<!doctype html>'))
            self.assertEqual(before,p.read_bytes())
            parser=Inspect();parser.feed(r.stdout.decode());self.assertEqual('preview',json.loads(parser.pre[-1])['plan']['status'])

    def test_asset_cli_html(self):
        with tempfile.TemporaryDirectory() as directory:
            r=subprocess.run([sys.executable,'asset_audit.py',directory,'--html'],capture_output=True)
            self.assertEqual(0,r.returncode)
            self.assertIn(b'Loose asset overlaps',r.stdout)
