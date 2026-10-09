import unittest
import pandas as pd
from history_engine import _find_series, PARENT_EQUITY_ROWS
from statement_reconciliation import calculate_ratios

class ParentEquityTests(unittest.TestCase):
    def test_explicit_parent_line_is_preferred(self):
        d=pd.DataFrame({"2026Q2":[150,120,30]},
             index=["Özkaynaklar","Ana Ortaklığa Ait Özkaynaklar","Kontrol Gücü Olmayan Paylar"])
        series,row=_find_series(d,PARENT_EQUITY_ROWS)
        self.assertEqual(row,"Ana Ortaklığa Ait Özkaynaklar")
        self.assertEqual(float(series["2026Q2"]),120)
        self.assertAlmostEqual(calculate_ratios(1200,100,120)["pb"],10)
    def test_unattributed_total_is_not_parent(self):
        d=pd.DataFrame({"2026Q2":[150]},
             index=["Özkaynaklar"])
        series,row=_find_series(d,PARENT_EQUITY_ROWS)
        self.assertIsNone(row)
        self.assertTrue(series.empty)

if __name__=="__main__":
    unittest.main()
