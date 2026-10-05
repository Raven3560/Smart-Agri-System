"""Recommendation engine.

Combines the disease prediction, the farmer's crop details, the weather
forecast and the irrigation plan into one context-aware report with a
prioritised action plan.
"""
from . import knowledge as kb
from .weather import pretty_date

CONF_HIGH = 0.75
CONF_LOW = 0.50
MIN_CROP_MASS = 0.15   # probability mass on the selected crop below which the image is doubted

GENERIC_FUNGAL_PROFILE = {"t_min": 15, "t_max": 30, "rh_min": 85, "needs_rain": False}
KISAN_CALL_CENTRE = "1800-180-1551"


def confidence_level(p):
    if p >= CONF_HIGH:
        return "high"
    if p >= CONF_LOW:
        return "medium"
    return "low"


def interpret_prediction(ranked, selected_crop):
    """Turn raw (label, probability) pairs into a diagnosis using crop context."""
    entries = []
    for label, prob in ranked:
        d = kb.disease_by_label(label)
        if d is not None:
            entries.append((d, float(prob)))
    top, top_p = entries[0]
    top3 = [{"key": d["key"], "name": d["name"], "crop": kb.crop_name(d["crop"]), "prob": round(p, 4),
             "healthy": d["healthy"]} for d, p in entries[:3]]

    crop_supported = selected_crop in kb.model_crops()
    result = {
        "crop_supported": crop_supported,
        "raw_top": {"key": top["key"], "name": top["name"], "crop": top["crop"], "prob": round(top_p, 4)},
        "top3": top3,
        "mismatch": False,
        "adjusted": False,
        "crop_mass": None,
    }
    if not crop_supported:
        result.update(status="unsupported", disease=None, confidence=0.0, level="low")
        return result

    in_crop = [(d, p) for d, p in entries if d["crop"] == selected_crop]
    crop_mass = sum(p for _, p in in_crop)
    result["crop_mass"] = round(crop_mass, 4)
    result["no_healthy_class"] = not any(d["healthy"] for d, _ in in_crop)

    if top["crop"] == selected_crop:
        disease, conf = top, top_p
    elif len(in_crop) == 1:
        # Only one class for this crop: renormalising would always give 100%, so keep the raw probability.
        result["mismatch"] = True
        disease, conf = in_crop[0]
    else:
        result["mismatch"] = True
        best, best_p = in_crop[0]
        disease = best
        conf = best_p / crop_mass if crop_mass > 0 else 0.0
        result["adjusted"] = True
        if crop_mass < MIN_CROP_MASS:
            conf = min(conf, crop_mass)  # the image probably does not show the selected crop

    level = confidence_level(conf)
    if level == "low":
        status = "uncertain"
    else:
        status = "healthy" if disease["healthy"] else "diseased"
    result.update(status=status, disease=disease["key"], confidence=round(conf, 4), level=level)
    return result


INFO_PREFIXES = ("Before disease", "Do not", "No ", "Use a miticide", "The virus", "Rotate between")


def curative_chemical(disease):
    """Pick the chemical option that applies to a crop that is already infected."""
    options = disease["treatment"]["chemical"]
    for opt in options:
        if opt.startswith("After disease appears:"):
            return opt.split(":", 1)[1].strip()
    for opt in options:
        if not opt.startswith(INFO_PREFIXES):
            return opt
    return None


def _favourable(day, prof):
    tmean = (day["tmax"] + day["tmin"]) / 2
    if not prof["t_min"] <= tmean <= prof["t_max"]:
        return False
    if "rh_max" in prof:
        return day["rh"] <= prof["rh_max"]
    wet = day["rh"] >= prof.get("rh_min", 0)
    if prof.get("needs_rain"):
        wet = wet or (day["rain"] >= 1 and day["rain_prob"] >= 50)
    return wet


def disease_weather_risk(profile, wx, days=3, name=None):
    if not profile:
        return None
    window = wx["forecast"][:days]
    fav = [d for d in window if _favourable(d, profile)]
    n = len(fav)
    level = "high" if n >= 2 else "moderate" if n == 1 else "low"
    subject = name or "this disease"
    if level == "high":
        text = f"Weather in the next {days} days strongly favours {subject}. Expect rapid spread if not managed."
    elif level == "moderate":
        text = f"Weather on {pretty_date(fav[0]['date'])} favours {subject}. Stay alert."
    else:
        text = f"Weather in the next {days} days is not favourable for {subject}."
    return {"level": level, "days": n, "window": days, "dates": [d["date"] for d in fav], "text": text}


def spray_advisory(wx):
    """Find a suitable spraying window (no rain, low wind) in the next 3 days."""
    days = wx["forecast"][:3]
    checks = []
    best = None
    for i, d in enumerate(days):
        reasons = []
        if d["rain"] >= 1 and d["rain_prob"] >= 60:
            reasons.append("rain likely")
        nxt = days[i + 1] if i + 1 < len(days) else None
        if nxt and nxt["rain"] >= 5 and nxt["rain_prob"] >= 70:
            reasons.append("heavy rain next day may wash off the spray")
        if d["wind"] >= 15:
            reasons.append(f"wind up to {d['wind']} km/h")
        checks.append({"date": d["date"], "ok": not reasons, "reasons": reasons})
        if not reasons and best is None:
            best = d
    hot = any(d["tmax"] >= 35 for d in days)
    if best is None:
        text = "No good spraying window in the next 3 days (rain or wind). Wait for calm, dry weather."
    elif best["date"] == days[0]["date"]:
        text = "Today is suitable for spraying. Spray in the early morning or late afternoon when it is calm."
    else:
        text = f"Avoid spraying today. The next suitable window is {pretty_date(best['date'])}, early morning."
    if hot:
        text += " Avoid the hottest hours; sulphur and some fungicides can scorch leaves above 32-35 °C."
    return {"ok_today": bool(checks and checks[0]["ok"]), "best_date": best["date"] if best else None,
            "text": text, "days": checks}


def build_report(prediction, crop_key, stage, wx, irrigation):
    disease = kb.disease_by_key(prediction["disease"]) if prediction.get("disease") else None
    status = prediction["status"]
    risk = None
    if disease and not disease["healthy"]:
        risk = disease_weather_risk(disease.get("weather_profile"), wx, name=disease["name"].lower())
    elif status in ("healthy", "unsupported"):
        risk = disease_weather_risk(GENERIC_FUNGAL_PROFILE, wx, name="fungal leaf diseases")
    spray = spray_advisory(wx)
    crop = kb.crops()[crop_key]
    houseplant = crop.get("kind") == "houseplant"
    nutrition_stage = crop["care"]["fertilizer"] if houseplant else kb.stage_nutrition()[stage]

    steps = []
    if status == "uncertain":
        steps.append({"icon": "camera", "title": "Retake the photo for a reliable result",
                      "text": "The model is not confident. Photograph a single affected leaf in daylight, filling the "
                              "frame, against a plain background, and keep the camera steady."})
    if status == "unsupported":
        steps.append({"icon": "info", "title": "Photo diagnosis isn't available for this plant yet",
                      "text": f"The image models recognise {len(kb.model_crops())} crops and {crop['name']} is not one "
                              "of them. Compare the leaf with the common problems listed below, and follow the watering "
                              "and feeding advice."})
    if status == "diseased" and disease:
        cultural = disease["treatment"]["cultural"][:2]
        steps.append({"icon": "scissors", "title": "Act on the affected plants now",
                      "text": " ".join(s.rstrip(".") + "." for s in cultural)})
        treat = []
        if disease["treatment"]["organic"]:
            treat.append("Organic option: " + disease["treatment"]["organic"][0] + ".")
        chem = curative_chemical(disease)
        if chem:
            treat.append("Chemical option: " + chem + ".")
        elif disease["treatment"]["chemical"]:
            treat.append(disease["treatment"]["chemical"][0] + ".")
        steps.append({"icon": "spray", "title": "Apply treatment at the right time",
                      "text": " ".join(treat) + " " + spray["text"]})
    if status == "healthy":
        if risk and risk["level"] == "high":
            text = ("No disease is visible, but humid weather ahead favours fungal diseases. Inspect plants every "
                    "2-3 days, keep leaves dry and improve air flow.")
        else:
            text = "No disease is visible. Keep inspecting the crop weekly and keep the field clean."
        steps.append({"icon": "check", "title": "Your crop looks healthy", "text": text})

    irr_text = irrigation["headline"]["text"]
    if disease and not disease["healthy"] and disease["type"].split()[0] in ("Fungal", "Bacterial", "Oomycete"):
        irr_text += " Water at the base of plants and avoid wetting leaves, which spreads the disease."
    steps.append({"icon": "droplet", "title": irrigation["headline"]["title"], "text": irr_text})

    nutrition = []
    if disease and not disease["healthy"]:
        nutrition.extend(disease["fertilizer"])
    elif disease:
        nutrition.extend(disease["fertilizer"])
    nutrition.append(nutrition_stage)
    stage_first = nutrition_stage.split(". ")[0].rstrip(".") + "."
    if len(nutrition) > 1:
        text = nutrition[0].rstrip(".") + ". " + stage_first
    else:
        text = stage_first
    steps.append({"icon": "sprout", "title": "Feeding" if houseplant else "Nutrition for this stage", "text": text})

    if status == "diseased":
        steps.append({"icon": "repeat", "title": "Monitor and re-check",
                      "text": "Scan the crop again in 5-7 days to track progress. If the problem spreads quickly, "
                              f"contact your nearest Krishi Vigyan Kendra or the Kisan Call Centre ({KISAN_CALL_CENTRE})."})

    return {
        "status": status,
        "disease": disease,
        "risk": risk,
        "spray": spray,
        "steps": steps,
        "nutrition": nutrition,
        "npk": crop["npk"],
        "stage_name": "Pot plant" if houseplant else kb.stages()[stage]["label"],
        "houseplant": houseplant,
        "problems": kb.crop_problems(crop_key) if status == "unsupported" else [],
    }
