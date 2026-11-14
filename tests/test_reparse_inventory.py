"""Reparse-attribute contracts without requiring Windows junction privileges."""
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from asset_audit import audit, compare_contents


class ReparseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_root_reparse_not_scanned_or_resolved(self):
        info = SimpleNamespace(st_mode=self.root.lstat().st_mode, st_file_attributes=0x400)
        with patch.object(Path, 'lstat', return_value=info), patch('asset_audit.os.scandir') as scan:
            report = audit([self.root])
        self.assertFalse(report['complete'])
        self.assertEqual(0, report['file_count'])
        scan.assert_not_called()

    def test_entry_reparse_not_inventoried(self):
        child = self.root / 'cloud.txt'
        child.write_bytes(b'no content read')
        info = SimpleNamespace(st_mode=child.lstat().st_mode, st_size=15, st_file_attributes=0x400)
        entry = SimpleNamespace(name=child.name, path=str(child), stat=lambda **kw: info)
        listing = MagicMock()
        listing.__enter__.return_value = iter([entry])
        with patch('asset_audit.os.scandir', return_value=listing):
            report = audit([self.root])
        self.assertFalse(report['complete'])
        self.assertEqual(0, report['file_count'])
        self.assertEqual('reparse-point-skipped', report['errors'][0]['code'])

    def test_content_root_reparse_rejected_before_resolution(self):
        info = SimpleNamespace(st_mode=self.root.lstat().st_mode, st_file_attributes=0x400)
        report = {'complete': True, 'errors': [], 'overlaps': [
            {'providers': [{'root_index': 0, 'path': 'a', 'size_bytes': 0}],
             'proposed_winner_root': 0}]}
        with patch.object(Path, 'lstat', return_value=info), patch('asset_audit._digest') as digest:
            compare_contents(report, [self.root])
        digest.assert_not_called()
        self.assertFalse(report['complete'])
        self.assertEqual('root-changed-to-link', report['errors'][0]['reason'])


@unittest.skipUnless(os.name == 'nt', 'requires native Windows junctions')
class NativeJunctionTests(unittest.TestCase):
    def test_real_junction_roots_children_and_replaced_content_root(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / 'target'; target.mkdir()
            secret = target / 'asset.txt'; secret.write_bytes(b'unchanged fixture')
            root = base / 'root'; root.mkdir()
            junction = root / 'junction'
            completed = subprocess.run(
                ['cmd.exe', '/d', '/c', 'mklink', '/J', str(junction), str(target)],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            try:
                self.assertTrue(junction.lstat().st_file_attributes & 0x400)
                root_report = audit([junction])
                self.assertFalse(root_report['complete'])
                self.assertEqual(0, root_report['file_count'])
                self.assertEqual('root-reparse-point', root_report['errors'][0]['code'])
                child_report = audit([root])
                self.assertFalse(child_report['complete'])
                self.assertEqual(0, child_report['file_count'])
                self.assertEqual('reparse-point-skipped', child_report['errors'][0]['code'])
                report = {'complete': True, 'errors': [], 'overlaps': [
                    {'providers': [{'root_index': 0, 'path': 'asset.txt', 'size_bytes': 17}],
                     'proposed_winner_root': 0}]}
                compare_contents(report, [junction])
                self.assertEqual(0, report['content_comparison']['bytes_read'])
                self.assertFalse(report['complete'])
                self.assertIsNone(report['overlaps'][0]['proposed_winner_root'])
                self.assertEqual('root-changed-to-link', report['errors'][0]['reason'])
                self.assertEqual(b'unchanged fixture', secret.read_bytes())
            finally:
                # Remove only the fixture junction, never the target's contents.
                junction.rmdir()
