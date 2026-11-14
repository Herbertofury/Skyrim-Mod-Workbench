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
