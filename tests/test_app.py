"""End-to-end tests of the Flask web application (uses a temporary database).

Weather calls are replaced with the offline estimate so the tests run without
internet. One test runs the real disease model on a sample leaf.
"""
import io
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agri import create_app  # noqa: E402
from agri.services import weather  # noqa: E402

SAMPLES = os.path.join(ROOT, "agri", "static", "samples")


def offline_weather(lat, lon, cache_dir, past_days=14, allow_estimate=True):
    return weather.estimated_weather(past_days)


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.patch = mock.patch("agri.views.weather.get_weather", side_effect=offline_weather)
        cls.patch.start()
        cls.app = create_app({
            "TESTING": True, "WARMUP_MODEL": False,
            "DATABASE": os.path.join(cls.tmp, "test.sqlite3"),
            "UPLOAD_DIR": os.path.join(cls.tmp, "uploads"),
            "WEATHER_CACHE": os.path.join(cls.tmp, "wx"),
        })
        os.makedirs(cls.app.config["UPLOAD_DIR"], exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.patch.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.client = self.app.test_client()

    def csrf(self, url="/login"):
        html = self.client.get(url).data.decode()
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def register(self, email="farmer@example.com"):
        token = self.csrf("/register")
        return self.client.post("/register", data={
            "csrf_token": token, "name": "Test Farmer", "email": email, "phone": "", "farm_name": "",
            "password": "secret12", "confirm": "secret12"})

    def test_public_pages(self):
        for url in ("/", "/project", "/model", "/login", "/register", "/healthz"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_protected_pages_redirect_to_login(self):
        for url in ("/dashboard", "/analyze", "/irrigation", "/weather", "/history", "/profile"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/login", r.headers["Location"])

    def test_post_without_csrf_is_rejected(self):
        r = self.client.post("/login", data={"email": "x@y.z", "password": "x"})
        self.assertEqual(r.status_code, 400)

    def test_register_login_logout(self):
        r = self.register("a@example.com")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/dashboard").status_code, 200)
        self.client.post("/logout", data={"csrf_token": self.csrf("/dashboard")})
        self.assertEqual(self.client.get("/dashboard").status_code, 302)
        token = self.csrf("/login")
        r = self.client.post("/login", data={"csrf_token": token, "email": "a@example.com", "password": "wrong"})
        self.assertIn(b"Incorrect email or password", r.data)
        r = self.client.post("/login", data={"csrf_token": token, "email": "a@example.com", "password": "secret12"})
        self.assertEqual(r.status_code, 302)

    def test_duplicate_email_rejected(self):
        self.register("dup@example.com")
        self.client = self.app.test_client()
        r = self.register("dup@example.com")
        self.assertIn(b"already exists", r.data)

    def test_irrigation_plan_flow(self):
        self.register("irr@example.com")
        token = self.csrf("/irrigation")
        r = self.client.post("/irrigation", data={
            "csrf_token": token, "crop": "wheat", "stage": "development", "soil": "alluvial", "method": "flood",
            "last_irrigation": "", "area_acres": "2", "pump_hp": "5", "pump_head_m": "20", "tariff": "6",
            "location_name": "Test", "lat": "28.5", "lon": "77.5"})
        self.assertEqual(r.status_code, 302)
        page = self.client.get(r.headers["Location"])
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"7-day schedule", page.data)
        self.assertIn(b"Irrigation plans (1)", self.client.get("/history?type=plans").data)

    def test_scan_flow_with_real_model(self):
        self.register("scan@example.com")
        token = self.csrf("/analyze")
        with open(os.path.join(SAMPLES, "corn_common_rust.jpg"), "rb") as fh:
            img = fh.read()
        r = self.client.post("/analyze", data={
            "csrf_token": token, "crop": "maize", "stage": "mid", "soil": "loamy", "method": "drip",
            "last_irrigation": "", "area_acres": "1", "location_name": "Test", "lat": "28.5", "lon": "77.5",
            "image": (io.BytesIO(img), "leaf.jpg")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302, r.data[:500])
        page = self.client.get(r.headers["Location"]).data.decode()
        self.assertIn("Maize Common Rust", page)
        self.assertIn("What to do now", page)
        img_url = re.search(r'src="(/uploads/[^"]+)"', page).group(1)
        img_resp = self.client.get(img_url)
        self.assertEqual(img_resp.status_code, 200)
        img_resp.close()

        # Another user cannot see this scan or its image.
        other = self.app.test_client()
        self.client = other
        self.register("other@example.com")
        self.assertEqual(other.get(r.headers["Location"]).status_code, 404)
        self.assertEqual(other.get(img_url).status_code, 404)

    def test_live_page(self):
        self.assertEqual(self.client.get("/live").status_code, 302)
        self.register("live@example.com")
        page = self.client.get("/live").data.decode()
        self.assertIn("data-live", page)
        self.assertIn("Start camera", page)

    def test_live_predict_endpoint(self):
        from PIL import Image
        with open(os.path.join(SAMPLES, "corn_common_rust.jpg"), "rb") as fh:
            img = Image.open(fh).convert("RGB").resize((320, 320))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        frame = buf.getvalue()

        r = self.client.post("/api/live/predict", data={"frame": (io.BytesIO(frame), "f.jpg")},
                             content_type="multipart/form-data")
        self.assertIn(r.status_code, (400, 401))  # no session and no CSRF token

        self.register("liveapi@example.com")
        token = re.search(r'data-csrf="([^"]+)"', self.client.get("/live").data.decode()).group(1)
        r = self.client.post("/api/live/predict", data={"frame": (io.BytesIO(frame), "f.jpg")},
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)  # CSRF header missing

        headers = {"X-CSRF-Token": token}
        r = self.client.post("/api/live/predict", data={}, headers=headers, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/live/predict", data={"frame": (io.BytesIO(b"nope"), "f.jpg")}, headers=headers,
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)

        r = self.client.post("/api/live/predict", data={"frame": (io.BytesIO(frame), "f.jpg")}, headers=headers,
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(len(data["probs"]), 38)
        self.assertAlmostEqual(sum(data["probs"]), 1.0, delta=0.01)
        best = max(range(38), key=lambda i: data["probs"][i])
        from agri.services import knowledge as kb
        self.assertEqual(kb.diseases()[best]["key"], "corn_common_rust")
        self.assertGreater(data["plant"], 0.05)
        self.assertIn("sharpness", data["quality"])

    def test_crop_guide_is_public_and_lists_all_crops(self):
        from agri.services import knowledge as kb
        html = self.client.get("/crops").data.decode()
        self.assertEqual(html.count("data-guide-card "), len(kb.crops()))
        self.assertIn("Money Plant (Pothos)", html)

    def test_money_plant_watering_plan_and_scan(self):
        self.register("pot@example.com")
        token = self.csrf("/irrigation")
        base = {"csrf_token": token, "stage": "mid", "soil": "loamy", "method": "drip", "area_acres": "1",
                "lat": "28.5", "lon": "77.5", "location_name": "Test"}
        r = self.client.post("/irrigation", data={**base, "crop": "money_plant", "last_irrigation": ""})
        self.assertEqual(r.status_code, 302)
        page = self.client.get(r.headers["Location"]).data.decode()
        self.assertIn("Check the soil today", page)
        self.assertIn("Root rot (overwatering)", page)
        with open(os.path.join(SAMPLES, "tomato_healthy.jpg"), "rb") as fh:
            img = fh.read()
        r = self.client.post("/analyze", data={**base, "crop": "money_plant", "last_irrigation": "",
                                               "image": (io.BytesIO(img), "m.jpg")}, content_type="multipart/form-data")
        page = self.client.get(r.headers["Location"]).data.decode()
        self.assertIn("Common problems with money plant", page)
        self.assertIn("Photo diagnosis isn&#39;t available", page)

    def test_scan_requires_image(self):
        self.register("noimg@example.com")
        token = self.csrf("/analyze")
        r = self.client.post("/analyze", data={"csrf_token": token, "crop": "tomato", "stage": "mid", "soil": "loamy",
                                               "method": "drip"}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)
        self.assertIn(b"Please upload or capture a photo", r.data)


if __name__ == "__main__":
    unittest.main()


class ExtraCropSampleTests(unittest.TestCase):
    """Real photos of the new crops are classified by the second model."""

    CASES = {"money_plant_bacterial_wilt.jpg": ("money_plant", "money_plant___bacterial_wilt"),
             "rice_blast.jpg": ("rice", "rice___blast"),
             "mango_anthracnose.jpg": ("mango", "mango___anthracnose"),
             "banana_sigatoka.jpg": ("banana", "banana___sigatoka")}

    def test_samples(self):
        from PIL import Image
        from agri.services import knowledge as kb
        from agri.services.disease_model import DiseaseModel
        from agri.services.extra_model import ExtraModel
        extra = ExtraModel(os.path.join(ROOT, "models", "extra-crops"))
        if not extra.available:
            self.skipTest("extra-crops model not trained")
        backbone = DiseaseModel(os.path.join(ROOT, "models", "plant-disease-mobilenetv2"))
        from agri.services import recommender
        for fname, (crop, expected) in self.CASES.items():
            path = os.path.join(SAMPLES, fname)
            if not os.path.exists(path):
                continue
            _, feature = backbone.analyse(Image.open(path))
            pred = recommender.interpret_prediction(extra.ranked(feature), crop)
            self.assertEqual(pred["disease"], expected, fname)
            self.assertIn(kb.disease_by_key(expected)["crop"], (crop,))
