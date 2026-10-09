import unittest
import pandas as pd
from analyze import dedupe


class ShareClassSelectionTests(unittest.TestCase):
    def test_choose_liquid_representative_instead_of_artificially_large_class(self):
        rows = pd.DataFrame([
            {"symbol":"ISBTR","description":"Turkiye Is Bankasi Anonim Sirketi Class B","market_cap_basic":1.0e15},
            {"symbol":"ISCTR","description":"Turkiye Is Bankasi Anonim Sirketi Class C","market_cap_basic":2.0e11},
            {"symbol":"KRDMA","description":"Kardemir Karabiik Demir celik Sanayi ve Ticaret A.S. Class A","market_cap_basic":1.0e12},
            {"symbol":"KRDMD","description":"Kardemir Karabiik Demir celik Sanayi ve Ticaret A.S. Class D","market_cap_basic":5.0e10},
            {"symbol":"OTHER","description":"Independent Co","market_cap_basic":1.0e9},
        ])
        out=dedupe(rows)
        self.assertEqual(len(out),3)
        self.assertEqual(set(out["symbol"]),{"ISCTR","KRDMD","OTHER"})

    def test_known_class_absent_preserves_available_stock(self):
        rows=pd.DataFrame([
            {"symbol":"ISBTR","description":"Turkiye Is Bankasi Anonim Sirketi Class B","market_cap_basic":100.0},
            {"symbol":"ISATR","description":"Turkiye Is Bankasi Anonim Sirketi Class A","market_cap_basic":30.0}
        ])
        self.assertEqual(dedupe(rows)["symbol"].tolist(),["ISBTR"])

    def test_unrelated_issuers_are_not_merged(self):
        rows=pd.DataFrame([
            {"symbol":"AAA","description":"Independent AA","market_cap_basic":100.0},
            {"symbol":"BBB","description":"Independent BB","market_cap_basic":200.0}
        ])
        self.assertEqual(len(dedupe(rows)),2)


if __name__=="__main__":
    unittest.main()
