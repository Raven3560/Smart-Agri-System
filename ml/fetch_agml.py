"""
Download open leaf-disease datasets from AgML (Project-AgML on Hugging Face) for the
crops PlantVillage does not cover, and save a balanced sample as an image folder:

    data/agml_images/<crop>___<class>/<n>.jpg

Every dataset used here is published under a Creative Commons licence; see
DATASETS below and agri/data/extra_sources.json for citations.

Usage:
    python ml/fetch_agml.py                 # all datasets, up to 300 images per class
    python ml/fetch_agml.py --per-class 150 --only money_plant banana
"""
import argparse
import io
import json
import os
import random
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Raw downloads can be several GB, so they go to a local cache outside the project (and outside
# OneDrive/Dropbox-synced folders) and are deleted after the sample is taken unless --keep-raw is given.
RAW = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache"), "SmartAgri", "agml")
OUT = os.path.join(ROOT, "data", "agml_images")
HF = "https://huggingface.co"

# crop key -> list of (dataset name, licence, {original class: our class or None to drop})
DATASETS = {
    "money_plant": [("money_plant_disease_classification", "CC BY 4.0", {
        "Bacterial wilt disease": "bacterial_wilt", "Healthy": "healthy", "Manganese Toxicity": "manganese_toxicity"})],
    "rice": [("rice_leaf_disease_classification_india", "CC BY 4.0", {
        "Bacterialblight": "bacterial_blight", "Blast": "blast", "Brownspot": "brown_spot", "Tungro": "tungro"})],
    "sugarcane": [("sugarcane_leaf_disease_classification", "CC BY 4.0", {
        "Banded Chlorosis": "banded_chlorosis", "Brown Spot": "brown_spot", "BrownRust": "brown_rust", "Dried": None,
        "Grassy shoot": "grassy_shoot", "Healthy": "healthy", "Pokkah Boeng": "pokkah_boeng", "Sett Rot": None,
        "Smut": "smut", "Viral Disease": "mosaic", "Yellow Leaf": "yellow_leaf"})],
    "cotton": [("cotton_leaf_disease_classification", "CC BY-NC 4.0", {
        "Alternaria_Leaf": "alternaria_leaf_spot", "Bacterial_Blight": "bacterial_blight", "Fusarium_Wilt": "fusarium_wilt",
        "Healthy_Leaf": "healthy", "Verticillium_Wilt": "verticillium_wilt"})],
    "mango": [("mango_leaf_disease_classification", "CC BY 4.0", {
        "Anthracnose": "anthracnose", "Bacterial_Canker": "bacterial_canker", "Cutting_Weevil": "cutting_weevil",
        "Die_Back": "die_back", "Gall_Midge": "gall_midge", "Healthy": "healthy", "Powdery_Mildew": "powdery_mildew",
        "Sooty_Mold": "sooty_mould"})],
    "banana": [("BananaLSD_leaf_disease_classification", "CC BY 4.0", {
                   "cordana": "cordana_leaf_spot", "healthy": "healthy", "pestalotiopsis": "pestalotiopsis_leaf_spot",
                   "sigatoka": "sigatoka"}),
               ("banana_leaf_disease_classification", "CC BY 4.0", {
                   "healthy": "healthy", "segatoka": "sigatoka", "xamthomonas": "xanthomonas_wilt"})],
    "chilli": [("COLD_chili_leaf_disease_classification", "CC BY 4.0", {
        "cercospora": "cercospora_leaf_spot", "healthy": "healthy", "mites_and_trips": "mites_and_thrips",
        "nutritional": "nutrient_deficiency", "powdery mildew": "powdery_mildew"})],
    "onion": [("COLD_onion_leaf_disease_classification", "CC BY 4.0", {
        "Iris yellow virus": "iris_yellow_spot_virus", "Stemphylium leaf blight and collectrichum leaf blight": "leaf_blight",
        "healthy": "healthy", "purple blotch": "purple_blotch"})],
    "groundnut": [("groundnut_leaf_disease_classification", "CC BY 4.0", {
        "ALTERNARIA LEAF SPOT": "alternaria_leaf_spot", "HEALTHY": "healthy", "LEAF SPOT": "tikka_leaf_spot",
        "ROSETTE": "rosette", "RUST": "rust"})],
    "turmeric": [("turmeric_leaf_disease_classification", "CC BY 4.0", {
        "Aphids_Disease": "aphids", "Blotch": "leaf_blotch", "Healthy_Leaf": "healthy", "Leaf_Spot": "leaf_spot"})],
    "tea": [("tea_leaf_disease_classification_bangladesh", "CC BY 4.0", {
        "Healthy": "healthy", "Tea leaf blight": "leaf_blight", "Tea red leaf spot": "red_leaf_spot",
        "Tea red scab": "red_scab"})],
    "papaya": [("papaya_leaf_disease_classification_bangladesh", "CC BY 4.0", {
        "Healthy Leaf": "healthy", "Leaf Curl": "leaf_curl", "Mealybug": "mealybug", "Mite Disease": "mites",
        "Mosaic": "mosaic", "Ring Spot": "ring_spot"})],
    "masoor": [("lentil_disease_classification", "CC BY 4.0", {
        "Ascochyta blight": "ascochyta_blight", "Lentil Rust": "rust", "Normal": "healthy",
        "Powdery Mildew": "powdery_mildew"})],
    "urad": [("blackgram_plant_leaf_disease_classification", "CC BY 4.0", {
        "anthracnose": "anthracnose", "healthy": "healthy", "leaf_crinckle": "leaf_crinkle",
        "powdery_mildew": "powdery_mildew", "yellow_mosaic": "yellow_mosaic"})],
    "malabar_spinach": [("IDDMSLD_spinach_leaf_disease_classification", "CC BY 4.0", {
        "Anthracnose": "anthracnose", "Bacterial-Spot": "bacterial_spot", "Downy-Mildew": "downy_mildew",
        "Healthy-Leaf": "healthy", "Pest-Damage": "pest_damage"})],
    "radish": [("radish_leaf_disease_classification", "CC BY 4.0", {
        "Black leaf spot": "black_leaf_spot", "Downey mildew": "downy_mildew", "Fresh leaf": "healthy",
        "Mosaic virus": "mosaic", "flea beetle": "flea_beetle"})],
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "smart-agri-assistant"})
    return urllib.request.urlopen(req, timeout=120)


def parquet_files(name):
    """Data files of a dataset. Original ("raw") photos are preferred over "augmented" copies,
    because rotated/flipped duplicates would leak between training and test sets."""
    with get(f"{HF}/api/datasets/Project-AgML/{name}/tree/main?recursive=true") as r:
        files = [x["path"] for x in json.load(r) if x.get("type") == "file" and x["path"].endswith(".parquet")]
    raw = [f for f in files if f.startswith("raw/")]
    if raw:
        return raw
    return [f for f in files if "augment" not in f.lower()] or files


def download(name):
    folder = os.path.join(RAW, name)
    os.makedirs(folder, exist_ok=True)
    paths = []
    for path in parquet_files(name):
        dest = os.path.join(folder, os.path.basename(path))
        if not os.path.exists(dest):
            tmp = dest + ".part"
            with get(f"{HF}/datasets/Project-AgML/{name}/resolve/main/{path}") as r, open(tmp, "wb") as fh:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    fh.write(chunk)
            os.replace(tmp, dest)
        paths.append(dest)
    return paths


def class_names(name):
    with get(f"{HF}/datasets/Project-AgML/{name}/raw/main/README.md") as r:
        head = r.read().decode("utf-8", "replace").split("---", 2)[1]
    names = {}
    for idx, label in re.findall(r"^\s+'(\d+)':\s*(.+)$", head, re.M):
        names.setdefault(int(idx), label.strip().strip("'\""))
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-class", type=int, default=300)
    ap.add_argument("--only", nargs="*", help="crop keys to fetch")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--keep-raw", action="store_true", help="keep the downloaded parquet files")
    args = ap.parse_args()

    import pyarrow.parquet as pq
    from PIL import Image

    rng = random.Random(args.seed)
    summary = {}
    for crop, sources in DATASETS.items():
        if args.only and crop not in args.only:
            continue
        wanted = {c for _, _, m in sources for c in m.values() if c}
        if not args.only and all(os.path.isdir(os.path.join(OUT, f"{crop}___{c}")) and
                                 os.listdir(os.path.join(OUT, f"{crop}___{c}")) for c in wanted):
            print(f"[{crop}] already prepared, skipping", flush=True)
            continue
        pool = {}
        for name, licence, mapping in sources:
            print(f"[{crop}] downloading {name} ...", flush=True)
            try:
                files = download(name)
                idx_to_label = class_names(name)
            except Exception as exc:  # noqa: BLE001 - carry on with the other datasets
                print(f"    failed: {exc}", flush=True)
                continue
            for f in files:
                table = pq.read_table(f, columns=["label"])
                labels = table.column("label").to_pylist()
                for row, lab in enumerate(labels):
                    ours = mapping.get(idx_to_label.get(lab))
                    if ours:
                        pool.setdefault(ours, []).append((f, row, name))
        for cls, items in sorted(pool.items()):
            rng.shuffle(items)
            chosen = items[:args.per_class]
            folder = os.path.join(OUT, f"{crop}___{cls}")
            os.makedirs(folder, exist_ok=True)
            by_file = {}
            for f, row, name in chosen:
                by_file.setdefault(f, []).append((row, name))
            n = 0
            for f, rows in by_file.items():
                table = pq.read_table(f, columns=["image"])
                col = table.column("image")
                for row, name in rows:
                    data = col[row].as_py()["bytes"]
                    try:
                        im = Image.open(io.BytesIO(data)).convert("RGB")
                    except Exception:  # noqa: BLE001 - skip unreadable images
                        continue
                    im.thumbnail((384, 384))
                    im.save(os.path.join(folder, f"{name[:12]}_{row}.jpg"), "JPEG", quality=90)
                    n += 1
            summary[f"{crop}___{cls}"] = {"images": n, "available": len(items)}
            print(f"    {crop}___{cls}: {n} saved of {len(items)}", flush=True)
        if not args.keep_raw:
            import shutil
            for name, _, _ in sources:
                shutil.rmtree(os.path.join(RAW, name), ignore_errors=True)
    with open(os.path.join(ROOT, "data", "agml_images_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
    print("done:", sum(v["images"] for v in summary.values()), "images in", len(summary), "classes")


if __name__ == "__main__":
    sys.exit(main())
