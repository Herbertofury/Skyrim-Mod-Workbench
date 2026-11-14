import unittest
from report_html import render_report
from header_compare import compare
from test_header_compare import report

class ComparisonViewTests(unittest.TestCase):
    def test_actual_field_differences_are_readable_not_only_raw_json(self):
        result=compare(report(masters=['Base.esm']),report(masters=['Next.esm'],flags=0x200))
        html=render_report(result,historical=True).split('<details><summary>Complete machine-readable')[0]
        for text in ('Changed header fields','<td>masters</td>','Base.esm','Next.esm','<td>flags</td>','<td>0</td>','<td>512</td>',result['before_report_sha256']):self.assertIn(text,html)
        self.assertIn('Historical snapshot',html);self.assertIn('do not establish FormID',html)
    def test_added_removed_and_incomplete_errors_are_explicit_and_escaped(self):
        a=report('Old.esp');b=report('New.esp');b.update(complete=False,errors=[{'name':'<script>bad</script>'}]);r=compare(a,b)
        html=render_report(r,historical=True).split('<details><summary>Complete machine-readable')[0]
        for text in ('incomplete-comparison','Added within supplied evidence','Removed from supplied evidence','Old.esp','New.esp','Incomplete source evidence','&lt;script&gt;'):self.assertIn(text,html)
        self.assertNotIn('<script',html)
