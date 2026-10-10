"""Contract tests for independently recalculated company peer cohorts."""
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

from statement_metrics import STANDARD_KEYS
from statement_peers import make_snapshot, read_snapshot, peer_distributions


def example_rows():
    rows = []
    for sym, value, q, industry, profile, sector, xu in [
        ("AAA", 10, "2026Q2", "Steel", "Sanayi", "Metal", True),
        ("BBB", 12, "2026Q2", "Steel", "Sanayi", "Metal", True),
        ("CCC", 14, "2026Q2", "Steel", "Sanayi", "Metal", True),
        ("DDD", 16, "2026Q1", "Steel", "Sanayi", "Metal", False),
        ("EEE", 50, "2024Q2", "Steel", "Sanayi", "Metal", False),
        ("FFF", 5, "2026Q2", "Bank", "Banka", "Finance", True),
        ("GGG", 6, "2026Q2", "Bank", "Banka", "Finance", True),
        ("HHH", 8, "2026Q2", "Broker", "Finansal", "Finance", True),
    ]:
        r = {
            "symbol":sym, "sector":sector, "industry":industry,
            "profile":profile, "is_xu100":xu, "status":"OK",
            "financial_period":q,
        }
        for k in STANDARD_KEYS:
            r["statement_" + k] = value if k=="pe" else None
            r["statement_" + k + "_status"] = "CALCULATED" if k=="pe" else "UNAVAILABLE"
        rows.append(r)
    return pd.DataFrame(rows)


class StandardPeerBenchmarksTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026,10,10,12,0,tzinfo=timezone.utc)
        self.df = make_snapshot(example_rows(),engine_version="test",
                                created_at=self.now)

    def test_no_provider_ratio_leakage(self):
        source=example_rows()
        source["price_earnings_ttm"]=999
        source.loc[source.symbol=="DDD","statement_pe_status"]="UNAVAILABLE"
        snap=make_snapshot(source,engine_version="test",created_at=self.now)
        self.assertTrue(pd.isna(snap.loc[snap.symbol=="DDD","statement_pe"].iloc[0]))
        self.assertNotIn("price_earnings_ttm", snap)

    def test_peers_match_statement_period_and_exclude_target(self):
        stats=peer_distributions(
            self.df,symbol="AAA",sector="Metal",industry="Steel",
            profile="Sanayi",quarter="2026Q2",
            metrics={"pe":11},directions={"pe":"low"},min_n=2
        )
        # BBB, CCC, DDD included; older EEE and target AAA excluded.
        self.assertEqual(stats["pe"]["industry"]["n"],3)
        self.assertEqual(stats["pe"]["industry"]["median"],14)
        self.assertAlmostEqual(stats["pe"]["industry"]["pct"],100)
        self.assertEqual(stats["pe"]["sector"]["median"],14)

    def test_sparse_cohort_reports_na_not_fake_percentiles(self):
        x=peer_distributions(
            self.df,symbol="DDD",sector="Metal",industry="Steel",
            profile="Sanayi",quarter="2026Q2",
            metrics={"pe":11},directions={"pe":"low"},min_n=10
        )
        self.assertIsNone(x["pe"]["sector"]["median"])
        self.assertIsNone(x["pe"]["sector"]["pct"])
        self.assertEqual(x["pe"]["sector"]["n"],3)

    def test_financial_sectors_respect_profile(self):
        x=peer_distributions(
            self.df,symbol="FFF",sector="Finance",industry="Bank",
            profile="Banka",quarter="2026Q2",
            metrics={"pe":7},directions={"pe":"low"},min_n=1
        )
        self.assertEqual(x["pe"]["sector"]["n"],1)
        self.assertEqual(x["pe"]["sector"]["median"],6)

    def test_snapshot_freshness_version_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"snapshot.csv"
            self.df.to_csv(path,index=False)
            self.assertIsNotNone(read_snapshot(
                path,engine_version="test",now=self.now + timedelta(hours=1)))
            self.assertIsNone(read_snapshot(
                path,engine_version="mismatch",now=self.now))
            self.assertIsNone(read_snapshot(
                path,engine_version="test",now=self.now + timedelta(days=20)))
            self.assertIsNone(read_snapshot(
                path,engine_version="test",now=self.now - timedelta(days=1)))

    def test_duplicate_issuer_is_rejected(self):
        with self.assertRaises(ValueError):
            make_snapshot(pd.concat([example_rows(),example_rows().iloc[:1]]),
                          engine_version="test",created_at=self.now)

    def test_no_future_data_leakage(self):
        x=peer_distributions(
            self.df,symbol="AAA",sector="Metal",industry="Steel",
            profile="Sanayi",quarter="2026Q1",
            metrics={"pe":15},directions={"pe":"low"},min_n=1
        )
        self.assertEqual(x["pe"]["industry"]["n"],1)


if __name__=="__main__":
    unittest.main()
