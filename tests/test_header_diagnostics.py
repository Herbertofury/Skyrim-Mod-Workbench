import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import plugin_headers as ph
from evidence import load_report
from report_html import render_report
from test_plugin_headers import fixture

class HeaderDiagnosticsTests(unittest.TestCase):
    def files(self, root, specs):
        paths=[]
        for name,masters in specs:
            p=root/name;p.write_bytes(fixture(masters));paths.append(p)
        return paths
    def test_order_uses_actual_headers_and_remains_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=self.files(Path(tmp), [('Patch.esp',['BASE.esm']),('Base.esm',[])])
            before=[p.read_bytes() for p in paths]
            r=ph.inventory(paths);self.assertNotIn('dependency_diagnostics',r)
            d=ph.diagnose_order(r)['dependency_diagnostics']
            self.assertEqual(d['findings'],[{'code':'master-not-before-dependent','plugin':'Patch.esp','master':'BASE.esm'}])
            self.assertFalse(d['manager_state_verified']);self.assertFalse(d['applied'])
            self.assertEqual(ph.diagnose_order(ph.inventory(paths[::-1]))['dependency_diagnostics']['findings'],[])
            self.assertEqual([p.read_bytes() for p in paths],before)
    def test_missing_and_cycles_are_within_supplied_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=self.files(Path(tmp),[('A.esp',['B.esp','Absent.esm']),('B.esp',['A.esp'])])
            d=ph.diagnose_order(ph.inventory(paths))['dependency_diagnostics']
            self.assertEqual({f['code'] for f in d['findings']},{'dependency-cycle','missing-master','master-not-before-dependent'})
            self.assertTrue(d['all_supplied_plugins_assumed_enabled'])
    def test_incomplete_inventory_does_not_turn_failed_header_into_missing_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=self.files(Path(tmp),[('A.esp',['Base.esm']),('Base.esm',[])])
            paths[1].write_bytes(b'bad')
            d=ph.diagnose_order(ph.inventory(paths))['dependency_diagnostics']
            self.assertEqual(d['status'],'blocked-incomplete-header-inventory');self.assertEqual(d['findings'],[])
    def test_cli_json_html_save_and_exit_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);paths=self.files(root,[('Patch.esp',['Absent.esm'])]);saved=root/'report'
            with contextlib.redirect_stdout(io.StringIO()) as out,contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(ph.main([str(paths[0]),'--diagnose-order','--save-report',str(saved)]),1)
            report=json.loads(out.getvalue());self.assertEqual(load_report(saved),report)
            self.assertIn('Supplied header order diagnostics',render_report(report))
            self.assertIn('missing-master',render_report(report))
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(ph.main([str(paths[0])]),0)
            paths[0].write_bytes(b'bad')
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(ph.main([str(paths[0]),'--diagnose-order','--html']),2)
    def test_html_escapes_header_diagnostic_names(self):
        report={'schema_version':1,'scope':'explicit-plugin-headers-only','complete':True,'game_verified':False,'status':'headers-read',
                'plugins':[ph.parse_header(fixture(['<missing>.esm']),'<patch>.esp')],'errors':[],'impact':None}
        html=render_report(ph.diagnose_order(report))
        self.assertNotIn('<patch>',html);self.assertNotIn('<missing>',html);self.assertIn('&lt;patch&gt;',html)
