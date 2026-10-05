"""Survey candidate AgML datasets on Hugging Face: classes, image counts, size and licence.

    python ml/agml_survey.py
"""
import json
import re
import sys
import urllib.request

CANDIDATES = {
    "money_plant": ["money_plant_disease_classification"],
    "rice": ["rice_leaf_disease_classification_india", "rice_leaf_disease_classification", "paddy_disease_classification"],
    "wheat": ["wheat_disease_detection"],
    "sugarcane": ["sugarcane_leaf_disease_classification"],
    "cotton": ["cotton_leaf_disease_classification", "cotton_leaf_disease_classification_bangladesh_2"],
    "mango": ["mango_leaf_disease_classification"],
    "banana": ["banana_leaf_disease_classification", "BananaLSD_leaf_disease_classification"],
    "chilli": ["COLD_chili_leaf_disease_classification"],
    "onion": ["COLD_onion_leaf_disease_classification"],
    "brinjal": ["eggplant_leaf_disease_classification"],
    "okra": ["OkraDiseaseNet_disease_classification"],
    "groundnut": ["groundnut_leaf_disease_classification", "groundnut_leaf_disease_classification_2"],
    "turmeric": ["turmeric_leaf_disease_classification", "turmeric_disease_classification"],
    "tea": ["tea_leaf_disease_classification", "tea_leaf_disease_classification_bangladesh"],
    "coffee": ["arabica_coffee_leaf_disease_classification"],
    "coconut": ["coconut_tree_disease_classification"],
    "cauliflower": ["cauliflower_leaf_disease_classification"],
    "cucumber": ["cucumber_disease_classification"],
    "papaya": ["papaya_leaf_disease_classification_bangladesh"],
    "guava": ["guava_disease_classification"],
    "pomegranate": ["pomegranate_disease_classification_india"],
    "radish": ["radish_leaf_disease_classification"],
    "spinach": ["IDDMSLD_spinach_leaf_disease_classification"],
    "masoor": ["lentil_disease_classification"],
    "urad": ["blackgram_plant_leaf_disease_classification", "black_gram_disease_classification"],
    "soybean": ["soybean_leaf_disease_classification"],
    "sunflower": ["sunflower_disease_classification"],
    "watermelon": ["watermelon_disease_classification"],
    "jute": ["jute_disease_classification"],
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "smart-agri-assistant"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def parse_card(text):
    head = text.split("---", 2)[1] if text.startswith("---") else ""
    lic = re.search(r"^license:\s*(\S+)", head, re.M)
    names = re.findall(r"^\s+'\d+':\s*(.+)$", head, re.M)
    n = re.search(r"num_examples:\s*(\d+)", head)
    size = re.search(r"download_size:\s*(\d+)", head)
    feats = re.findall(r"^\s+- name:\s*(\S+)", head, re.M)
    body = text.split("---", 2)[2] if text.startswith("---") else text
    return {
        "license": lic.group(1) if lic else None,
        "classes": [x.strip().strip("'\"") for x in names],
        "images": int(n.group(1)) if n else None,
        "download_mb": round(int(size.group(1)) / 1e6, 1) if size else None,
        "features": feats,
        "about": " ".join(body.strip().split())[:220],
    }


def main():
    out = {}
    for crop, names in CANDIDATES.items():
        for name in names:
            try:
                card = parse_card(fetch(f"https://huggingface.co/datasets/Project-AgML/{name}/raw/main/README.md"))
            except Exception as exc:  # noqa: BLE001
                card = {"error": str(exc)}
            out[name] = {"crop": crop, **card}
            c = out[name]
            print(f"{crop:12s} {name:48s} {c.get('license')!s:10s} imgs={c.get('images')!s:6s} "
                  f"MB={c.get('download_mb')!s:7s} classes={c.get('classes')}")
            sys.stdout.flush()
    with open("data/agml_survey.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
