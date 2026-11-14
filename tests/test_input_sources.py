import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class InputSourceTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', 'POSIX special-file coverage')
    def test_export_and_manifest_fifo_fail_without_waiting_for_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input';os.mkfifo(path)
            for command,status in [('workbench.py','invalid-input'),('mo2_profile.py','invalid-mo2-export')]:
                with self.subTest(command=command):
                    result=subprocess.run([sys.executable,str(ROOT/command),str(path)],capture_output=True,text=True,timeout=2)
                    self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,'')
                    self.assertEqual(json.loads(result.stderr)['status'],status)
    def test_regular_file_boundary_and_invalid_limits(self):
        from input_files import read_bounded
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input';path.write_bytes(b'abcd')
            self.assertEqual(read_bounded(path,4),b'abcd')
            for limit in (3,-1,True,1.5):
                with self.subTest(limit=limit),self.assertRaises(ValueError):read_bounded(path,limit)
            path.write_bytes(b'');self.assertEqual(read_bounded(path,0),b'')
    @unittest.skipUnless(os.name == 'posix', 'symlink creation permissions vary on Windows')
    def test_regular_file_symlink_preserved(self):
        from input_files import read_bounded
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'file';path.write_bytes(b'abc');link=Path(tmp)/'link';link.symlink_to(path)
            self.assertEqual(read_bounded(link,3),b'abc')
    def test_growth_beyond_bound_is_rejected_after_read(self):
        from input_files import read_bounded
        from unittest.mock import patch, Mock
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'file';path.write_bytes(b'abcde')
            with patch.object(Path,'stat',return_value=Mock(st_mode=0o100600,st_size=0)),patch('input_files.os.fstat',return_value=Mock(st_mode=0o100600,st_size=0)):
                with self.assertRaisesRegex(ValueError,'byte limit'):read_bounded(path,4)
