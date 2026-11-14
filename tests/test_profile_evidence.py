"""Explicit report persistence never changes plugin/profile inputs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from evidence import load_report
from test_plugin_headers import fixture


class ProfileEvidenceTests(unittest.TestCase):
    def test_headers_save_incomplete_scope_and_preserve_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); plugin = root / 'Patch.esp'; output = root / 'headers.json'
            raw = fixture(['Old.esm']); plugin.write_bytes(raw)
            result = subprocess.run([sys.executable, 'plugin_headers.py', str(plugin),
                                     str(root / 'Missing.esp'), '--master', 'Old.esm',
                                     '--save-report', str(output)], capture_output=True, text=True)
            self.assertEqual(2, result.returncode)
            self.assertTrue(json.loads(result.stderr)['evidence_save']['published'])
            report = load_report(output)
            self.assertEqual(json.loads(result.stdout), report)
            self.assertFalse(report['complete'])
            self.assertEqual(['Patch.esp'], report['impact']['direct_dependents'])
            self.assertEqual(raw, plugin.read_bytes())

    def test_mo2_html_save_finding_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mods = root / 'mods'; mods.mkdir()
            source = root / 'modlist.txt'; source.write_bytes(b'+Missing\n')
            output = root / 'profile.json'
            command = [sys.executable, 'mo2_profile.py', str(source), '--mods-directory',
                       str(mods), '--html', '--save-report', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(1, result.returncode)
            self.assertIn('<!doctype html>', result.stdout)
            self.assertEqual('reconciliation-findings', load_report(output)['status'])
            old = output.read_bytes()
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(2, again.returncode)
            self.assertEqual('evidence-not-saved', json.loads(again.stderr)['status'])
            self.assertEqual(old, output.read_bytes())
            self.assertEqual(b'+Missing\n', source.read_bytes())

    def test_invalid_export_does_not_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'modlist.txt'; source.write_bytes(b'Invalid')
            output = root / 'invalid.json'
            result = subprocess.run([sys.executable, 'mo2_profile.py', str(source),
                                     '--save-report', str(output)], capture_output=True, text=True)
            self.assertEqual(2, result.returncode)
            self.assertFalse(output.exists())
            self.assertEqual('invalid-mo2-export', json.loads(result.stderr)['status'])
