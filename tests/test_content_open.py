"""Content opening must not wait on a file replaced with a FIFO."""
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


class ContentOpenTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, 'mkfifo') and hasattr(os, 'O_NONBLOCK'), 'POSIX FIFO required')
    def test_fifo_replacement_between_stat_and_open_is_bounded(self):
        # A subprocess timeout protects the suite from the original blocking open.
        script = textwrap.dedent('''
            import json, os, tempfile
            from pathlib import Path
            from unittest.mock import patch
            from asset_audit import audit, compare_contents
            with tempfile.TemporaryDirectory() as temporary:
                roots = [Path(temporary) / name for name in ('a', 'b')]
                for root in roots:
                    root.mkdir()
                    (root / 'asset.dds').write_bytes(b'one')
                report = audit(roots)
                target = roots[0] / 'asset.dds'
                real_open = os.open
                def replace_then_open(path, flags, *args, **kwargs):
                    if Path(path) == target:
                        target.unlink()
                        os.mkfifo(target)
                    return real_open(path, flags, *args, **kwargs)
                with patch('asset_audit.os.open', side_effect=replace_then_open):
                    compare_contents(report, roots)
                print(json.dumps(report))
        ''')
        result = subprocess.run([sys.executable, '-c', script], capture_output=True,
                                text=True, timeout=5, cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(0, result.returncode, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report['complete'])
        overlap = report['overlaps'][0]
        self.assertEqual('unknown', overlap['content_equivalence'])
        self.assertIsNone(overlap['proposed_winner_root'])
        self.assertNotIn('sha256', overlap['providers'][0])
        self.assertEqual(3, report['content_comparison']['bytes_read'])
        self.assertEqual('file-changed-before-read', report['errors'][0]['reason'])
