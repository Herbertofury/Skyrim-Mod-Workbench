import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from asset_audit import audit, compare_contents


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.roots = [self.base / str(i) for i in range(2)]
        for root in self.roots: root.mkdir()

    def files(self, a=b'one', b=b'one'):
        for root, data in zip(self.roots, [a, b]): (root / 'asset.dds').write_bytes(data)

    def test_equal_and_same_size_different(self):
        for a, b, expected in [(b'one', b'one', 'sha256-equal'), (b'one', b'two', 'different'), (b'', b'', 'sha256-equal')]:
            self.files(a, b)
            report = compare_contents(audit(self.roots), self.roots)
            self.assertEqual(expected, report['overlaps'][0]['content_equivalence'])
            self.assertEqual(len(a)+len(b), report['content_comparison']['bytes_read'])
            self.assertEqual(hashlib.sha256(a).hexdigest(), report['overlaps'][0]['providers'][0]['sha256'])

    def test_default_never_opens_content(self):
        self.files()
        with patch('asset_audit.os.open', side_effect=AssertionError('unexpected content read')):
            self.assertEqual('not-tested', audit(self.roots)['overlaps'][0]['content_equivalence'])

    def test_unique_files_not_hashed(self):
        self.files()
        (self.roots[0] / 'unique.bin').write_bytes(b'not part of collision')
        report = compare_contents(audit(self.roots), self.roots)
        self.assertEqual(6, report['content_comparison']['bytes_read'])

    def test_limits_and_no_winner(self):
        self.files()
        for limits in [{'per_file_limit': 2}, {'total_limit': 3}]:
            report = compare_contents(audit(self.roots), self.roots, **limits)
            self.assertFalse(report['complete'])
            self.assertEqual('unknown', report['overlaps'][0]['content_equivalence'])
            self.assertIsNone(report['overlaps'][0]['proposed_winner_root'])
            self.assertLessEqual(report['content_comparison']['bytes_read'], limits.get('total_limit', 128*1024*1024))

    def test_changed_or_deleted_after_inventory(self):
        for delete in [False, True]:
            self.files()
            report = audit(self.roots)
            path = self.roots[0] / 'asset.dds'
            if delete: path.unlink()
            else: path.write_bytes(b'longer')
            result = compare_contents(report, self.roots)
            self.assertFalse(result['complete'])
            self.assertEqual('unknown', result['overlaps'][0]['content_equivalence'])

    def test_link_substitution_refused(self):
        self.files()
        report = audit(self.roots)
        path = self.roots[0] / 'asset.dds'; path.unlink()
        try: path.symlink_to(self.roots[1] / 'asset.dds')
        except OSError: self.skipTest('symlink unavailable')
        self.assertFalse(compare_contents(report, self.roots)['complete'])

    def test_incomplete_inventory_skips_reads(self):
        self.files()
        report = audit(self.roots + [self.base / 'missing'])
        with patch('asset_audit.os.open', side_effect=AssertionError):
            result = compare_contents(report, self.roots)
        self.assertEqual('skipped-incomplete-inventory', result['content_comparison']['status'])

    def test_cli_and_immutability(self):
        self.files(b'one', b'two')
        result = subprocess.run([sys.executable, 'asset_audit.py', '--compare-content', *map(str, self.roots)], capture_output=True)
        self.assertEqual(1, result.returncode)
        self.assertEqual('different', json.loads(result.stdout)['overlaps'][0]['content_equivalence'])
        self.assertEqual([b'one', b'two'], [(r / 'asset.dds').read_bytes() for r in self.roots])
