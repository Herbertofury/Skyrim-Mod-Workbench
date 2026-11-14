import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import evidence
from workbench import diagnose

class EvidenceHTMLTests(unittest.TestCase):
    def invoke(self,args):
        out=io.StringIO();err=io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):code=evidence.main(args)
        return code,out.getvalue(),err.getvalue()
    def test_verified_view_is_explicitly_historical_and_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'saved.json';r=diagnose({'schema_version':1,'plugins':[{'name':'A.esp','enabled':True,'masters':['Missing.esm']}]})
            r['note']='<script>bad()</script>';evidence.save_report(r,p);before=p.read_bytes()
            code,out,err=self.invoke([str(p),'--html'])
            self.assertEqual(code,0);self.assertEqual(err,'');self.assertEqual(p.read_bytes(),before)
            for text in ('Historical snapshot','integrity verified only','No files were rescanned','Missing.esm','&lt;script&gt;'):self.assertIn(text,out)
            self.assertNotIn('<script',out)
            code,out,err=self.invoke([str(p)]);self.assertTrue(json.loads(out)['historical'])
    def test_tampered_evidence_never_renders(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'saved.json';p.write_bytes(evidence.envelope({'schema_version':1,'game_verified':False}))
            p.write_text(p.read_text().replace('"game_verified":false','"game_verified":true'))
            code,out,err=self.invoke([str(p),'--html']);self.assertEqual(code,2);self.assertEqual(out,'');self.assertEqual(json.loads(err)['status'],'invalid-evidence')
    def test_integrity_valid_unknown_shape_reports_view_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'saved.json';p.write_bytes(evidence.envelope({'schema_version':1,'game_verified':False}))
            code,out,err=self.invoke([str(p),'--html']);self.assertEqual(code,2);self.assertEqual(out,'');self.assertTrue(json.loads(err)['integrity_verified']);self.assertEqual(json.loads(err)['status'],'unsupported-report-view')
