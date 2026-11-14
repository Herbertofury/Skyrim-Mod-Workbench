"""Executable fingerprint must describe the selected opened file, not a namesake."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import toolchain

class ToolIdentityTests(unittest.TestCase):
    def test_substituted_open_handle_is_rejected_before_fingerprinting(self):
        with tempfile.TemporaryDirectory() as tmp:
            selected=Path(tmp)/'selected.exe'; other=Path(tmp)/'other.exe'
            magic=b'MZ00' if os.name=='nt' else b'\x7fELF'
            selected.write_bytes(magic+b'AAAA');other.write_bytes(magic+b'BBBB')
            real_open=Path.open
            def swapped(path,*args,**kwargs):
                return real_open(other if path==selected else path,*args,**kwargs)
            with patch.object(Path,'open',swapped), patch('toolchain.subprocess.Popen') as start:
                with self.assertRaisesRegex(ValueError,'changed before'):
                    toolchain.inspect_executable(selected)
            start.assert_not_called()

    def test_open_descriptor_metadata_change_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            selected=Path(tmp)/'selected.exe'; selected.write_bytes((b'MZ00' if os.name=='nt' else b'\x7fELF')+b'fixture')
            real_fstat=os.fstat; calls=0
            def changed(fd):
                nonlocal calls
                calls+=1
                current=real_fstat(fd)
                if calls==2:
                    class Observed:
                        def __getattr__(self,key):
                            return getattr(current,key)+(1 if key=='st_ctime_ns' else 0)
                    return Observed()
                return current
            with patch('toolchain.os.fstat',side_effect=changed):
                with self.assertRaisesRegex(ValueError,'changed during'):
                    toolchain.inspect_executable(selected)

    def test_unchanged_native_fixture_digest_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fixture.exe';b=(b'MZ00' if os.name=='nt' else b'\x7fELF')+b'not-a-real-tool';p.write_bytes(b)
            self.assertEqual(toolchain.inspect_executable(p),(p,hashlib.sha256(b).hexdigest()))
