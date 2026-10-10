"""Statement-first financial formula regression fixtures: no network required."""
import unittest
from statement_metrics import derive_statement_ratios, STANDARD_KEYS


def fixture():
    period="2026Q2"
    return {
        "financial_group_used":"XI_29",
        "rows_found":{
            "net_income":"Ana Ortaklık Payları",
            "total_net_income":"NET DÖNEM KARI (ZARARI)",
            "parent_equity":"Ana Ortaklığa Ait Özkaynaklar",
        },
        "summary":{
            "latest_period":period,
            "ttm_net_income":100,
            "ttm_total_net_income":90,
            "parent_equity":500,
            "total_assets":1500,
            "avg_parent_equity_ttm":400,
            "avg_assets_ttm":1200,
            "ttm_ebitda":100,
            "ttm_ebitda_reporting_period":period,
            "ttm_ebitda_source":"EXPLICIT_INCOME_STATEMENT",
            "net_debt_statement":250,
            "net_debt_statement_period_aligned":True,
            "financial_debt":300,
            "current_assets":500,
            "current_liabilities":200,
            "inventories":100,
            "ttm_revenue":800,
            "ttm_gross_profit":400,
            "ttm_operating_profit":200,
            "ttm_free_cash_flow":120,
            "ttm_free_cash_flow_source":"EXPLICIT_CASHFLOW",
            "revenue_ttm_yoy":18,
            "net_income_ttm_yoy":25,
            "balance_input_periods":{
                x:period for x in ("parent_equity","total_assets","financial_debt",
                                  "cash","current_assets","current_liabilities",
                                  "inventories","financial_investments")},
            "flow_input_periods":{
                x:period for x in ("net_income","total_net_income","revenue",
                                  "gross_profit","operating_profit","free_cash_flow",
                                  "operating_cash_flow","capex")},
        },
    }


class StandardStatementEngineTests(unittest.TestCase):
    def test_standardized_industrial_ratios(self):
        a=derive_statement_ratios(fixture(),1000,"Sanayi")
        self.assertEqual(set(a),set(STANDARD_KEYS))
        expected={
            "pe":10,"pb":2,"ev":12.5,"roe":25,"roa":7.5,
            "curr":2.5,"quick":2,"de":0.6,"nde":2.5,
            "eq_assets":1/3,"gross":50,"opm":25,"netm":11.25,
            "ebitdam":12.5,"rev_g":18,"ni_g":25,
            "fcfm":15,"pfcf":1000/120,
        }
        for key,val in expected.items():
            with self.subTest(key=key):
                self.assertAlmostEqual(a[key]["value"],val)
                self.assertEqual(a[key]["status"],"CALCULATED")
                self.assertEqual(a[key]["reporting_period"],"2026Q2")

    def test_provider_ratio_is_never_substituted(self):
        h=fixture();h["market"]={"pe":3,"pb":0.4}
        h["summary"]["parent_equity"]=None
        a=derive_statement_ratios(h,1000,"Sanayi")
        self.assertIsNone(a["pb"]["value"])
        self.assertEqual(a["pb"]["status"],"UNAVAILABLE")
        self.assertEqual(a["pe"]["value"],10)

    def test_parent_ownership_basis_is_strict(self):
        h=fixture();h["rows_found"]["net_income"]="Net Dönem Karı"
        a=derive_statement_ratios(h,1000,"Sanayi")
        self.assertIsNone(a["pe"]["value"])
        self.assertIsNone(a["roe"]["value"])
        self.assertEqual(a["roa"]["value"],7.5)

    def test_no_mixed_quarter_data(self):
        h=fixture();h["summary"]["balance_input_periods"]["parent_equity"]="2026Q1"
        h["summary"]["flow_input_periods"]["net_income"]="2026Q1"
        a=derive_statement_ratios(h,1000,"Sanayi")
        self.assertIsNone(a["pe"]["value"])
        self.assertIsNone(a["pb"]["value"])
        self.assertIsNone(a["roe"]["value"])

    def test_negative_income_and_cash_flow_are_not_value_multiples(self):
        h=fixture();h["summary"]["ttm_net_income"]=-100
        h["summary"]["ttm_free_cash_flow"]=-50
        a=derive_statement_ratios(h,1000,"Sanayi")
        self.assertIsNone(a["pe"]["value"])
        self.assertIsNone(a["pfcf"]["value"])
        self.assertEqual(a["roe"]["value"],-25)
        self.assertAlmostEqual(a["fcfm"]["value"],-6.25)

    def test_bank_and_sector_rules(self):
        a=derive_statement_ratios(fixture(),1000,"Banka")
        self.assertEqual(a["ev"]["status"],"NOT_APPLICABLE")
        self.assertEqual(a["de"]["status"],"NOT_APPLICABLE")
        self.assertEqual(a["quick"]["status"],"NOT_APPLICABLE")
        self.assertEqual(a["pb"]["value"],2)
        self.assertEqual(a["roe"]["value"],25)

    def test_missing_period_does_not_make_number_up(self):
        h=fixture();h["summary"]["latest_period"]=None
        a=derive_statement_ratios(h,1000,"Sanayi")
        self.assertTrue(all(row["value"] is None for row in a.values()))

    def test_fcf_reconstruction_must_match_period(self):
        h=fixture()
        h["summary"]["ttm_free_cash_flow_source"]="RECONSTRUCTED_CFO_MINUS_CAPEX"
        h["summary"]["flow_input_periods"]["capex"]="2026Q1"
        a=derive_statement_ratios(h,1000,"Sanayi")
        self.assertIsNone(a["pfcf"]["value"])

    def test_financial_ratio_uses_price_input_not_vendor_pe(self):
        h=fixture()
        self.assertEqual(derive_statement_ratios(h,2000,"Sanayi")["pe"]["value"],20)


if __name__=="__main__":
    unittest.main()
