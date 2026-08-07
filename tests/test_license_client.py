import unittest
import os
import shutil
import tempfile
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

import license_client
import app as application


class TestLicenseClient(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.old_data_dir = license_client.DATA_DIR
        self.old_file = license_client.LICENSE_FILE
        self.old_id_file = license_client.INSTANCE_ID_FILE

        license_client.DATA_DIR = self.test_dir
        license_client.LICENSE_FILE = os.path.join(self.test_dir, "license.json")
        license_client.INSTANCE_ID_FILE = os.path.join(self.test_dir, "instance_id.txt")

    def tearDown(self):
        license_client.DATA_DIR = self.old_data_dir
        license_client.LICENSE_FILE = self.old_file
        license_client.INSTANCE_ID_FILE = self.old_id_file
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_get_machine_fingerprint_stability(self):
        fp1 = license_client.get_machine_fingerprint()
        fp2 = license_client.get_machine_fingerprint()
        self.assertEqual(fp1, fp2)
        self.assertEqual(len(fp1), 64)  # SHA-256 hex length

    def test_default_license_state(self):
        lic = license_client.get_license()
        self.assertEqual(lic["status"], "unlicensed")
        self.assertEqual(lic["license_key"], "")
        self.assertIn("fingerprint", lic)

    @patch("license_client._send_request")
    def test_activate_success(self, mock_send):
        mock_send.return_value = (200, {
            "status": "active",
            "token": "hmac_signed_token_example",
            "expires_at": "2027-01-01T00:00:00Z",
            "grace_days": 3,
            "entitlements": {"PRO_FEATURES": True}
        }, None)

        success, msg, status = license_client.activate("ABCD-1234-EFGH")
        self.assertTrue(success)
        self.assertEqual(status, "active")

        # Pastikan data terisi di get_license()
        lic = license_client.get_license()
        self.assertEqual(lic["status"], "active")
        self.assertEqual(lic["license_key"], "ABCD-1234-EFGH")
        self.assertEqual(lic["token"], "hmac_signed_token_example")

    @patch("license_client._send_request")
    def test_activate_seat_full(self, mock_send):
        mock_send.return_value = (200, {
            "status": "seat_full",
            "message": "Batas maksimal perangkat 1 sudah terpenuhi"
        }, None)

        success, msg, status = license_client.activate("ABCD-1234-EFGH")
        self.assertFalse(success)
        self.assertEqual(status, "seat_full")
        self.assertIn("Kuota perangkat", msg)

    def test_is_license_active_unlicensed(self):
        active, reason = license_client.is_license_active()
        self.assertFalse(active)
        self.assertIn("Unlicensed", reason)

    @patch("license_client.validate")
    def test_is_license_active_expired_date(self, mock_val):
        lic = license_client.get_license()
        lic.update({
            "status": "active",
            "license_key": "TEST-KEY",
            "expires_at": "2020-01-01T00:00:00Z", # Past date
            "grace_days": 3
        })
        license_client.save_license(lic)
        mock_val.return_value = lic

        active, reason = license_client.is_license_active()
        self.assertFalse(active)
        self.assertIn("melewati tanggal", reason)

    def test_is_license_active_future_date(self):
        lic = license_client.get_license()
        future_date = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        lic.update({
            "status": "active",
            "license_key": "TEST-KEY",
            "expires_at": future_date,
            "grace_days": 3
        })
        license_client.save_license(lic)

        active, reason = license_client.is_license_active()
        self.assertTrue(active)
        self.assertEqual(reason, "Active")

    def test_flask_middleware_interception(self):
        client = application.app.test_client()
        # Aktifkan mode intercept tes
        application.app.config["TEST_LICENSE_INTERCEPT"] = True
        try:
            # Menguji dalam kondisi unlicensed
            res = client.get("/")
            self.assertEqual(res.status_code, 302)
            self.assertIn("/license-lockout", res.headers["Location"])

            # Halaman lockout itu sendiri harus bisa diakses
            res_lockout = client.get("/license-lockout")
            self.assertEqual(res_lockout.status_code, 403)
            self.assertIn(b"Akses Fitur Website Dibatasi", res_lockout.data)
        finally:
            application.app.config["TEST_LICENSE_INTERCEPT"] = False


if __name__ == "__main__":
    unittest.main()
