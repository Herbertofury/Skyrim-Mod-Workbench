import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import toolchain


class ToolchainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.exe = Path(self.tmp.name) / 'LOOT.exe'
        self.exe.write_bytes((b'MZ00' if os.name == 'nt' else b'\x7fELF') + b'fixture-not-real-tool')

    def test_preview_never_launches(self):
        with patch('toolchain.subprocess.Popen') as start:
            report = toolchain.launch_loot(self.exe)
        start.assert_not_called()
        self.assertEqual(report['argv'], [str(self.exe), '--game=Skyrim Special Edition'])
        self.assertFalse(report['operation_completed'])
        self.assertFalse(report['tool_identity_verified'])

    def test_requires_both_execution_gates(self):
        digest = toolchain.inspect_executable(self.exe)[1]
        with patch('toolchain.subprocess.Popen') as start:
            for options in [{'expected_sha256': digest}, {'acknowledge_side_effects': True},
                            {'acknowledge_side_effects': True, 'expected_sha256': '0'*64}]:
                with self.assertRaises(ValueError):
                    toolchain.launch_loot(self.exe, execute=True, **options)
        start.assert_not_called()

    def test_exact_argv_no_shell_and_receipt_is_not_completion(self):
        digest = toolchain.inspect_executable(self.exe)[1]
        with patch('toolchain.subprocess.Popen', return_value=Mock(pid=42)) as start:
            report = toolchain.launch_loot(self.exe, execute=True, expected_sha256=digest,
                                          acknowledge_side_effects=True)
        self.assertFalse(start.call_args.kwargs['shell'])
        self.assertEqual(start.call_args.args[0], [str(self.exe), '--game=Skyrim Special Edition'])
        self.assertTrue(report['process_started'])
        self.assertFalse(report['operation_completed'])
        self.assertFalse(report['native_acceptance_verified'])

    def test_changed_binary_and_unrecognized_scripts_rejected(self):
        digest = toolchain.inspect_executable(self.exe)[1]
        self.exe.write_bytes(self.exe.read_bytes() + b'changed')
        with patch('toolchain.subprocess.Popen') as start, self.assertRaises(ValueError):
            toolchain.launch_loot(self.exe, execute=True, expected_sha256=digest, acknowledge_side_effects=True)
        start.assert_not_called()
        self.exe.write_bytes(b'#!/bin/sh\nexit 0')
        with self.assertRaises(ValueError):
            toolchain.inspect_executable(self.exe)

    def test_bound_and_cli(self):
        with patch('toolchain.MAX_EXECUTABLE_BYTES', 1), self.assertRaises(ValueError):
            toolchain.inspect_executable(self.exe)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(toolchain.main(['loot', str(self.exe)]), 0)
        self.assertEqual(json.loads(out.getvalue())['status'], 'preview')
        with patch('toolchain.subprocess.Popen', side_effect=OSError), contextlib.redirect_stderr(io.StringIO()):
            digest = toolchain.inspect_executable(self.exe)[1]
            self.assertEqual(toolchain.main(['loot', str(self.exe), '--execute', '--expected-sha256', digest,
                                            '--acknowledge-tool-side-effects']), 2)
