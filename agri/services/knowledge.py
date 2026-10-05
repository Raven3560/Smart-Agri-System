"""Agricultural knowledge base: diseases, crops, soils and irrigation methods.

All data lives in JSON files under ``agri/data`` so it can be reviewed and
extended without touching code.
"""
import json
import os
from functools import lru_cache

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _load(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def diseases():
    """The 38 PlantVillage classes, indexed by the original model's class id."""
    items = _load("diseases.json")
    items.sort(key=lambda d: d["id"])
    return items


@lru_cache(maxsize=1)
def extra_diseases():
    """Classes of the extra-crops model (money plant, rice, sugarcane, ...), in model order."""
    path = os.path.join(DATA_DIR, "diseases_extra.json")
    if not os.path.exists(path):
        return []
    items = _load("diseases_extra.json")
    items.sort(key=lambda d: d["id"])
    return items


def all_diseases():
    """Every class the photo models know: PlantVillage first, then the extra crops."""
    return diseases() + extra_diseases()


@lru_cache(maxsize=1)
def _crop_data():
    return _load("crops.json")


@lru_cache(maxsize=1)
def _soil_data():
    return _load("soils.json")


def crops():
    return _crop_data()["crops"]


def stages():
    return _crop_data()["stages"]


def stage_nutrition():
    return _crop_data()["stage_nutrition"]


def methods():
    return _crop_data()["methods"]


def soils():
    return _soil_data()["soils"]


def disease_by_key(key):
    for d in all_diseases():
        if d["key"] == key:
            return d
    return None


def disease_by_label(label):
    """Match a model output label to a knowledge-base entry.

    Works with the pretrained model labels ("Tomato with Late Blight") and with
    PlantVillage folder names ("Tomato___Late_blight") used by models trained
    with ml/train.py.
    """
    for d in all_diseases():
        if label in (d["model_label"], d["pv_folder"], d["key"]):
            return d
    return None


def _crops_of(items):
    seen = []
    for d in items:
        if d["crop"] not in seen:
            seen.append(d["crop"])
    return seen


@lru_cache(maxsize=1)
def pv_crops():
    """Crops covered by the PlantVillage model."""
    return _crops_of(diseases())


@lru_cache(maxsize=1)
def extra_crops():
    """Crops covered by the extra-crops model."""
    return _crops_of(extra_diseases())


@lru_cache(maxsize=1)
def model_crops():
    """Crops with photo disease checks (either model). The extra model wins where both cover a crop."""
    return pv_crops() + [c for c in extra_crops() if c not in pv_crops()]


def model_for_crop(crop_key):
    if crop_key in extra_crops():
        return "extra"
    if crop_key in pv_crops():
        return "plantvillage"
    return None


def classes_for_crop(crop_key):
    source = model_for_crop(crop_key)
    pool = extra_diseases() if source == "extra" else diseases()
    return [d for d in pool if d["crop"] == crop_key]


def crop_has_healthy_class(crop_key):
    return any(d["healthy"] for d in classes_for_crop(crop_key))


def crop_name(crop_key):
    c = crops().get(crop_key)
    return c["name"] if c else crop_key.replace("_", " ").title()


def grouped_crop_choices():
    """Crops split by whether disease detection supports them (for <select>)."""
    supported, irrigation_only = [], []
    for key in crops():
        (supported if key in model_crops() else irrigation_only).append((key, crop_label(key)))
    supported.sort(key=lambda x: x[1])
    irrigation_only.sort(key=lambda x: x[1])
    return supported, irrigation_only


GROUP_LABELS = {
    "Cereal": "Cereals and millets", "Pulse": "Pulses", "Oilseed": "Oilseeds", "Vegetable": "Vegetables",
    "Fruit": "Fruits", "Fruit tree": "Fruits", "Fruit vine": "Fruits", "Fruit bush": "Fruits",
    "Spice": "Spices", "Plantation": "Plantation crops", "Cash crop": "Cash crops", "Houseplant": "Houseplants",
}
GROUP_ORDER = ["Cereals and millets", "Pulses", "Oilseeds", "Vegetables", "Fruits", "Spices", "Plantation crops",
               "Cash crops", "Houseplants"]


def crop_label(crop_key):
    """Display name with the Hindi name, e.g. 'Pearl Millet (Bajra)'."""
    c = crops().get(crop_key)
    if not c:
        return crop_name(crop_key)
    name, hindi = c["name"], (c.get("hindi") or "").strip()
    if not hindi or hindi.lower() == name.lower():
        return name
    if name.endswith(")") and " (" in name:            # "Maize (Corn)" -> "Maize (Corn, Makka)"
        base, inner = name[:-1].split(" (", 1)
        return f"{base} ({inner}, {hindi})"
    return f"{name} ({hindi})"


def group_label(crop_key):
    return GROUP_LABELS.get(crops()[crop_key].get("group"), "Other")


def is_houseplant(crop_key):
    return crops().get(crop_key, {}).get("kind") == "houseplant"


def houseplant_keys():
    return [k for k in crops() if is_houseplant(k)]


def crop_groups(exclude=()):
    """[(group label, [(key, label), ...]), ...] in a fixed, farmer-friendly order."""
    buckets = {}
    for key in crops():
        if key in exclude:
            continue
        buckets.setdefault(group_label(key), []).append((key, crop_label(key)))
    order = GROUP_ORDER + sorted(g for g in buckets if g not in GROUP_ORDER)
    return [(g, sorted(buckets[g], key=lambda x: x[1])) for g in order if g in buckets]


def crop_problems(crop_key):
    """Common problems for a crop: from the disease model's classes, or from the crop entry."""
    if crop_key in model_crops():
        out = []
        for d in classes_for_crop(crop_key):
            if d["healthy"]:
                continue
            manage = (d["treatment"]["cultural"] or d["prevention"] or [""])[0]
            out.append({"name": d["name"], "type": d["type"], "signs": d["symptoms"][0] if d["symptoms"] else d["summary"],
                        "manage": manage, "photo_check": True})
        return out + crops().get(crop_key, {}).get("problems", [])
    return crops().get(crop_key, {}).get("problems", [])
