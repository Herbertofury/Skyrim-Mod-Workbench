import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import evidence
import plugin_headers as ph
from report_html import render_report
from test_plugin_headers import fixture

class HeaderHTMLTests(unittest.TestCase):
    def test_inventory_and_impact_visible_with_explicit_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'Child.esp';p.write_bytes(fixture(['Base.esm'],0x200))
            report=ph.inventory([p],'Base.esm');html=render_report(report)
        for value in ('Explicit plugin headers','Child.esp','Base.esm','999','Direct dependents','Transitive dependents','do not establish ESL eligibility','record mapping'):
            self.assertIn(value,html)
        self.assertNotIn('<script',html)
        self.assertIn(report['plugins'][0]['header_sha256'],html)

    def test_failed_inputs_and_injected_labels_are_escaped(self):
        report=ph.inventory(['/missing/Bad.esp'],'Base.esm')
        report['errors'][0]['name']='<img src=x onerror=alert(1)>'
        report['impact']['master']='<script>bad</script>'
        html=render_report(report)
        self.assertIn('incomplete-header-inventory',html)
        self.assertIn('&lt;img',html);self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<img',html);self.assertNotIn('<script',html)

    def test_cli_html_and_evidence_save_keep_separate_streams(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'A.esp';p.write_bytes(fixture());dest=Path(tmp)/'snapshot.json'
            out=io.StringIO();err=io.StringIO()
            with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
                code=ph.main([str(p),'--html','--save-report',str(dest)])
            self.assertEqual(code,0);self.assertTrue(out.getvalue().startswith('<!doctype html>'))
            self.assertTrue(json.loads(err.getvalue())['evidence_save']['published'])
            self.assertEqual(evidence.load_report(dest)['plugins'][0]['name'],'A.esp')
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(ph.main([str(p),'--html','--save-report',str(dest)]),2)
