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

class HeaderEvidenceValidationTests(unittest.TestCase):
    def test_malformed_hedr_cannot_be_certified_equal(self):
        for hedr in ({}, {'version': '1.7', 'declared_record_count': 0, 'next_object_id': 0},
                     {'version': True, 'declared_record_count': 0, 'next_object_id': 0},
                     {'version': 1.7, 'declared_record_count': -1, 'next_object_id': 0},
                     {'version': 1.7, 'declared_record_count': False, 'next_object_id': 0},
                     {'version': 1.7, 'declared_record_count': 0, 'next_object_id': 2**32}):
            with self.subTest(hedr=hedr):
                a=report();a['plugins'][0]['hedr']=hedr
                with self.assertRaises(ValueError):hc.compare(a,copy.deepcopy(a))
    def test_impossible_header_ranges_and_flag_conflicts_rejected(self):
        for fields in ({'flags': 2**32}, {'form_version': 65536}, {'header_bytes': 0},
                       {'header_bytes': ph.MAX_HEADER_BYTES+25}, {'esm_flag': True}, {'esl_flag': True}):
            with self.subTest(fields=fields):
                a=report();a['plugins'][0].update(fields)
                with self.assertRaises(ValueError):hc.compare(a,copy.deepcopy(a))
    def test_schema_and_nonfinite_version_rejected(self):
        for version in (None,True,2):
            a=report();a['schema_version']=version
            with self.subTest(schema=version),self.assertRaises(ValueError):hc.compare(a,a)
        for version in (float('nan'),float('inf'),-float('inf'),10**400):
            a=report();a['plugins'][0]['hedr']['version']=version
            with self.subTest(version=version),self.assertRaises(ValueError):hc.compare(a,a)
    def test_valid_checksum_does_not_override_structural_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'bad';b=Path(tmp)/'good';bad=report();bad['plugins'][0]['hedr']={}
            save_report(bad,a);save_report(report(),b)
            with contextlib.redirect_stdout(io.StringIO()) as out,contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(hc.main([str(a),str(b)]),2)
            self.assertEqual(out.getvalue(),'')
            self.assertEqual(json.loads(err.getvalue())['status'],'invalid-comparison-input')
