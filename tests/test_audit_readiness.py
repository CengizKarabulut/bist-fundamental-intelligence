import unittest
from audit_readiness import readiness_from_audit

class AuditReadinessTests(unittest.TestCase):
    def test_clean_operating_company(self):
        self.assertEqual(readiness_from_audit({"profile":"Genel","status":"OK","issues":[]})[0],"READY")
    def test_provider_warning(self):
        self.assertEqual(readiness_from_audit({"profile":"Genel","status":"WARNING","issues":[{"code":"PROVIDER_CONFLICT"}]})[0],"REVIEW")
    def test_missing_history(self):
        self.assertEqual(readiness_from_audit({"profile":"Finansal","status":"WARNING","issues":[{"code":"HISTORY_UNAVAILABLE"}]})[0],"PARTIAL")
    def test_nav_required(self):
        self.assertEqual(readiness_from_audit({"profile":"GYO","status":"OK","issues":[]})[0],"VALUATION_PARTIAL")
    def test_critical_overrides(self):
        self.assertEqual(readiness_from_audit({"profile":"GYO","status":"CRITICAL","issues":[]})[0],"REVIEW")

if __name__=="__main__":
    unittest.main()
