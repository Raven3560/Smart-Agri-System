"""Unit tests for the knowledge base, irrigation engine, recommender and image checks.

Run all tests:  python -m unittest discover -s tests -v
"""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageFilter  # noqa: E402

from agri.services import image_quality, irrigation, recommender, weather  # noqa: E402
from agri.services import knowledge as kb  # noqa: E402

TODAY = dt.date(2026, 10, 4)


def make_weather(et0=5.0, rain=None, rain_prob=None, past_days=14, rh=60, tmax=32, tmin=20):
    """Synthetic weather in the same shape as weather.get_weather()."""
    rain = rain or {}
    rain_prob = rain_prob or {}
    days = []
    for offset in range(-past_days, 7):
        d = TODAY + dt.timedelta(days=offset)
        days.append({"date": d.isoformat(), "code": 1, "label": "Clear", "icon": "sun", "tmax": tmax, "tmin": tmin,
                     "rain": rain.get(offset, 0.0), "rain_prob": rain_prob.get(offset, 0), "et0": et0, "wind": 8.0,
                     "rh": rh, "radiation": 18.0, "sunrise": "06:00", "sunset": "18:00"})
    return {"source": "live", "current": {}, "days": days, "today_index": past_days, "today": TODAY.isoformat(),
            "past": days[:past_days], "forecast": days[past_days:]}


def plan(**kw):
    args = dict(crop_key="tomato", stage="mid", soil_key="loamy", method_key="drip", area_acres=1,
                last_irrigation=(TODAY - dt.timedelta(days=3)).isoformat(), weather=make_weather(), today=TODAY)
    args.update(kw)
    return irrigation.plan_irrigation(**args)


class KnowledgeBaseTests(unittest.TestCase):
    def test_38_classes_in_model_order(self):
        items = kb.diseases()
        self.assertEqual(len(items), 38)
        self.assertEqual([d["id"] for d in items], list(range(38)))

    def test_model_labels_match_saved_model(self):
        import json
        cfg = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "plant-disease-mobilenetv2", "config.json")
        if not os.path.exists(cfg):
            self.skipTest("model not downloaded")
        with open(cfg, encoding="utf-8") as fh:
            id2label = json.load(fh)["id2label"]
        for d in kb.diseases():
            self.assertEqual(id2label[str(d["id"])], d["model_label"])

    def test_every_disease_has_guidance(self):
        for d in kb.diseases():
            self.assertIn(d["crop"], kb.crops(), d["key"])
            self.assertTrue(d["summary"])
            self.assertTrue(d["fertilizer"], d["key"])
            if not d["healthy"]:
                self.assertTrue(d["symptoms"], d["key"])
                self.assertTrue(d["treatment"]["cultural"], d["key"])
                self.assertTrue(d["treatment"]["chemical"], d["key"])

    def test_no_banned_antibiotic_recommended(self):
        for d in kb.diseases():
            for opt in d["treatment"]["chemical"] + d["treatment"]["organic"]:
                if "streptomycin" in opt.lower() or "streptocycline" in opt.lower():
                    self.assertTrue(opt.startswith("Do not"), opt)

    def test_label_lookup_accepts_plantvillage_folder(self):
        self.assertEqual(kb.disease_by_label("Tomato___Late_blight")["key"], "tomato_late_blight")
        self.assertEqual(kb.disease_by_label("Tomato with Late Blight")["key"], "tomato_late_blight")


class IrrigationTests(unittest.TestCase):
    def test_effective_rain(self):
        self.assertEqual(irrigation.effective_rain(1.5), 0)
        self.assertAlmostEqual(irrigation.effective_rain(12), 8.0)

    def test_crop_coefficient_by_stage(self):
        tomato = kb.crops()["tomato"]
        self.assertEqual(irrigation.crop_coefficient(tomato, "initial"), 0.60)
        self.assertEqual(irrigation.crop_coefficient(tomato, "mid"), 1.15)
        self.assertAlmostEqual(irrigation.crop_coefficient(tomato, "development"), 0.875)

    def test_freshly_irrigated_field_needs_no_water_today(self):
        r = plan(last_irrigation=TODAY.isoformat())
        self.assertEqual(r["soil_water"]["depletion_mm"], 0)
        self.assertNotEqual(r["status"], "irrigate_now")

    def test_dry_sandy_field_needs_irrigation_now(self):
        r = plan(soil_key="sandy", last_irrigation=(TODAY - dt.timedelta(days=12)).isoformat())
        self.assertEqual(r["status"], "irrigate_now")
        self.assertGreater(r["next"]["net_mm"], 0)
        self.assertAlmostEqual(r["next"]["gross_mm"], round(r["next"]["net_mm"] / 0.9, 1), places=1)

    def test_depletion_never_exceeds_taw(self):
        r = plan(soil_key="sandy", last_irrigation=(TODAY - dt.timedelta(days=40)).isoformat())
        self.assertLessEqual(r["soil_water"]["depletion_mm"], r["soil_water"]["taw_mm"])

    def test_heavy_rain_postpones_irrigation(self):
        wx = make_weather(rain={1: 30.0}, rain_prob={1: 90})
        r = plan(soil_key="sandy", last_irrigation=(TODAY - dt.timedelta(days=6)).isoformat(), weather=wx)
        self.assertEqual(r["status"], "delay_rain")
        self.assertGreater(r["savings"]["rain_skip_l"], 0)

    def test_unlikely_rain_is_ignored(self):
        wx = make_weather(rain={1: 30.0}, rain_prob={1: 20})
        r = plan(soil_key="sandy", last_irrigation=(TODAY - dt.timedelta(days=12)).isoformat(), weather=wx)
        self.assertEqual(r["status"], "irrigate_now")

    def test_past_rain_refills_soil(self):
        dry = plan(last_irrigation=(TODAY - dt.timedelta(days=8)).isoformat())
        wet = plan(last_irrigation=(TODAY - dt.timedelta(days=8)).isoformat(),
                   weather=make_weather(rain={-2: 40.0}, rain_prob={-2: 100}))
        self.assertLess(wet["soil_water"]["depletion_mm"], dry["soil_water"]["depletion_mm"])

    def test_drip_saves_water_versus_flood(self):
        drip = plan(soil_key="sandy", method_key="drip", last_irrigation=(TODAY - dt.timedelta(days=12)).isoformat())
        flood = plan(soil_key="sandy", method_key="flood", last_irrigation=(TODAY - dt.timedelta(days=12)).isoformat())
        self.assertLess(drip["next"]["volume_l"], flood["next"]["volume_l"])
        self.assertGreater(drip["savings"]["vs_flood_l"], 0)
        self.assertEqual(flood["savings"]["vs_flood_l"], 0)

    def test_volume_scales_with_area(self):
        a1 = plan(soil_key="sandy", area_acres=1, last_irrigation=(TODAY - dt.timedelta(days=12)).isoformat())
        a2 = plan(soil_key="sandy", area_acres=2, last_irrigation=(TODAY - dt.timedelta(days=12)).isoformat())
        self.assertAlmostEqual(a2["next"]["volume_l"], 2 * a1["next"]["volume_l"], delta=2)

    def test_energy_estimate(self):
        e = irrigation.energy_for(100000, hp=5, head_m=20, tariff=6)
        self.assertGreater(e["hours"], 0)
        self.assertAlmostEqual(e["kwh"], 5 * 0.746 * e["hours"], delta=0.2)
        self.assertAlmostEqual(e["co2_kg"], e["kwh"] * irrigation.GRID_CO2_KG_PER_KWH, delta=0.2)

    def test_schedule_covers_seven_days(self):
        self.assertEqual(len(plan()["schedule"]), 7)

    def test_unknown_inputs_rejected(self):
        with self.assertRaises(ValueError):
            plan(crop_key="not_a_real_crop")
        with self.assertRaises(ValueError):
            plan(soil_key="moon_dust")


class RecommenderTests(unittest.TestCase):
    def ranked(self, label, p):
        rest = [d["model_label"] for d in kb.diseases() if d["model_label"] != label]
        share = (1 - p) / len(rest)
        return [(label, p)] + [(lab, share) for lab in rest]

    def test_confident_disease(self):
        r = recommender.interpret_prediction(self.ranked("Tomato with Late Blight", 0.95), "tomato")
        self.assertEqual(r["status"], "diseased")
        self.assertEqual(r["disease"], "tomato_late_blight")
        self.assertFalse(r["mismatch"])

    def test_low_confidence_is_uncertain(self):
        r = recommender.interpret_prediction(self.ranked("Tomato with Late Blight", 0.3), "tomato")
        self.assertEqual(r["status"], "uncertain")

    def test_crop_context_reranks(self):
        ranked = [("Potato with Late Blight", 0.55), ("Tomato with Late Blight", 0.40)] + \
                 [(d["model_label"], 0.05 / 36) for d in kb.diseases()
                  if d["model_label"] not in ("Potato with Late Blight", "Tomato with Late Blight")]
        r = recommender.interpret_prediction(ranked, "tomato")
        self.assertTrue(r["mismatch"])
        self.assertEqual(r["disease"], "tomato_late_blight")
        self.assertEqual(r["status"], "diseased")

    def test_unsupported_crop(self):
        r = recommender.interpret_prediction(self.ranked("Tomato with Late Blight", 0.9), "wheat")
        self.assertEqual(r["status"], "unsupported")

    def test_late_blight_risk_high_in_cool_humid_weather(self):
        d = kb.disease_by_key("tomato_late_blight")
        risk = recommender.disease_weather_risk(d["weather_profile"], make_weather(rh=95, tmax=22, tmin=14))
        self.assertEqual(risk["level"], "high")
        risk = recommender.disease_weather_risk(d["weather_profile"], make_weather(rh=40, tmax=38, tmin=26))
        self.assertEqual(risk["level"], "low")

    def test_spider_mites_favoured_by_hot_dry_weather(self):
        d = kb.disease_by_key("tomato_spider_mites")
        risk = recommender.disease_weather_risk(d["weather_profile"], make_weather(rh=30, tmax=40, tmin=27))
        self.assertEqual(risk["level"], "high")

    def test_spray_advisory_avoids_rain(self):
        s = recommender.spray_advisory(make_weather(rain={0: 10.0}, rain_prob={0: 90}))
        self.assertFalse(s["ok_today"])
        self.assertEqual(s["best_date"], (TODAY + dt.timedelta(days=1)).isoformat())

    def test_curative_chemical_for_infected_crop(self):
        chem = recommender.curative_chemical(kb.disease_by_key("potato_late_blight"))
        self.assertTrue(chem.startswith("Cymoxanil"))
        self.assertIsNone(recommender.curative_chemical(kb.disease_by_key("tomato_mosaic_virus")))

    def test_report_has_action_plan(self):
        pred = recommender.interpret_prediction(self.ranked("Tomato with Late Blight", 0.95), "tomato")
        wx = make_weather()
        rep = recommender.build_report(pred, "tomato", "mid", wx, plan(weather=wx))
        titles = [s["title"] for s in rep["steps"]]
        self.assertIn("Act on the affected plants now", titles)
        self.assertIn("Monitor and re-check", titles)


class ImageQualityTests(unittest.TestCase):
    def test_sharp_vs_blurred(self):
        sample = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agri", "static", "samples", "tomato_late_blight.jpg")
        img = Image.open(sample)
        self.assertTrue(image_quality.assess(img)["ok"])
        blurred = image_quality.assess(img.filter(ImageFilter.GaussianBlur(3)))
        self.assertFalse(blurred["ok"])

    def test_dark_and_small_images_flagged(self):
        self.assertFalse(image_quality.assess(Image.new("RGB", (400, 400), (5, 5, 5)))["ok"])
        self.assertFalse(image_quality.assess(Image.new("RGB", (60, 60), (120, 160, 90)))["ok"])


class WeatherTests(unittest.TestCase):
    def test_estimated_weather_shape(self):
        wx = weather.estimated_weather(past_days=5)
        self.assertEqual(wx["source"], "estimated")
        self.assertEqual(len(wx["forecast"]), 7)
        self.assertEqual(len(wx["past"]), 5)

    def test_offline_falls_back(self):
        import tempfile
        from unittest import mock

        import requests
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(weather.requests, "get", side_effect=requests.ConnectionError("offline")):
            weather._memory.clear()
            wx = weather.get_weather(10.123, 20.456, tmp, past_days=3)
            self.assertEqual(wx["source"], "estimated")

    def test_wmo_codes(self):
        self.assertEqual(weather.describe(63), ("Rain", "rain"))
        self.assertEqual(weather.describe(None)[0], "Unknown")


if __name__ == "__main__":
    unittest.main()


class CropDatabaseTests(unittest.TestCase):
    REQUIRED = ("name", "group", "kc", "root_m", "p", "npk", "tip", "kind", "kc_source")

    def test_every_crop_is_complete(self):
        for key, c in kb.crops().items():
            for field in self.REQUIRED:
                self.assertIn(field, c, f"{key} missing {field}")
            self.assertEqual(len(c["kc"]), 3, key)
            self.assertTrue(all(0.1 <= k <= 1.4 for k in c["kc"]), key)
            self.assertTrue(0.1 <= c["root_m"] <= 2.0, key)
            self.assertTrue(0.1 <= c["p"] <= 0.8, key)
            self.assertIn(c["kc_source"], ("FAO-56", "Approximate"), key)

    def test_indian_crops_and_money_plant_present(self):
        for key in ("bajra", "jowar", "ragi", "arhar", "moong", "urad", "groundnut", "brinjal", "okra", "chilli",
                    "banana", "mango", "coconut", "turmeric", "money_plant", "tulsi"):
            self.assertIn(key, kb.crops())
        self.assertGreaterEqual(len(kb.crops()), 60)
        self.assertEqual(kb.crop_label("bajra"), "Pearl Millet (Bajra)")
        self.assertEqual(kb.crop_label("maize"), "Maize (Corn, Makka)")

    def test_every_crop_has_problems_or_photo_check(self):
        for key in kb.crops():
            self.assertTrue(kb.crop_problems(key), f"{key} has no common problems listed")
            for pr in kb.crop_problems(key):
                self.assertTrue(pr["signs"] and pr["manage"], key)

    def test_houseplants_have_care_profile(self):
        self.assertEqual(sorted(kb.houseplant_keys()), ["money_plant", "tulsi"])
        for key in kb.houseplant_keys():
            care = kb.crops()[key]["care"]
            self.assertLessEqual(care["water_days"]["hot"], care["water_days"]["warm"])
            self.assertLessEqual(care["water_days"]["warm"], care["water_days"]["cool"])

    def test_crop_groups_cover_every_crop_once(self):
        keys = [k for _, items in kb.crop_groups() for k, _ in items]
        self.assertEqual(sorted(keys), sorted(kb.crops()))

    def test_new_field_crop_runs_water_balance(self):
        r = plan(crop_key="bajra", soil_key="sandy", last_irrigation=(TODAY - dt.timedelta(days=12)).isoformat())
        self.assertNotEqual(r.get("kind"), "houseplant")
        self.assertEqual(r["soil_water"]["kc"], 1.0)
        self.assertEqual(r["status"], "irrigate_now")


class HouseplantTests(unittest.TestCase):
    def pot(self, crop="money_plant", days=None, tmax=30, rh=60):
        last = (TODAY - dt.timedelta(days=days)).isoformat() if days is not None else None
        return plan(crop_key=crop, last_irrigation=last, weather=make_weather(tmax=tmax, tmin=tmax - 10, rh=rh))

    def test_kind_and_no_field_maths(self):
        r = self.pot(days=2)
        self.assertEqual(r["kind"], "houseplant")
        self.assertNotIn("soil_water", r)
        self.assertEqual(r["savings"]["total_l"], 0)

    def test_hot_weather_waters_more_often(self):
        self.assertLess(self.pot(days=1, tmax=36)["care"]["interval_days"], self.pot(days=1, tmax=18)["care"]["interval_days"])

    def test_due_and_not_due(self):
        self.assertEqual(self.pot(days=20)["status"], "irrigate_now")
        self.assertEqual(self.pot(days=1)["status"], "upcoming")

    def test_unknown_last_watering_says_check_soil(self):
        r = self.pot(days=None)
        self.assertEqual(r["status"], "irrigate_now")
        self.assertIn("Check the soil", r["headline"]["title"])

    def test_tulsi_needs_frequent_water_in_summer(self):
        r = self.pot(crop="tulsi", days=1, tmax=36)
        self.assertEqual(r["care"]["interval_days"], 1)
        self.assertEqual(sum(1 for s in r["schedule"] if s["action"]), 7)


class ExtraModelTests(unittest.TestCase):
    """Second photo model: Indian crops and money plant (models/extra-crops)."""

    @classmethod
    def setUpClass(cls):
        from agri.services.extra_model import ExtraModel
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.model = ExtraModel(os.path.join(root, "models", "extra-crops"))
        if not cls.model.available:
            raise unittest.SkipTest("extra-crops model not trained")

    def test_every_class_has_advice(self):
        keys = {d["key"] for d in kb.extra_diseases()}
        self.assertEqual(set(self.model.classes), keys)
        for d in kb.extra_diseases():
            self.assertTrue(d["summary"], d["key"])
            if not d["healthy"]:
                self.assertTrue(d["symptoms"] and d["treatment"]["cultural"] and d["treatment"]["chemical"], d["key"])

    def test_money_plant_is_covered(self):
        self.assertIn("money_plant", kb.model_crops())
        self.assertEqual(kb.model_for_crop("money_plant"), "extra")
        self.assertEqual(kb.model_for_crop("tomato"), "plantvillage")
        self.assertIsNone(kb.model_for_crop("bajra"))

    def test_probabilities_sum_to_one(self):
        import numpy as np
        p = self.model.probabilities(np.zeros(1280, dtype=np.float32))
        self.assertAlmostEqual(float(p.sum()), 1.0, places=4)
        self.assertEqual(len(p), len(self.model.classes))


class SingleClassCropTests(unittest.TestCase):
    def test_single_class_crop_is_not_forced_to_100_percent(self):
        # PlantVillage only knows "powdery mildew" for squash; a tomato-looking photo must not become 100% mildew.
        ranked = [("Tomato with Late Blight", 0.90), ("Squash with Powdery Mildew", 0.02)] + \
                 [(d["model_label"], 0.08 / 36) for d in kb.diseases()
                  if d["model_label"] not in ("Tomato with Late Blight", "Squash with Powdery Mildew")]
        r = recommender.interpret_prediction(ranked, "squash")
        self.assertEqual(r["status"], "uncertain")
        self.assertLess(r["confidence"], 0.5)
