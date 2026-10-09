import unittest
from statement_reconciliation import calculate_ratios, reconcile, diagnose_pb_denominator, implied_parent_equity_from_vendor_pb

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
    def test_pb_provider_implied_equity_is_not_audited(self):
        diagnostic=diagnose_pb_denominator(
            market_cap_try=100.0,vendor_pb=1.0,
            consolidated_equity_try=250.0,parent_equity_try=100.0
        )
        self.assertAlmostEqual(diagnostic["vendor_implied_equity_try"],100.0)
        self.assertAlmostEqual(diagnostic["total_equity_gap_fraction"],0.6)
        self.assertEqual(diagnostic["classification"],"PARENT_CANDIDATE_TIME_UNVERIFIED")
        self.assertFalse(diagnostic["is_independent_confirmation"])

    def test_pb_negative_multiple_does_not_produce_false_parent_equity(self):
        self.assertIsNone(implied_parent_equity_from_vendor_pb(100,-1))
        self.assertEqual(diagnose_pb_denominator(100,-1,100,None)["classification"],"UNVERIFIABLE")

    def test_subunit_pb_relative_gap(self):
        # A 0.30 gap between P/B=0.50 and 0.80 is economically material,
        # even though its absolute value is smaller than 0.35.
        self.assertEqual(reconcile(0.5, 0.8), "REVIEW")
        self.assertEqual(reconcile(0.8, 0.5), "REVIEW")
        self.assertEqual(reconcile(0.8, 0.82), "WITHIN_TOLERANCE")
        self.assertEqual(reconcile(0.1, 0.12), "REVIEW")

    def test_comparison(self):
        self.assertEqual(reconcile(10,11),"WITHIN_TOLERANCE")
        self.assertEqual(reconcile(10,25),"REVIEW")
        self.assertEqual(reconcile(None,25),"UNVERIFIABLE")

if __name__=="__main__":
    unittest.main()
