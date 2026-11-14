"""Reparse-attribute contracts without requiring Windows junction privileges."""
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
