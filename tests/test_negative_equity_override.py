"""Regression: negative equity values are reported but NEVER scoreable."""
import unittest
from analyze import _apply_independent_statement_factors, M


class NegativeEquityScoringTests(unittest.TestCase):
    def test_nonpositive_equity_disables_all_capital_quality_scores(self):
        keys=("roe","pb","de","eq_assets")
        metrics={}
        statements={}
        for k in keys:
            metrics[k]={
                "v":42,"source":"vendor","app":True,"scoreable":True,
                "abs":85.0,"groups":{
                    g:{"median":10,"pct":45,"n":20}
                    for g in ("industry","sector","xu100","bist")
                },
            }
            statements[k]={
                "value": -100 if k in ("roe","eq_assets") else None,
                "status": "CALCULATED" if k in ("roe","eq_assets") else "UNAVAILABLE",
            }
        history={"summary":{"equity":-10,"parent_equity":-10}}
        got=_apply_independent_statement_factors(
            metrics, "Genel", {}, statements, history
        )
        self.assertEqual(got["roe"]["v"],-100)
        self.assertEqual(got["eq_assets"]["v"],-100)
        for k in keys:
            self.assertFalse(got[k]["scoreable"],k)
            self.assertIsNone(got[k]["abs"],k)

    def test_empty_historical_record_does_not_leave_vendor_ratios_scoreable(self):
        metrics={"pb":{
            "v":1.5,"source":"TradingView","app":True,
            "scoreable":True,"abs":90,"groups":{},
        }}
        statements={"pb":{"value":None,"status":"UNAVAILABLE"}}
        got=_apply_independent_statement_factors(
            metrics,"Genel",{},statements,{"summary":{}}
        )
        self.assertIsNone(got["pb"]["v"])
        self.assertFalse(got["pb"]["scoreable"])


if __name__=="__main__":
    unittest.main()
