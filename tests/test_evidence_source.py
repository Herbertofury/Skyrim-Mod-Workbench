"""Evidence verification must not block on named pipes or read special devices."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
import evidence

class EvidenceSourceTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os,'mkfifo'),'requires POSIX FIFO')
    def test_fifo_cli_rejects_promptly_without_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            fifo=Path(tmp)/'receipt';os.mkfifo(fifo)
            try:
                r=subprocess.run([sys.executable,str(Path(evidence.__file__)),str(fifo)],capture_output=True,text=True,timeout=2)
            except subprocess.TimeoutExpired:
                self.fail('evidence verifier blocked opening a FIFO with no writer')
            self.assertEqual(r.returncode,2);self.assertIn('invalid-evidence',r.stderr);self.assertEqual(r.stdout,'')

    @unittest.skipUnless(hasattr(os,'mkfifo') and hasattr(os,'O_NONBLOCK'),'requires POSIX nonblocking FIFO')
    def test_fifo_replacement_after_preflight_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fifo=Path(tmp)/'receipt';os.mkfifo(fifo)
            # Simulate the preflight having seen the regular file before swap.
            with patch.object(Path,'stat',return_value=Mock(st_mode=0o100600)):
                with self.assertRaisesRegex(ValueError,'regular file'):
                    evidence.load_report(fifo)

    def test_directory_rejected_before_open(self):
        with tempfile.TemporaryDirectory() as tmp, patch('evidence.open',create=True) as opened:
            with self.assertRaises(ValueError):evidence.load_report(tmp)
            opened.assert_not_called()

    def test_regular_saved_snapshot_still_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'receipt';r={'schema_version':1,'game_verified':False};evidence.save_report(r,p)
            self.assertEqual(evidence.load_report(p),r)
