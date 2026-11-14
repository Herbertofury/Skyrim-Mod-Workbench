import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import plugin_headers as ph


def sub(tag, payload):
    return struct.pack('<4sH', tag, len(payload)) + payload


def fixture(masters=(), flags=0):
    body = sub(b'HEDR', struct.pack('<fII', 1.7, 999, 0x800))
    for name in masters:
        body += sub(b'MAST', name.encode('cp1252') + b'\0') + sub(b'DATA', b'\0'*8)
    return struct.pack('<4sIIIIHH', b'TES4', len(body), flags, 0, 0, 44, 0) + body


class HeaderTests(unittest.TestCase):
    def test_flags_not_eligibility_or_actual_record_count(self):
        report = ph.parse_header(fixture(['Skyrim.esm'], 0x201), 'Test.esp')
        self.assertTrue(report['esl_flag'])
        self.assertTrue(report['esm_flag'])
        self.assertEqual(report['masters'], ['Skyrim.esm'])
        self.assertEqual(report['hedr']['declared_record_count'], 999)
        self.assertIn('not-assessed', report['esl_eligibility'])

    def test_invalid_headers(self):
        for raw in [b'', fixture()[:-1], fixture()+b'extra', fixture(flags=0x40000),
                    fixture(['A.esm', 'a.esm']), fixture(['../A.esm'])]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                ph.parse_header(raw, 'Test.esp')

    def test_truncation_at_every_boundary(self):
        raw = fixture(['Skyrim.esm'])
        for n in range(len(raw)):
            with self.assertRaises(ValueError):
                ph.parse_header(raw[:n], 'A.esp')

    def test_subrecord_contract(self):
        for body in [sub(b'XXXX', b'\0'*4), sub(b'MAST', b'A.esm\0'),
                     sub(b'DATA', b'\0'*8), sub(b'HEDR', b'\0'*11),
                     sub(b'MAST', b'A.esm\0x')]:
            raw = struct.pack('<4sIIIIHH', b'TES4', len(body), 0, 0, 0, 44, 0)+body
            with self.assertRaises(ValueError):
                ph.parse_header(raw, 'A.esp')

    def test_actual_file_header_only_and_transitive_impact(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name, masters in [('Patch.esp', ['Old.esm']), ('Child.esp', ['Patch.esp']), ('Other.esp', [])]:
                path = Path(tmp)/name
                path.write_bytes(fixture(masters)+b'UNPARSED-RECORD-DATA')
                paths.append(path)
            before = [p.read_bytes() for p in paths]
            report = ph.inventory(paths, 'old.ESM')
            self.assertEqual(report['impact']['direct_dependents'], ['Patch.esp'])
            self.assertEqual(report['impact']['transitive_dependents'], ['Patch.esp', 'Child.esp'])
            self.assertFalse(report['impact']['record_mapping_verified'])
            self.assertEqual(before, [p.read_bytes() for p in paths])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(ph.main([str(p) for p in paths]+['--master', 'Old.esm']), 0)
            self.assertTrue(json.loads(out.getvalue())['complete'])
            paths.append(Path(tmp)/'Missing.esp')
            self.assertFalse(ph.inventory(paths, 'Old.esm')['impact']['scope_complete'])

    def test_duplicate_names_and_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'A.esp'
            path.write_bytes(fixture())
            self.assertFalse(ph.inventory([path,path])['complete'])
            with patch('plugin_headers.MAX_HEADER_BYTES', 1), self.assertRaises(ValueError):
                ph.read_header(path)
        with self.assertRaises(ValueError):
            ph.inventory([])

    def test_reverse_chain_impact_has_bounded_name_normalization(self):
        # Count operations, not wall time: a repeated full rescan is quadratic.
        calls = [0]

        class CountedName(str):
            def casefold(self):
                calls[0] += 1
                return super().casefold()

        count = 4096
        headers = [{'name': CountedName(f'P{i}.esp'),
                    'masters': [CountedName(f'P{i-1}.esp' if i else 'Old.esm')]}
                   for i in reversed(range(count))]
        with patch('plugin_headers.read_header', side_effect=headers):
            report = ph.inventory([h['name'] for h in headers], 'OLD.ESM')
        self.assertEqual(report['impact']['direct_dependents'], ['P0.esp'])
        self.assertEqual(report['impact']['transitive_dependents'],
                         [h['name'] for h in headers])
        self.assertLessEqual(calls[0], count * 8)
        self.assertFalse(report['game_verified'])
        self.assertFalse(report['applied'])

    def test_impact_diamond_cycle_and_input_order(self):
        headers = [
            {'name': 'Leaf.esp', 'masters': ['LEFT.esp', 'Right.esp']},
            {'name': 'Unrelated.esp', 'masters': ['Missing.esm']},
            {'name': 'Right.esp', 'masters': ['Old.esm']},
            {'name': 'Left.esp', 'masters': ['OLD.ESM', 'Leaf.esp']},
            {'name': 'Old.esm', 'masters': ['Leaf.esp']},
        ]
        with patch('plugin_headers.read_header', side_effect=headers):
            report = ph.inventory([h['name'] for h in headers], 'old.esm')
        self.assertEqual(report['impact']['direct_dependents'], ['Right.esp', 'Left.esp'])
        self.assertEqual(report['impact']['transitive_dependents'],
                         ['Leaf.esp', 'Right.esp', 'Left.esp'])
        self.assertTrue(report['impact']['scope_complete'])
        self.assertFalse(report['impact']['all_installed_mods_scanned'])

    def test_failed_parse_still_consumes_global_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/'A.esp', Path(tmp)/'B.esp'
            raw = fixture()
            # Correct framing but invalid HEDR length in payload.
            bad = bytearray(raw)
            bad[28:30] = struct.pack('<H', 11)
            a.write_bytes(bad)
            b.write_bytes(raw)
            with patch('plugin_headers.MAX_TOTAL_HEADER_BYTES', len(raw)):
                report = ph.inventory([a, b])
            self.assertEqual(len(report['errors']), 2)
            self.assertEqual(report['plugins'], [])


class HeaderDescriptorTests(unittest.TestCase):
    def test_opened_replacement_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / 'First.esp'
            second = Path(directory) / 'Second.esp'
            first.write_bytes(fixture(['Old.esm']))
            second.write_bytes(fixture(['New.esm']))
            budget = [1000]
            # Stable pathname observations do not prove which file was opened.
            with second.open('rb') as replacement:
                with patch.object(Path, 'open', return_value=replacement):
                    with self.assertRaisesRegex(ValueError, 'changed before'):
                        ph.read_header(first, budget=budget)
            self.assertEqual([1000], budget)

    def test_same_api_descriptor_change_rejected(self):
        import os
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Stable.esp'
            path.write_bytes(fixture())
            real_fstat = os.fstat
            calls = 0
            def observed(fd):
                nonlocal calls
                calls += 1
                info = real_fstat(fd)
                values = {key: getattr(info, key) for key in
                          ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_mtime_ns', 'st_ctime_ns')}
                values['st_ctime_ns'] += int(calls > 1)
                return SimpleNamespace(**values)
            with patch('os.fstat', side_effect=observed):
                with self.assertRaisesRegex(ValueError, 'changed during'):
                    ph.read_header(path)
