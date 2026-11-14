import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mo2_profile import parse_modlist, reconcile_mods, audit_profile_assets, main
from report_html import render_report

class ProfileAssetsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ['High', 'Low', 'Disabled', 'Section_separator']:
            directory = self.root / name
            directory.mkdir()
            (directory / 'texture.dds').write_bytes(name.encode())
        self.raw = b'+High\n-Disabled\n+Section_separator\n*Foreign\n+Low\n'

    def report(self):
        return reconcile_mods(parse_modlist(self.raw), self.root)

    def test_export_priority_filters_and_preserves_mapping(self):
        result = audit_profile_assets(self.report(), self.root)['profile_assets']
        self.assertEqual([m['name'] for m in result['root_mods']], ['Low', 'High'])
        overlap = result['audit']['overlaps'][0]
        self.assertEqual(overlap['proposed_winner_root'], 1)
        self.assertNotIn('sha256', overlap['providers'][0])
        self.assertFalse(result['manager_state_verified'])

    def test_explicit_comparison(self):
        result = audit_profile_assets(self.report(), self.root, compare_content=True)['profile_assets']
        self.assertEqual(result['audit']['overlaps'][0]['content_equivalence'], 'different')

    def test_missing_enabled_blocks_scan(self):
        self.raw += b'+Missing\n'
        with patch('asset_audit.audit') as scan:
            result = audit_profile_assets(self.report(), self.root)['profile_assets']
        scan.assert_not_called()
        self.assertIn('enabled-directory-unresolved', result['blockers'])
        self.assertIsNone(result['audit'])

    def test_incomplete_and_root_limit_block(self):
        report = self.report()
        report['reconciliation']['complete'] = False
        self.assertIn('incomplete-directory-reconciliation', audit_profile_assets(report, self.root)['profile_assets']['blockers'])
        report = self.report()
        report['mods'] = [report['mods'][0].copy() for _ in range(129)]
        self.assertIn('enabled-root-limit', audit_profile_assets(report, self.root)['profile_assets']['blockers'])

    def test_empty_selection_does_not_invent_clean_audit(self):
        report = reconcile_mods(parse_modlist(b'-Low\n'), self.root)
        result = audit_profile_assets(report, self.root)['profile_assets']
        self.assertEqual(result['status'], 'no-enabled-regular-mods')
        self.assertIsNone(result['audit'])

    def test_incomplete_audit_withholds_winners(self):
        report = self.report()
        (self.root / 'High' / 'texture.dds').unlink()
        (self.root / 'High').rmdir()
        result = audit_profile_assets(report, self.root)['profile_assets']['audit']
        self.assertFalse(result['complete'])
        self.assertTrue(all(o['proposed_winner_root'] is None for o in result['overlaps']))

    def test_cli_and_html(self):
        export = self.root / 'modlist.txt'
        export.write_bytes(self.raw)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main([str(export), '--mods-directory', str(self.root), '--audit-assets'])
        self.assertEqual(code, 1)
        report = json.loads(out.getvalue())
        html = render_report(report)
        self.assertIn('Export-selected loose asset audit', html)
        self.assertIn('texture.dds', html)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main([str(export), '--audit-assets'])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main([str(export), '--compare-content'])
