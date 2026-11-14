import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from evidence import save_report, load_report
import header_compare as hc
import plugin_headers as ph
from test_plugin_headers import fixture


def report(name='A.esp', masters=(), flags=0):
    return {'schema_version':1,'scope':'explicit-plugin-headers-only','complete':True,'game_verified':False,'errors':[],
            'plugins':[ph.parse_header(fixture(masters,flags),name)]}

class HeaderComparisonTests(unittest.TestCase):
    def test_identical_headers_remain_limited_not_game_verified(self):
        a=report();r=hc.compare(a,copy.deepcopy(a));self.assertEqual(r['status'],'no-header-differences')
        for f in ('game_verified','record_mapping_verified','whole_plugin_content_compared','current_files_verified'):self.assertFalse(r[f])
        self.assertEqual(r['unchanged_headers'],1)
    def test_master_order_flags_and_counts_not_hidden(self):
        a=report(masters=['Base.esm','Other.esm']);b=report(masters=['Other.esm','Base.esm'],flags=0x200)
        b['plugins'][0]['hedr']['declared_record_count']+=1
        r=hc.compare(a,b);self.assertEqual(r['status'],'header-differences-found')
        self.assertTrue({'masters','flags','esl_flag','hedr','header_sha256'}<=r['changed'][0]['changes'].keys())
    def test_case_matching_and_no_guessed_renames(self):
        r=hc.compare(report('A.esp'),report('a.ESP'));self.assertEqual(r['added_in_supplied_evidence'],[]);self.assertIn('name',r['changed'][0]['changes'])
        r=hc.compare(report('Old.esp'),report('New.esp'));self.assertEqual(r['removed_from_supplied_evidence'],['Old.esp']);self.assertFalse(r['renames_inferred'])
    def test_partial_inventory_retains_errors_and_never_claims_clean(self):
        a=report();a.update(complete=False,errors=[{'name':'Bad.esp','error_type':'ValueError'}]);r=hc.compare(a,a)
        self.assertEqual(r['status'],'incomplete-comparison');self.assertEqual(r['input_errors']['before'],a['errors'])
    def test_wrong_scope_duplicates_and_invalid_fields_rejected(self):
        for mutate in [lambda a:a.update(scope='other'),lambda a:a['plugins'].append(a['plugins'][0]),lambda a:a['plugins'][0].update(header_sha256='bad'),lambda a:a.update(errors=[{}])]:
            a=report();mutate(a)
            with self.assertRaises(ValueError):hc.compare(a,report())
    def test_cli_status_and_saved_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'a';b=Path(tmp)/'b';out=Path(tmp)/'out';save_report(report(),a);save_report(report(flags=0x200),b)
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(hc.main([str(a),str(b),'--save-report',str(out)]),1)
                self.assertEqual(hc.main([str(a),str(a)]),0)
                self.assertEqual(hc.main([str(a),str(b),'--save-report',str(out)]),2)
            self.assertEqual(load_report(out)['status'],'header-differences-found')
            b.write_text('{}')
            with contextlib.redirect_stdout(io.StringIO()) as stdout,contextlib.redirect_stderr(io.StringIO()):self.assertEqual(hc.main([str(a),str(b)]),2)
            self.assertEqual(stdout.getvalue(),'')
