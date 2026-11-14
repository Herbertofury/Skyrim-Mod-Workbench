from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from mo2_profile import parse_modlist, reconcile_mods
from report_html import render_report


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
    def run_report(self, raw=b'+Enabled\n-Disabled\n'):
        return reconcile_mods(parse_modlist(raw),self.root)
    def test_present_case_insensitive_no_modification(self):
        (self.root/'enabled').mkdir();(self.root/'Disabled').mkdir()
        (self.root/'metadata.txt').write_text('untouched')
        result=self.run_report()
        self.assertEqual('export-directories-reconciled',result['status'])
        self.assertEqual(['present','present'],[m['directory_state'] for m in result['mods']])
        self.assertEqual(1,result['reconciliation']['ignored_non_directory_count'])
        self.assertFalse(result['manager_state_verified'])
        self.assertEqual('untouched',(self.root/'metadata.txt').read_text())
    def test_missing_enabled_inactive_and_unlisted(self):
        (self.root/'NewMod').mkdir()
        result=self.run_report()
        self.assertEqual({'enabled-mod-directory-missing','inactive-or-separator-directory-missing','directory-not-in-export'},
                         {f['code'] for f in result['reconciliation']['findings']})
    def test_foreign_and_overwrite_not_assumed_missing(self):
        result=self.run_report(b'*DLC\n+Overwrite\n')
        self.assertEqual([],result['reconciliation']['findings'])
        self.assertTrue(all(m['directory_state']=='outside-regular-mod-directory-scope' for m in result['mods']))
    def test_unavailable_does_not_invent_missing(self):
        with patch('mo2_profile.os.scandir',side_effect=PermissionError): result=self.run_report()
        self.assertFalse(result['reconciliation']['complete'])
        self.assertTrue(all(m['directory_state']=='unknown-incomplete-inventory' for m in result['mods']))
        self.assertEqual(['mods-directory-unavailable'],[f['code'] for f in result['reconciliation']['findings']])
    def test_symlink_not_followed(self):
        try:(self.root/'Enabled').symlink_to(self.root,target_is_directory=True)
        except OSError:self.skipTest('symlink unavailable')
        result=self.run_report()
        self.assertFalse(result['reconciliation']['complete'])
        self.assertEqual('unresolved',result['mods'][1]['directory_state'])
    def test_case_collision_ambiguous(self):
        (self.root/'Enabled').mkdir()
        try:(self.root/'enabled').mkdir()
        except FileExistsError:self.skipTest('case-insensitive filesystem')
        result=self.run_report()
        self.assertFalse(result['reconciliation']['complete'])
        self.assertEqual('unresolved',result['mods'][1]['directory_state'])
    def test_cli_finding_exit_and_html(self):
        source=self.root/'modlist.txt';source.write_text('+Enabled\n')
        result=subprocess.run([sys.executable,'mo2_profile.py',str(source),'--mods-directory',str(self.root),'--html'],capture_output=True)
        self.assertEqual(1,result.returncode)
        self.assertIn(b'enabled-mod-directory-missing',result.stdout)
        self.assertEqual('+Enabled\n',source.read_text())
        self.assertNotIn(str(self.root),render_report(self.run_report()))

    def test_reconcile_again_discards_missing_directory_name(self):
        child = self.root / 'Enabled'
        child.mkdir()
        report = self.run_report(b'+Enabled\n')
        self.assertEqual('Enabled', report['mods'][0]['directory_name'])
        child.rmdir()
        reconcile_mods(report, self.root)
        self.assertEqual('missing', report['mods'][0]['directory_state'])
        self.assertNotIn('directory_name', report['mods'][0])

    def test_reconcile_again_invalidates_derived_asset_audit(self):
        from mo2_profile import audit_profile_assets
        child = self.root / 'Enabled'
        child.mkdir()
        report = self.run_report(b'+Enabled\n')
        audit_profile_assets(report, self.root)
        self.assertEqual('audited', report['profile_assets']['status'])
        with patch('mo2_profile.os.scandir', side_effect=PermissionError):
            reconcile_mods(report, self.root)
        self.assertFalse(report['reconciliation']['complete'])
        self.assertNotIn('directory_name', report['mods'][0])
        self.assertNotIn('profile_assets', report)
        audit_profile_assets(report, self.root)
        self.assertEqual('blocked', report['profile_assets']['status'])
        self.assertIsNone(report['profile_assets']['audit'])

    def test_successful_reconciliation_requires_fresh_asset_audit(self):
        from mo2_profile import audit_profile_assets
        (self.root / 'Enabled').mkdir()
        report = self.run_report(b'+Enabled\n')
        audit_profile_assets(report, self.root)
        reconcile_mods(report, self.root)
        self.assertEqual('present', report['mods'][0]['directory_state'])
        self.assertEqual('Enabled', report['mods'][0]['directory_name'])
        self.assertNotIn('profile_assets', report)
        audit_profile_assets(report, self.root)
        self.assertEqual('audited', report['profile_assets']['status'])
