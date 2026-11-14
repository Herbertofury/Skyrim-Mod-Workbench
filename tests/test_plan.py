import copy
import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from workbench import dependency_plan, diagnose
from test_workbench import manifest, plugin


class PlanTests(unittest.TestCase):
    def test_reorders_and_keeps_disabled_slots(self):
        data = manifest(plugin('Patch.esp', ['Base.esm']), plugin('Off.esp', enabled=False), plugin('Base.esm'))
        original = copy.deepcopy(data)
        plan = dependency_plan(data)
        self.assertEqual(['Base.esm', 'Off.esp', 'Patch.esp'], plan['candidate_order'])
        self.assertEqual([{'plugin': 'Base.esm', 'from_index': 2, 'to_index': 0},
                          {'plugin': 'Patch.esp', 'from_index': 0, 'to_index': 2}], plan['moves'])
        self.assertEqual(original, data)
        self.assertFalse(plan['applied'])
        self.assertTrue(plan['requires_external_validation'])

    def test_blocks_missing_disabled_cycle(self):
        cases = [manifest(plugin('A.esp', ['Missing.esm'])),
                 manifest(plugin('A.esp', ['B.esm']), plugin('B.esm', enabled=False)),
                 manifest(plugin('A.esp', ['A.esp'])),
                 manifest(plugin('A.esp', ['B.esp']), plugin('B.esp', ['A.esp']))]
        for data in cases:
            plan = dependency_plan(data)
            self.assertEqual('blocked', plan['status'])
            self.assertIsNone(plan['candidate_order'])
            self.assertEqual([], plan['moves'])
            self.assertTrue(plan['blockers'])

    def test_stability_for_valid_order_empty_disabled(self):
        for data in [manifest(), manifest(plugin('Off.esp', enabled=False)),
                     manifest(plugin('B.esm'), plugin('A.esp', ['b.ESM']), plugin('Other.esp'))]:
            plan = dependency_plan(data)
            self.assertEqual('no-dependency-reorder-needed', plan['status'])
            self.assertEqual([p['name'] for p in data['plugins']], plan['candidate_order'])

    def test_all_dag_permutations_and_idempotence(self):
        nodes = [plugin('Base.esm'), plugin('A.esp', ['BASE.esm']),
                 plugin('B.esp', ['Base.esm']), plugin('C.esp', ['A.esp', 'B.esp']), plugin('Independent.esp')]
        for order in itertools.permutations(nodes):
            data = manifest(*order)
            plan = dependency_plan(data)
            lookup = {p['name']: p for p in order}
            candidate = manifest(*(lookup[n] for n in plan['candidate_order']))
            self.assertEqual([], diagnose(candidate)['findings'])
            self.assertEqual([], dependency_plan(candidate)['moves'])
            self.assertEqual(plan, dependency_plan(data))

    def test_basis_tracks_semantics_not_dict_key_order(self):
        a = manifest(plugin('A.esm'))
        b = {'plugins': a['plugins'], 'schema_version': 1}
        self.assertEqual(dependency_plan(a)['basis_sha256'], dependency_plan(b)['basis_sha256'])
        b = copy.deepcopy(b); b['plugins'][0]['enabled'] = False
        self.assertNotEqual(dependency_plan(a)['basis_sha256'], dependency_plan(b)['basis_sha256'])

    def test_long_reverse_chain(self):
        data = manifest(*(plugin(f'{i}.esp', [f'{i+1}.esp'] if i < 1999 else []) for i in range(2000)))
        self.assertEqual([f'{i}.esp' for i in reversed(range(2000))], dependency_plan(data)['candidate_order'])

    def test_cli_plan_still_reports_unfixed_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'inventory.json'
            path.write_text(json.dumps(manifest(plugin('A.esp', ['B.esm']), plugin('B.esm'))))
            before = path.read_bytes()
            r = subprocess.run([sys.executable, 'workbench.py', str(path), '--plan'], capture_output=True)
            self.assertEqual(1, r.returncode)
            self.assertEqual('preview', json.loads(r.stdout)['plan']['status'])
            self.assertEqual(before, path.read_bytes())
            self.assertEqual([path], list(Path(directory).iterdir()))
