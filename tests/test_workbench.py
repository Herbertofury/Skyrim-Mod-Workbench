import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from workbench import diagnose, validate


def plugin(name, masters=(), enabled=True):
    return dict(name=name, masters=list(masters), enabled=enabled)


def manifest(*plugins):
    return dict(schema_version=1, plugins=list(plugins))


class DiagnosticTests(unittest.TestCase):
    def codes(self, data):
        return [f['code'] for f in diagnose(data)['findings']]

    def test_clean_case_insensitive_and_immutable(self):
        data = manifest(plugin('Base.esm'), plugin('Patch.esp', ['BASE.esm']))
        original = copy.deepcopy(data)
        self.assertEqual([], self.codes(data))
        self.assertEqual(original, data)
        self.assertFalse(diagnose(data)['game_verified'])

    def test_missing_disabled_and_order(self):
        data = manifest(plugin('Patch.esp', ['Gone.esm', 'Off.esm', 'Late.esm']),
                        plugin('Off.esm', enabled=False), plugin('Late.esm'))
        self.assertEqual(['missing-master', 'disabled-master', 'master-not-before-dependent'], self.codes(data))

    def test_cycle_and_self_reference(self):
        for data in [manifest(plugin('A.esp', ['A.esp'])),
                     manifest(plugin('A.esp', ['B.esp']), plugin('B.esp', ['A.esp']))]:
            self.assertIn('dependency-cycle', self.codes(data))

    def test_disabled_dependent_ignored(self):
        self.assertEqual([], self.codes(manifest(plugin('A.esp', ['Missing.esm'], False))))

    def test_long_chain_no_recursion_failure(self):
        data = manifest(*(plugin(f'{i}.esp', [f'{i+1}.esp'] if i < 1999 else []) for i in range(2000)))
        self.assertNotIn('dependency-cycle', self.codes(data))

    def test_invalid_schemas_and_names(self):
        bad = [None, {}, {'schema_version': True, 'plugins': []},
               manifest(plugin('A.esp'), plugin('a.ESP')),
               manifest(plugin('A.esp', ['B.esm', 'b.ESM'])),
               manifest(plugin('A.esp', enabled=1))]
        for name in ['../A.esp', 'x\\A.esp', ' C.esp', 'A.esp\n', 'C:A.esp', 'A.txt']:
            bad.append(manifest(plugin(name)))
        for data in bad:
            with self.subTest(data=data), self.assertRaises(ValueError):
                validate(data)

    def test_cli_exit_codes_no_write_and_duplicate_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            cases = [(json.dumps(manifest(plugin('A.esm'))), 0),
                     (json.dumps(manifest(plugin('A.esp', ['B.esm']))), 1),
                     ('{"schema_version":1,"schema_version":1,"plugins":[]}', 2),
                     ('x' * 2_000_001, 2)]
            for text, expected in cases:
                path.write_text(text)
                before = path.read_bytes()
                result = subprocess.run([sys.executable, 'workbench.py', str(path)], capture_output=True)
                self.assertEqual(expected, result.returncode)
                self.assertEqual(before, path.read_bytes())
                self.assertEqual([path], list(Path(directory).iterdir()))


if __name__ == '__main__':
    unittest.main()
