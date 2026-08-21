import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import lcu_client
from app import app

class TestSocialBackend(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_social_overview_lcu(self):
        session, base_url = lcu_client.get_lcu_session()
        if not session:
            self.skipTest("LCU not running - skipping live LCU test.")
        
        overview = lcu_client.get_social_overview()
        self.assertTrue(overview.get("success"))
        self.assertIn("friends", overview)
        self.assertIn("groups", overview)
        self.assertIn("requests", overview)
        self.assertIn("blocked", overview)
        self.assertIn("me", overview)
        self.assertIn("counts", overview)
        print(f"\n[TEST PASS] Loaded {len(overview['friends'])} friends across {len(overview['groups'])} groups.")

    def test_social_overview_api(self):
        session, base_url = lcu_client.get_lcu_session()
        if not session:
            self.skipTest("LCU not running - skipping live API test.")
        res = self.app.get('/api/social/overview')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIsInstance(data.get("friends"), list)
        self.assertIsInstance(data.get("groups"), list)

    def test_friend_group_crud(self):
        session, base_url = lcu_client.get_lcu_session()
        if not session:
            self.skipTest("LCU not running.")

        # 1. Create group
        create_res = lcu_client.create_friend_group("TestAutomatedFolder")
        self.assertTrue(create_res.get("success"), f"Failed to create group: {create_res}")
        
        # 2. Verify in overview
        overview = lcu_client.get_social_overview()
        created_group = next((g for g in overview["groups"] if g["name"] == "TestAutomatedFolder"), None)
        self.assertIsNotNone(created_group, "Created group not found in groups list")
        group_id = created_group["id"]

        # 3. Update group
        update_res = lcu_client.update_friend_group(group_id, name="TestAutomatedFolderRenamed")
        self.assertTrue(update_res.get("success"), f"Failed to update group: {update_res}")

        # 4. Delete group
        del_res = lcu_client.delete_friend_group(group_id)
        self.assertTrue(del_res.get("success"), f"Failed to delete group: {del_res}")
        print(f"[TEST PASS] Group CRUD test successful (Created, Renamed, Deleted id {group_id}).")

    def test_hovercard_api(self):
        session, base_url = lcu_client.get_lcu_session()
        if not session:
            self.skipTest("LCU not running.")

        overview = lcu_client.get_social_overview()
        if not overview["friends"]:
            self.skipTest("No friends in list to test hovercard.")

        sample_puuid = overview["friends"][0]["puuid"]
        res = self.app.get(f'/api/social/hovercard/{sample_puuid}')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("hovercard", data)
        print(f"[TEST PASS] Hovercard fetched successfully for PUUID {sample_puuid[:8]}...")

    def test_blocked_api(self):
        session, base_url = lcu_client.get_lcu_session()
        if not session:
            self.skipTest("LCU not running - skipping live API test.")
        res = self.app.get('/api/social/blocked')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIsInstance(data.get("blocked"), list)
    def test_batch_remove_validation(self):
        # Test empty input validation
        res = self.app.post('/api/social/friends/batch-remove', json={})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get("success"))

        res2 = self.app.post('/api/social/friends/batch-remove', json={"friendIds": []})
        self.assertEqual(res2.status_code, 400)
        print("[TEST PASS] Batch remove API parameter validation passed.")

if __name__ == '__main__':
    unittest.main()
