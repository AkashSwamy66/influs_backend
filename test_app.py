import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import create_app
from werkzeug.security import check_password_hash


class CreatorApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = str(Path(self.temp_dir.name) / "test.sqlite3")
        self.app = create_app({"TESTING": True, "DATABASE": database})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def register_sponsor_and_login(self, email="sponsor@example.com"):
        registration = self.client.post(
            "/api/auth/register/sponsor",
            json={
                "companyName": "Test Sponsor",
                "email": email,
                "password": "sponsor-password-123",
                "industry": "Technology",
                "companySize": "Just me",
            },
        )
        self.assertEqual(registration.status_code, 201)
        login = self.client.post(
            "/api/auth/login",
            json={
                "role": "sponsor",
                "email": email,
                "password": "sponsor-password-123",
            },
        )
        return {"Authorization": f"Bearer {login.json['data']['token']}"}

    def register_influencer_and_login(self, email="influencer@example.com"):
        registration = self.client.post(
            "/api/auth/register/influencer",
            json={
                "name": "Test Influencer",
                "email": email,
                "password": "influencer-password-123",
                "city": "Pune",
                "niche": "Travel",
            },
        )
        self.assertEqual(registration.status_code, 201)
        login = self.client.post(
            "/api/auth/login",
            json={
                "role": "influencer",
                "email": email,
                "password": "influencer-password-123",
            },
        )
        return {"Authorization": f"Bearer {login.json['data']['token']}"}

    def test_health_and_seeded_creator_list_match_frontend_contract(self):
        health = self.client.get("/api/health")
        headers = self.register_sponsor_and_login()
        response = self.client.get("/api/creators", headers=headers)

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json, {"status": "ok"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["data"]), 6)
        self.assertIn("socialLinks", response.json["data"][0])
        self.assertIn("contactEmail", response.json["data"][0])
        self.assertEqual(response.json["data"][0]["instagram_id"], "aishakapoor")

    def test_get_creator_and_missing_creator(self):
        headers = self.register_sponsor_and_login()
        response = self.client.get("/api/creators/5", headers=headers)
        missing = self.client.get("/api/creators/999", headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"]["name"], "Meher Ali")
        self.assertEqual(missing.status_code, 404)

    def test_create_creator_persists_and_returns_frontend_shape(self):
        headers = self.register_sponsor_and_login()
        payload = {
            "name": "Test Creator",
            "category": "Technology",
            "city": "Delhi",
            "contactEmail": "test@example.com",
            "platforms": ["Instagram"],
            "socialLinks": [
                {"name": "Instagram", "url": "https://instagram.com/test"}
            ],
        }
        created = self.client.post(
            "/api/creators",
            data=json.dumps(payload),
            content_type="application/json",
            headers=headers,
        )
        creator_id = created.json["data"]["id"]
        fetched = self.client.get(f"/api/creators/{creator_id}", headers=headers)

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json["data"]["contactEmail"], "test@example.com")
        self.assertEqual(fetched.json["data"]["socialLinks"], payload["socialLinks"])

    def test_create_creator_requires_name_category_and_city(self):
        headers = self.register_sponsor_and_login()
        response = self.client.post(
            "/api/creators",
            json={"name": "Incomplete"},
            headers=headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("category", response.json["error"])

    def test_creator_feed_requires_login(self):
        self.assertEqual(self.client.get("/api/creators").status_code, 401)
        self.assertEqual(self.client.get("/api/creators/1").status_code, 401)
        self.assertEqual(
            self.client.post("/api/creators", json={"name": "No auth"}).status_code,
            401,
        )

    def test_influencers_cannot_view_other_creators_contact_or_instagram(self):
        headers = self.register_influencer_and_login()
        listed = self.client.get("/api/creators", headers=headers)
        aisha = next(creator for creator in listed.json["data"] if creator["id"] == 1)
        detail = self.client.get("/api/creators/1", headers=headers).json["data"]

        self.assertEqual(aisha["contactEmail"], "")
        self.assertEqual(aisha["handle"], "")
        self.assertEqual(aisha["socialLinks"], [])
        self.assertEqual(detail["contactEmail"], "")
        self.assertEqual(detail["handle"], "")
        self.assertEqual(detail["socialLinks"], [])

        own_creator_id = next(
            creator["id"]
            for creator in listed.json["data"]
            if creator["contactEmail"] == "influencer@example.com"
        )
        own_profile = self.client.get(
            f"/api/creators/{own_creator_id}", headers=headers
        ).json["data"]
        self.assertEqual(own_profile["contactEmail"], "influencer@example.com")

    def test_sponsors_can_view_creator_contact_and_instagram(self):
        headers = self.register_sponsor_and_login()
        creator = self.client.get("/api/creators/1", headers=headers).json["data"]

        self.assertEqual(creator["contactEmail"], "aisha@example.com")
        self.assertEqual(creator["handle"], "@aishakapoor")
        self.assertGreater(len(creator["socialLinks"]), 0)
        self.assertIn(
            "Instagram",
            [link["name"] for link in creator["socialLinks"]],
        )

    def test_influencer_registration_hashes_password_and_creates_creator_profile(self):
        response = self.client.post(
            "/api/auth/register/influencer",
            json={
                "name": "New Creator",
                "handle": "@newcreator",
                "email": "new@example.com",
                "password": "long-enough-password",
                "city": "Delhi",
                "niche": "Food",
                "bio": "Food creator",
                "instagram": "newcreator",
                "youtube": "",
                "image": "https://example.com/newcreator.jpg",
                "followers": "12500",
                "likes": "2400",
                "views": "48000",
                "engagement": "6.5",
                "rate": "1200",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.json["data"])
        self.assertNotIn("password_hash", response.json["data"])
        creator_id = response.json["data"]["creatorId"]
        token = self.client.post(
            "/api/auth/login",
            json={
                "role": "influencer",
                "email": "new@example.com",
                "password": "long-enough-password",
            },
        ).json["data"]["token"]
        headers = {"Authorization": f"Bearer {token}"}
        creator = self.client.get(
            f"/api/creators/{creator_id}", headers=headers
        ).json["data"]
        self.assertEqual(creator["contactEmail"], "new@example.com")
        self.assertEqual(creator["socialLinks"][0]["url"], "https://instagram.com/newcreator")
        self.assertEqual(creator["followers"], 12500)
        self.assertEqual(creator["likes"], 2400)
        self.assertEqual(creator["views"], 48000)
        self.assertEqual(creator["engagement"], 6.5)
        self.assertEqual(creator["price"], 1200)
        self.assertEqual(creator["image"], "https://example.com/newcreator.jpg")
        self.assertEqual(creator["rating"], 0)

        with self.app.app_context():
            row = sqlite3.connect(self.app.config["DATABASE"]).execute(
                "SELECT password_hash FROM accounts WHERE email = ?",
                ("new@example.com",),
            ).fetchone()
        self.assertTrue(check_password_hash(row[0], "long-enough-password"))
        self.assertNotEqual(row[0], "long-enough-password")

    def test_sponsor_registration_and_duplicate_email(self):
        payload = {
            "companyName": "Northstar Studio",
            "email": "team@example.com",
            "password": "sponsor-password",
            "industry": "Technology",
            "companySize": "2-10",
            "website": "https://northstar.example",
        }
        response = self.client.post("/api/auth/register/sponsor", json=payload)
        duplicate = self.client.post("/api/auth/register/sponsor", json=payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["data"]["role"], "sponsor")
        self.assertEqual(duplicate.status_code, 409)
        self.assertNotIn("password_hash", response.json["data"])

    def test_registration_rejects_short_password(self):
        response = self.client.post(
            "/api/auth/register/sponsor",
            json={
                "companyName": "Northstar Studio",
                "email": "team@example.com",
                "password": "short",
                "industry": "Technology",
                "companySize": "2-10",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("8 characters", response.json["error"])

    def test_influencer_registration_rejects_invalid_audience_metrics(self):
        response = self.client.post(
            "/api/auth/register/influencer",
            json={
                "name": "Invalid Creator",
                "email": "invalid@example.com",
                "password": "long-enough-password",
                "city": "Delhi",
                "niche": "Food",
                "followers": -1,
                "likes": 0,
                "views": 0,
                "engagement": 101,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("engagement between 0 and 100", response.json["error"])

    def test_instagram_id_is_unique_case_insensitively_during_registration(self):
        registration = {
            "name": "First Instagram Creator",
            "email": "first-instagram@example.com",
            "password": "creator-password-123",
            "city": "Delhi",
            "niche": "Food",
            "instagram": "UniqueCreator",
        }
        first = self.client.post("/api/auth/register/influencer", json=registration)
        registration.update(
            {
                "name": "Duplicate Instagram Creator",
                "email": "second-instagram@example.com",
                "instagram": "@UNIQUECREATOR/",
            }
        )
        duplicate = self.client.post("/api/auth/register/influencer", json=registration)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("Instagram account", duplicate.json["error"])
        login = self.client.post(
            "/api/auth/login",
            json={
                "role": "influencer",
                "email": "first-instagram@example.com",
                "password": "creator-password-123",
            },
        )
        headers = {"Authorization": f"Bearer {login.json['data']['token']}"}
        self.assertEqual(len(self.client.get("/api/creators", headers=headers).json["data"]), 7)

    def test_creator_create_rejects_existing_instagram_id(self):
        headers = self.register_sponsor_and_login()
        response = self.client.post(
            "/api/creators",
            json={
                "name": "Duplicate Creator",
                "category": "Food",
                "city": "Delhi",
                "socialLinks": [
                    {"name": "Instagram", "url": "https://instagram.com/aishakapoor/"}
                ],
            },
            headers=headers,
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("Instagram account", response.json["error"])

    def test_profile_update_rejects_instagram_id_owned_by_another_creator(self):
        registration = self.client.post(
            "/api/auth/register/influencer",
            json={
                "name": "Profile Editor",
                "email": "profile-editor@example.com",
                "password": "editor-password-123",
                "city": "Pune",
                "niche": "Travel",
            },
        )
        login = self.client.post(
            "/api/auth/login",
            json={
                "role": "influencer",
                "email": "profile-editor@example.com",
                "password": "editor-password-123",
            },
        )
        token = login.json["data"]["token"]
        response = self.client.put(
            "/api/me",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "socialLinks": [
                    {"name": "Instagram", "url": "https://instagram.com/aishakapoor/"}
                ],
                "platforms": ["Instagram"],
            },
        )

        self.assertEqual(registration.status_code, 201)
        self.assertEqual(response.status_code, 409)

    def test_login_and_authenticated_influencer_profile_update(self):
        registration = self.client.post(
            "/api/auth/register/influencer",
            json={
                "name": "Profile Owner",
                "email": "owner@example.com",
                "password": "owner-password-123",
                "city": "Delhi",
                "niche": "Food",
                "followers": 1500,
                "likes": 250,
                "views": 9000,
                "engagement": 4.5,
            },
        )
        login = self.client.post(
            "/api/auth/login",
            json={
                "role": "influencer",
                "email": "OWNER@example.com",
                "password": "owner-password-123",
            },
        )

        self.assertEqual(registration.status_code, 201)
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json["data"]["account"]["role"], "influencer")
        self.assertNotIn("password", login.json["data"])

        token = login.json["data"]["token"]
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        headers = {"Authorization": f"Bearer {token}"}
        profile = self.client.get("/api/me", headers=headers)
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json["data"]["profile"]["followers"], 1500)

        updated = self.client.put(
            "/api/me",
            headers=headers,
            json={
                "name": "Profile Owner Updated",
                "followers": 2500,
                "likes": 600,
                "views": 18000,
                "engagement": 6.2,
                "price": 2200,
                "rating": 5,
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json["data"]["name"], "Profile Owner Updated")
        self.assertEqual(updated.json["data"]["followers"], 2500)
        self.assertEqual(updated.json["data"]["contactEmail"], "owner@example.com")
        self.assertEqual(updated.json["data"]["rating"], 0)

        listed = self.client.get("/api/creators", headers=headers).json["data"]
        saved_profile = next(item for item in listed if item["name"] == "Profile Owner Updated")
        self.assertEqual(saved_profile["views"], 18000)

    def test_login_rejects_wrong_password(self):
        self.client.post(
            "/api/auth/register/sponsor",
            json={
                "companyName": "Login Test",
                "email": "login@example.com",
                "password": "correct-password",
                "industry": "Technology",
                "companySize": "Just me",
            },
        )
        response = self.client.post(
            "/api/auth/login",
            json={
                "role": "sponsor",
                "email": "login@example.com",
                "password": "wrong-password",
            },
        )

        self.assertEqual(response.status_code, 401)

    def test_profile_update_is_rejected_for_sponsor_account(self):
        self.client.post(
            "/api/auth/register/sponsor",
            json={
                "companyName": "Sponsor Test",
                "email": "sponsor-profile@example.com",
                "password": "sponsor-password",
                "industry": "Technology",
                "companySize": "Just me",
            },
        )
        login = self.client.post(
            "/api/auth/login",
            json={
                "role": "sponsor",
                "email": "sponsor-profile@example.com",
                "password": "sponsor-password",
            },
        )
        token = login.json["data"]["token"]

        response = self.client.put(
            "/api/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Attempted creator edit"},
        )

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()