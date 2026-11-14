import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from asset_audit import audit


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.a = self.base / 'a'; self.a.mkdir()
        self.b = self.base / 'b'; self.b.mkdir()

    def put(self, root, path, data=b'content'):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def test_case_insensitive_overlap_and_priority(self):
        self.put(self.a, 'Textures/Armor.dds', b'one')
        self.put(self.b, 'textures/armor.DDS', b'two')
        report = audit([self.a, self.b])
        self.assertTrue(report['complete'])
        self.assertEqual('textures/armor.dds', report['overlaps'][0]['path_key'])
        self.assertEqual(1, report['overlaps'][0]['proposed_winner_root'])
        self.assertEqual('not-tested', report['overlaps'][0]['content_equivalence'])
        self.assertNotIn(str(self.base), json.dumps(report))
        self.assertFalse(report['applied'])

    def test_same_root_case_ambiguity(self):
        self.put(self.a, 'A.txt')
        self.put(self.a, 'a.txt')
        if len(list(self.a.iterdir())) != 2:
            self.skipTest('case-insensitive filesystem cannot represent fixture')
        self.assertIsNone(audit([self.a])['overlaps'][0]['proposed_winner_root'])

    def test_nested_and_duplicate_roots_rejected(self):
        nested = self.a / 'nested'; nested.mkdir()
        for roots in [[self.a, self.a], [self.a, nested], [nested, self.a]]:
            report = audit(roots)
            self.assertFalse(report['complete'])
            self.assertEqual('overlapping-root', report['errors'][0]['code'])

    def test_symlink_skipped_and_never_read(self):
        outside = self.put(self.b, 'secret.txt')
        try:
            (self.a / 'link').symlink_to(outside)
        except OSError:
            self.skipTest('symlink creation unavailable')
        result = audit([self.a])
        self.assertFalse(result['complete'])
        self.assertEqual(0, result['file_count'])
        self.assertEqual('symlink-skipped', result['errors'][0]['code'])

    def test_limits_do_not_claim_complete(self):
        for name in ['1.txt', '2.txt', '3.txt']:
            self.put(self.a, name)
        result = audit([self.a], max_entries=1)
        self.assertFalse(result['complete'])
        self.assertEqual('entry-limit', result['errors'][0]['code'])
        (self.b / 'empty').mkdir()
        self.assertFalse(audit([self.b], max_directories=1)['complete'])

    def test_missing_and_permission_failure(self):
        self.assertFalse(audit([self.base / 'missing'])['complete'])
        with patch('asset_audit.os.scandir', side_effect=PermissionError):
            result = audit([self.a])
        self.assertEqual('directory-unreadable', result['errors'][0]['code'])

    def test_incomplete_audit_suppresses_winner(self):
        self.put(self.a, 'same.txt')
        self.put(self.b, 'same.txt')
        report = audit([self.a, self.b, self.base / 'missing'])
        self.assertTrue(report['overlaps'])
        self.assertIsNone(report['overlaps'][0]['proposed_winner_root'])

    def test_empty_unique_and_invalid(self):
        self.assertEqual('no-loose-overlaps', audit([self.a])['status'])
        self.put(self.a, 'unique.txt')
        self.assertEqual(1, audit([self.a])['file_count'])
        for roots in [[], [self.a] * 129]:
            with self.assertRaises(ValueError): audit(roots)

    def test_deterministic_and_cli_no_mutation(self):
        original = self.put(self.a, 'same.txt', b'original')
        self.put(self.b, 'same.txt', b'override')
        report = audit([self.a, self.b])
        self.assertEqual(report, audit([self.a, self.b]))
        result = subprocess.run([sys.executable, 'asset_audit.py', str(self.a), str(self.b)], capture_output=True)
        self.assertEqual(1, result.returncode)
        self.assertEqual(report, json.loads(result.stdout))
        self.assertEqual(b'original', original.read_bytes())
        self.assertEqual(2, len(list(self.base.rglob('*.txt'))))
