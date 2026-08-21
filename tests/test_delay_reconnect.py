import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import lcu_client
from app import app

class TestDelayReconnect(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_gameflow_phase_lcu(self):
        phase = lcu_client.get_gameflow_phase()
        self.assertIsInstance(phase, str)
        print(f"\n[TEST PASS] Current Gameflow Phase: '{phase}'")

    def test_delay_status_api(self):
        res = self.app.get('/api/delay-reconnect/status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("enabled", data)
        self.assertIn("delay_seconds", data)
        self.assertIn("active", data)
        print(f"[TEST PASS] Delay Status API returned: {data}")

    def test_delay_settings_api(self):
        # Test enabling and setting 75s
        res = self.app.post('/api/delay-reconnect/settings', json={
            "enabled": True,
            "delay_seconds": 75
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("enabled"))
        self.assertEqual(data.get("delay_seconds"), 75)

        # Reset back to False for clean state
        self.app.post('/api/delay-reconnect/settings', json={"enabled": False})
        print(f"[TEST PASS] Delay Settings API successfully updated to 75s and toggled.")

if __name__ == '__main__':
    unittest.main()
