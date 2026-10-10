"""KAP financial-source guards, mocked: no API credentials/network required."""
import json
import os
import unittest
from unittest.mock import patch

from kap_financials import (
    _trusted_mkk_url,_canonical_json_to_frames,KapSchemaError,
    KapConfigurationError,configured_official_kap_ticker,
    OfficialKapStatements,
)


def payload():
    return {
        "symbol":"ASELS","financial_group":"XI_29","currency":"TRY",
        "unit_multiplier_try":1000,
        "statements":{
            "balance_sheet":[
                {"label":"Ana Ortaklığa Ait Özkaynaklar","period":"2026Q2","amount":123},
                {"label":"Toplam Varlıklar","period":"2026Q2","amount":345},
            ],
            "income_stmt":[
                {"label":"Ana Ortaklık Payları","period":"2026Q1","amount":4},
                {"label":"Ana Ortaklık Payları","period":"2026Q2","amount":10},
            ],
        },
        "annual_statements":{
            "income_stmt":[
                {"label":"Ana Ortaklık Payları","period":"2025","amount":20},
            ],
        },
    }


class KapAdapterContractTests(unittest.TestCase):
    def test_strict_symbol_currency_period_and_money_units(self):
        frames=_canonical_json_to_frames(payload(),symbol="ASELS",group="XI_29")
        self.assertEqual(frames[("quarterly","balance_sheet")].loc[
            "Ana Ortaklığa Ait Özkaynaklar","2026Q2"],123000)
        self.assertEqual(frames[("annual","income_stmt")].loc[
            "Ana Ortaklık Payları","2025"],20000)

    def test_wrong_symbol_and_undocumented_unit_fail_closed(self):
        p=payload()
        p["symbol"]="THYAO"
        with self.assertRaises(KapSchemaError):
            _canonical_json_to_frames(p,symbol="ASELS",group="XI_29")
        p=payload()
        del p["unit_multiplier_try"]
        with self.assertRaises(KapSchemaError):
            _canonical_json_to_frames(p,symbol="ASELS",group="XI_29")

    def test_bad_period_or_conflicting_fact_rejected(self):
        p=payload();p["statements"]["balance_sheet"][0]["period"]="2026-06"
        with self.assertRaises(KapSchemaError):
            _canonical_json_to_frames(p,symbol="ASELS",group="XI_29")
        p=payload()
        p["statements"]["balance_sheet"].append(
            {"label":"Toplam Varlıklar","period":"2026Q2","amount":123}
        )
        with self.assertRaises(KapSchemaError):
            _canonical_json_to_frames(p,symbol="ASELS",group="XI_29")

    def test_only_official_https_api_hosts_receive_secrets(self):
        self.assertTrue(_trusted_mkk_url(
            "https://apiportal.mkk.com.tr/financials/ASELS"))
        for unsafe in (
            "http://apiportal.mkk.com.tr/fake",
            "https://mkk.com.tr.evil.com/fake",
            "https://kap.org.tr@evil.com/fake",
            "https://apiportal.mkk.com.tr:8080/fake",
        ):
            with self.subTest(url=unsafe), self.assertRaises(KapConfigurationError):
                _trusted_mkk_url(unsafe)

    def test_no_credentials_means_existing_borsapy_fallback(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertIsNone(configured_official_kap_ticker("ASELS"))
        with patch.dict(os.environ,{"KAP_API_KEY":"secret"},clear=True):
            with self.assertRaises(KapConfigurationError):
                configured_official_kap_ticker("ASELS")

    def test_canonical_frames_are_pandas_statements(self):
        adapter=OfficialKapStatements(
            "ASELS","https://apiportal.mkk.com.tr/v1/reports/{symbol}?group={financial_group}",
            "secret",
        )
        with patch.object(adapter,"_fetch",return_value=_canonical_json_to_frames(
            payload(),symbol="ASELS",group="XI_29"
        )):
            result=adapter.get_income_stmt(quarterly=True,last_n=1)
            self.assertEqual(result.columns.tolist(),["2026Q2"])
            self.assertEqual(result.loc["Ana Ortaklık Payları","2026Q2"],10000)
            annual=adapter.get_income_stmt(quarterly=False)
            self.assertEqual(annual.loc["Ana Ortaklık Payları","2025"],20000)


if __name__=="__main__":
    unittest.main()
