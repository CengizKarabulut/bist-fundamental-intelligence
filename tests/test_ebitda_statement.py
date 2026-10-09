"""Deterministic tests of the statement-derived industrial EBITDA layer."""
import unittest
import pandas as pd
from history_engine import _statement_ebitda_ttm
from statement_reconciliation import calculate_ratios

def quarters(vals):
    keys=["2025Q3","2025Q4","2026Q1","2026Q2"]
    return pd.Series(dict(zip(keys, vals)), dtype=float)

class EbitdaTests(unittest.TestCase):
    def test_explicit_ebitda_four_contiguous_quarters(self):
        value,source=_statement_ebitda_ttm(
            quarters([80,100,120,140]),
            quarters([10,10,10,10]),
            quarters([20,20,20,20]),
            (2026,2),"Genel")
        self.assertEqual(value,440)
        self.assertEqual(source,"EXPLICIT_INCOME_STATEMENT")

    def test_reconstructed_ebitda_is_labeled(self):
        value,source=_statement_ebitda_ttm(
            pd.Series(dtype=float),
            quarters([60,65,70,75]),
            quarters([-10,-11,-12,-13]),
            (2026,2),"Genel")
        self.assertEqual(value,316)
        self.assertEqual(source,"RECONSTRUCTED_OPERATING_PROFIT_PLUS_DA")

    def test_gapped_quarters_are_not_summed(self):
        operating=pd.Series({
            "2025Q2":50,"2025Q3":50,"2026Q1":50,"2026Q2":50},dtype=float)
        value,source=_statement_ebitda_ttm(
            pd.Series(dtype=float),operating,quarters([10,10,10,10]),
            (2026,2),"Genel")
        self.assertIsNone(value)
        self.assertEqual(source,"UNAVAILABLE")

    def test_stale_ebitda_not_used(self):
        value,source=_statement_ebitda_ttm(
            quarters([50,50,50,50]),pd.Series(dtype=float),
            pd.Series(dtype=float),(2026,3),"Genel")
        self.assertIsNone(value)
        self.assertEqual(source,"UNAVAILABLE")

    def test_nonindustrial_profile_has_no_ebitda(self):
        value,source=_statement_ebitda_ttm(
            quarters([50,50,50,50]),pd.Series(dtype=float),
            pd.Series(dtype=float),(2026,2),"Banka")
        self.assertIsNone(value)
        self.assertEqual(source,"NOT_APPLICABLE")

    def test_ev_needs_real_net_debt(self):
        self.assertIsNone(calculate_ratios(1000,100,500,None,100)["ev"])
        self.assertEqual(calculate_ratios(1000,100,500,200,100)["ev"],12)

if __name__=="__main__":
    unittest.main()
