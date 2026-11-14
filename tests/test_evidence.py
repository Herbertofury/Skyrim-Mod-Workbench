import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from evidence import save_report, load_report, envelope
from workbench import diagnose
from test_workbench import manifest, plugin


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.target=self.base/'receipt.json'
        self.report=diagnose(manifest(plugin('A.esp',['Missing.esm'])))

    def test_round_trip_including_failures(self):
        receipt=save_report(self.report,self.target)
        self.assertTrue(receipt['published']);self.assertTrue(receipt['file_fsynced'])
        self.assertEqual(self.report,load_report(self.target))
        self.assertEqual([self.target],list(self.base.iterdir()))

    def test_existing_receipt_never_overwritten(self):
        self.target.write_bytes(b'last good')
        with self.assertRaises(FileExistsError):save_report(self.report,self.target)
        self.assertEqual(b'last good',self.target.read_bytes())

    def test_atomic_race_preserves_other_writer(self):
        real=os.link
        def race(source,target):
            Path(target).write_bytes(b'other writer')
            return real(source,target)
        with patch('evidence.os.link',side_effect=race),self.assertRaises(FileExistsError):
            save_report(self.report,self.target)
        self.assertEqual(b'other writer',self.target.read_bytes())
        self.assertEqual([self.target],list(self.base.iterdir()))

    def test_file_fsync_failure_does_not_publish(self):
        with patch('evidence.os.fsync',side_effect=OSError('disk error')),self.assertRaises(OSError):
            save_report(self.report,self.target)
        self.assertFalse(self.target.exists());self.assertEqual([],list(self.base.iterdir()))

    @unittest.skipUnless(os.name=='posix','directory fsync is POSIX-only')
    def test_directory_fsync_failure_reports_existing_file(self):
        original=os.fsync;calls=0
        def failing(fd):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('directory flush error')
            return original(fd)
        with patch('evidence.os.fsync',side_effect=failing):receipt=save_report(self.report,self.target)
        self.assertTrue(receipt['published']);self.assertEqual('unconfirmed',receipt['directory_fsync'])
        self.assertEqual(self.report,load_report(self.target))

    def test_corruption_duplicate_keys_version_and_native_claim_rejected(self):
        good=json.loads(envelope(self.report))
        cases=[]
        changed=json.loads(json.dumps(good));changed['report']['status']='healthy';cases.append(json.dumps(changed))
        changed=json.loads(json.dumps(good));changed['evidence_version']=True;cases.append(json.dumps(changed))
        cases.extend(['{}','{"report":{},"report":{}}',envelope(self.report).decode()[:-5]])
        for content in cases:
            self.target.write_text(content)
            with self.assertRaises(ValueError):load_report(self.target)
        with self.assertRaises(ValueError):envelope({'schema_version':1,'game_verified':True})

    def test_cli_save_preserves_findings_and_verify_is_historical(self):
        source=self.base/'input.json';source.write_text(json.dumps(manifest(plugin('A.esp',['Missing.esm']))))
        before=source.read_bytes()
        result=subprocess.run([sys.executable,'workbench.py',str(source),'--save-report',str(self.target)],capture_output=True)
        self.assertEqual(1,result.returncode)
        self.assertTrue(json.loads(result.stderr)['evidence_save']['published'])
        verified=subprocess.run([sys.executable,'evidence.py',str(self.target)],capture_output=True)
        self.assertEqual(0,verified.returncode)
        value=json.loads(verified.stdout);self.assertTrue(value['historical']);self.assertFalse(value['current_files_verified'])
        self.assertEqual(before,source.read_bytes())
        again=subprocess.run([sys.executable,'workbench.py',str(source),'--save-report',str(self.target)],capture_output=True)
        self.assertEqual(2,again.returncode)
        self.assertEqual(self.report,load_report(self.target))

    def test_cleanup_error_does_not_hide_publication(self):
        original=Path.unlink
        def fail_temp(path,*args,**kwargs):
            if path.name.startswith('.workbench-evidence-'):raise PermissionError('cleanup denied')
            return original(path,*args,**kwargs)
        with patch('evidence.Path.unlink',fail_temp):receipt=save_report(self.report,self.target)
        self.assertTrue(receipt['published']);self.assertFalse(receipt['temporary_removed'])
        self.assertEqual(self.report,load_report(self.target))

    @unittest.skipUnless(os.name == 'posix', 'directory descriptors are POSIX-only')
    def test_directory_close_error_does_not_hide_publication(self):
        real_close = os.close
        def failed_close(fd):
            # Model an error returned after closing the directory descriptor.
            real_close(fd)
            raise OSError('directory close error')
        with patch('evidence.os.close', side_effect=failed_close):
            receipt = save_report(self.report, self.target)
        self.assertTrue(receipt['published'])
        self.assertTrue(receipt['file_fsynced'])
        self.assertEqual('unconfirmed', receipt['directory_fsync'])
        self.assertEqual(self.report, load_report(self.target))
        with self.assertRaises(FileExistsError):
            save_report(self.report, self.target)
