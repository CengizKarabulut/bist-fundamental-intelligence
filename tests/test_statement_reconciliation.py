import unittest
from statement_reconciliation import calculate_ratios, reconcile

class StatementReconciliationTests(unittest.TestCase):
    def test_independent_pe_pb_ev(self):
        r=calculate_ratios(1000,100,500,200,150)
        self.assertAlmostEqual(r["pe"],10)
        self.assertAlmostEqual(r["pb"],2)
        self.assertAlmostEqual(r["ev"],8)
    def test_no_guessed_ebitda(self):
        self.assertIsNone(calculate_ratios(1000,100,500,200,None)["ev"])
    def test_missing_equity_and_profit(self):
        r=calculate_ratios(1000,None,None,None,None)
        self.assertIsNone(r["pe"])
        self.assertIsNone(r["pb"])
    def test_negative_profits_not_cheap(self):
        self.assertIsNone(calculate_ratios(1000,-10,-5,None,None)["pe"])
    def test_comparison(self):
        self.assertEqual(reconcile(10,11),"WITHIN_TOLERANCE")
        self.assertEqual(reconcile(10,25),"REVIEW")
        self.assertEqual(reconcile(None,25),"UNVERIFIABLE")

if __name__=="__main__":
    unittest.main()
