"""Deterministic accounting guards for BIST statement reconstruction."""
import unittest
import pandas as pd
from history_engine import (
    _ttm, _ttm_yoy, _net_debt_if_complete,
    _average_positive_balance, _discrete_from_ytd,
)

class AccountingGuards(unittest.TestCase):
    def test_ttm_contiguous(self):
        s=pd.Series({"2025Q1":10,"2025Q2":20,"2025Q3":30,"2025Q4":40,
                     "2026Q1":50,"2026Q2":60,"2026Q3":70,"2026Q4":80})
        self.assertEqual(_ttm(s),260)
        self.assertAlmostEqual(_ttm_yoy(s),160.0)

    def test_sparse_quarters_do_not_fake_ttm(self):
        s=pd.Series({"2025Q2":20,"2025Q3":30,"2026Q1":50,"2026Q4":80})
        self.assertIsNone(_ttm(s))
        self.assertIsNone(_ttm_yoy(s))

    def test_discrete_ytd_is_consistent(self):
        ytd=pd.Series({"2025Q1":10,"2025Q2":30,"2025Q3":60,"2025Q4":100})
        self.assertEqual(_ttm(_discrete_from_ytd(ytd)),100)

    def test_missing_net_debt_inputs_not_zero(self):
        self.assertIsNone(_net_debt_if_complete(100,None,20))
        self.assertIsNone(_net_debt_if_complete(100,30,None))
        self.assertEqual(_net_debt_if_complete(100,30,20),50)
        self.assertEqual(_net_debt_if_complete(100,0,0),100)

    def test_roe_roa_need_averaged_positive_denominator(self):
        self.assertIsNone(_average_positive_balance(100,None))
        self.assertIsNone(_average_positive_balance(-100,0))
        self.assertEqual(_average_positive_balance(100,200),150)

if __name__=="__main__":
    unittest.main()
