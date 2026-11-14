import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import toolchain

class XEditAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.exe = Path(self.tmp.name)/'SSEEdit.exe'
        self.exe.write_bytes(b'MZ00fixture-not-a-real-tool')

    def test_source_pinned_view_mode_preview(self):
        with patch('toolchain.subprocess.Popen') as start:
            report = toolchain.launch_xedit_view(self.exe)
        start.assert_not_called()
        self.assertEqual(report['argv'], [str(self.exe), '-sse', '-plugins', '-view', '-DontCache'])
        self.assertIn('0f3f6fb', report['source'])
        self.assertFalse(report['operation_completed'])
        self.assertEqual(report['execution_platform_supported'], os.name == 'nt')

    def test_native_windows_only_and_not_acceptance(self):
        digest = toolchain.launch_xedit_view(self.exe)['executable_sha256']
        with patch('toolchain.subprocess.Popen', return_value=Mock(pid=67)) as start:
            if os.name != 'nt':
                with self.assertRaises(ValueError):
                    toolchain.launch_xedit_view(self.exe, execute=True, expected_sha256=digest, acknowledge_side_effects=True)
                start.assert_not_called()
            else:
                report = toolchain.launch_xedit_view(self.exe, execute=True, expected_sha256=digest, acknowledge_side_effects=True)
                self.assertTrue(report['process_started'])
                self.assertFalse(report['native_acceptance_verified'])
                self.assertFalse(start.call_args.kwargs['shell'])

    def test_scripts_wrong_format_and_extra_arguments_rejected(self):
        self.exe.write_bytes(b'\x7fELFunsupported-for-xedit')
        with self.assertRaises(ValueError):
            toolchain.launch_xedit_view(self.exe)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            toolchain.main(['xedit-view', str(self.exe), '-quickautoclean'])

    def test_cli_preview(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(toolchain.main(['xedit-view', str(self.exe)]), 0)
        self.assertEqual(json.loads(out.getvalue())['scope'], 'external-xedit-view-launch')
