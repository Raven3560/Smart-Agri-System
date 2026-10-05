---
title: SmartAgri
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 4.44.1
python_version: "3.11"
app_file: app.py
pinned: false
---

# SmartAgri AI: AI-Based Smart Agriculture Assistant for Crop Health and Smart Irrigation Management

Final year B.Tech (CSE) project, I.T.S Engineering College, Greater Noida (AKTU), session 2026-27, group 27CSE53.
Team: Pratyush Srivastava, Rashmi Rajput, Shivam Mahajan, Shubham Kumar. Supervisor: Mr. Sushil Chabbra.

A software-only web application. A farmer uploads or captures a leaf photo and enters crop details. The system then:

1. detects the disease with a deep learning model (MobileNetV2, 38 classes, 14 crops),
2. gives treatment, pesticide, fertilizer and prevention guidance,
3. combines the local weather forecast to assess disease risk and pick a spraying window,
4. runs an FAO-56 soil water balance to say **when to irrigate and how much**, holding irrigation when rain is coming,
5. converts the water need into pump hours, electricity, cost and CO₂ (SDG 7),
6. saves everything to a dashboard and history,
7. keeps a crop database of 61 crops and plants grown in India (cereals, millets, pulses, oilseeds, vegetables,
   fruits, spices, plantation crops, and pot plants like money plant and tulsi) with water needs, fertilizer and
   common problems, browsable on the public **Crop guide** page.

No sensors or IoT hardware are needed.

---

## Quick start (Windows)

Requirements: Python 3.10 or newer.

```bat
cd smart-agri-assistant
pip install -r requirements.txt
python scripts\download_model.py      REM only if models\plant-disease-mobilenetv2 is missing
python run.py
```

Or double-click **`start.bat`**.

Open <http://localhost:5000> and click **Try the demo**, or log in with:

| Email | Password |
|---|---|
| demo@smartagri.local | demo1234 |

Before a presentation, refresh the demo data with today's weather:

```bat
python scripts\seed_demo.py
```

### Using it from a phone

Run `python run.py --host 0.0.0.0 --https`. The console prints an address like `https://192.168.1.5:5000`; open it on a phone on the same Wi-Fi. The browser warns that the certificate is self-signed: tap **Advanced** then **Proceed**. HTTPS is needed because browsers only give web pages camera access over a secure connection, and **Live scan** uses the camera directly. Without `--https`, uploads still work and the **Take photo** button falls back to the phone's own camera app, but Live scan can't open the camera on a phone.

### Offline behaviour

The disease model runs fully offline. Weather comes from the free Open-Meteo API (no key). If the internet drops, the app uses the last saved forecast for that location, or a clearly labelled seasonal estimate, so the demo never breaks.

---

## Features and objectives

| Objective (synopsis) | Where it is implemented |
|---|---|
| O1: web app to upload or capture images | Check a leaf page (upload, camera capture, sample leaves) and Live scan page (real-time camera scanning) |
| O2: AI computer vision disease detection | `agri/services/disease_model.py`, image quality checks, confidence handling |
| O3: treatment, pesticide, fertilizer advice | `agri/data/diseases.json` knowledge base, `agri/services/recommender.py` |
| O4: irrigation guidance | `agri/services/irrigation.py` (FAO-56 soil water balance) |
| O5: weather API integration | `agri/services/weather.py` (Open-Meteo forecast and ET₀) |
| O6: dashboard and history | Dashboard, history with filters, printable reports |

---

## How it works

### 1. Disease detection (Computer Vision)

* **Model**: MobileNetV2 (2.27 M parameters, 9 MB) fine-tuned on the PlantVillage dataset (pretrained weights `linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification`).
* **Preprocessing**: fix phone orientation (EXIF), resize the short side to 256 px, centre-crop 224 × 224, normalise.
* **Quality checks** before prediction: resolution, brightness, and blur (variance of the Laplacian, threshold calibrated on PlantVillage images).
* **Crop context**: if the top prediction belongs to a different crop than the farmer selected (for example potato late blight on a tomato), the result is re-ranked within the selected crop. If the photo barely matches the selected crop, it is marked uncertain.
* **Confidence**: high ≥ 75%, medium 50-75%, below 50% is reported as *uncertain* and the farmer is asked for a clearer photo.

### Live scan (real-time camera)

The **Live scan** page opens the camera in the browser and checks the plant continuously:

* The page copies the square inside the on-screen guide box from the video to a 320 × 320 image, about 5 times a second, and posts it to `/api/live/predict`. Only one request is in flight at a time, so a slow connection lowers the frame rate instead of piling up requests.
* The server runs the same MobileNetV2 model (about 30-40 ms on a laptop CPU) and returns the probability of all 38 classes, plus a sharpness, light and "plant in view" check.
* The browser smooths the probabilities over recent frames with an exponential moving average, so the answer doesn't flicker. If a crop is selected, it keeps only that crop's classes, using the same rule as the full report.
* A result is shown as steady only after the same answer repeats for 3 frames in a row. Below 50% confidence it says "not sure", and if almost nothing in the square looks like plant tissue it asks you to point at a leaf.
* **Save report** grabs a sharper 720 × 720 frame and runs the full analysis (treatment, spray timing, weather, irrigation), saved to history.
* Frames are never stored. A video file can be used instead of the camera, which is handy for demos.

### Crop database

`agri/data/crops.json` holds 61 crops and plants. Each entry has:

* the English and Hindi name, group (cereal, pulse, vegetable...) and season (Kharif, Rabi, Zaid, perennial),
* FAO-56 crop coefficients for the initial, mid-season and late stages, root depth and depletion fraction,
* a fertilizer reference (N : P : K) and a growing tip,
* common problems with the signs to look for and what to do.

Water figures follow FAO-56 Tables 12 and 22. Ten crops that FAO does not list (pigeon pea, okra, bottle gourd,
bitter gourd, turmeric, ginger, mango, guava, papaya, pomegranate) use values from the closest listed crop and are
marked `"kc_source": "Approximate"`; the crop guide shows them as approximate.

**Pot plants.** Money plant and tulsi are marked `"kind": "houseplant"`. A field water balance in mm per acre makes no
sense for a pot, so they get a watering interval instead: from the plant's care profile, shortened in hot weather and
lengthened slightly in humid weather. The plan page shows the next watering dates, light and feeding advice, and
common problems.

**Photo diagnosis** still covers only the 14 crops the image model was trained on. Adding a crop to the database
gives it irrigation, fertilizer and the problem guide, but the model can only learn to recognise a new crop's
diseases from labelled photos (see *Training your own model*). On the result page, crops without photo diagnosis
show their common problems so the farmer can compare by eye.

To add or edit crops, change `agri/data/crops.json` (or `scripts/add_indian_crops.py` and re-run it), then restart
the app. The test suite checks every entry for missing fields and sensible values.

### 2. Recommendation engine

Each of the 38 classes has symptoms, cause, favourable weather, cultural, organic and chemical treatment, fertilizer notes and prevention (`agri/data/diseases.json`). The engine:

* scores **disease risk** for the next 3 days from each disease's temperature and humidity profile,
* finds a **spray window** without rain (≥ 60% chance) or strong wind (≥ 15 km/h),
* builds a prioritised **action plan** combining treatment, irrigation and nutrition.

Chemical doses are general per-litre guidance in line with common Indian recommendations. Antibiotics (streptomycin and tetracycline) are deliberately excluded because their agricultural use is banned in India.

### 3. Smart irrigation (FAO-56)

```
ETc  = Kc × ET0                        crop water use per day
TAW  = AWC × Zr                        water the root zone can hold
RAW  = p × TAW                         water usable before stress
Dr(i) = Dr(i-1) + Ks × ETc(i) − Peff(i)  daily root-zone depletion
```

* ET₀ (reference evapotranspiration) and rain come from the weather API, both for past days and the 7-day forecast.
* Kc, root depth Zr and depletion fraction p come from FAO-56 Tables 12 and 22 for 21 crops and 4 growth stages. AWC values for 10 soil types, including Indian soils, come from FAO-56 Table 19.
* The balance starts at field capacity on the last irrigation date.
* Effective rain = 80% of daily rain above 2 mm. Forecast rain only counts when its probability is 50% or more.
* Irrigation is due when depletion reaches RAW. If at least half the need is likely to come from rain within 2 days, irrigation is **held**, which saves water and pumping energy.
* Gross depth = net depth ÷ method efficiency (drip 90%, sprinkler 75%, furrow 60%, flood 50%).

### 4. Energy and SDG 7

Pump discharge is estimated from pump power and total head (40% wire-to-water efficiency, typical of Indian farm pump-sets). This gives pump hours, kWh, cost at your tariff, and CO₂ at 0.71 kg/kWh (Indian grid). Savings are reported against flood irrigation and against irrigating before rain. Forecast solar radiation rates the site's solar-pump potential, with a pointer to the PM-KUSUM scheme.

---

## Model evaluation

`python ml/evaluate.py --data data/plantvillage_sample` produces accuracy, precision, recall, F1-score and a confusion matrix, which the **Model** page displays.

Results on 760 PlantVillage images (20 per class, from the public GitHub mirror):

| Metric | Value |
|---|---|
| Accuracy | 94.7% |
| Top-3 accuracy | 99.5% |
| Macro precision / recall / F1 | 0.954 / 0.947 / 0.947 |
| Inference time (CPU) | about 41 ms per image |

The pretrained model was fine-tuned on a version of PlantVillage, so some of these images may have been seen in training. Treat this as an upper bound and a check that the integration is correct, not as a held-out test score. For a proper held-out result, train your own model as described below. The training script reports metrics on a test split that is never used for training or model selection.

### Second model: Indian crops and money plant

PlantVillage covers only 14 crops. A second classifier adds photo diagnosis for money plant and Indian crops
using open, peer-reviewed leaf datasets published through AgML (Project-AgML on Hugging Face):

| Crop | Classes |
|---|---|
| Money plant | bacterial wilt, manganese toxicity, healthy |
| Rice | bacterial blight, blast, brown spot, tungro (no healthy class in the data) |
| Sugarcane | banded chlorosis, brown spot, brown rust, grassy shoot, mosaic, pokkah boeng, smut, yellow leaf, healthy |
| Cotton | alternaria leaf spot, bacterial blight, fusarium wilt, verticillium wilt, healthy |
| Mango | anthracnose, bacterial canker, cutting weevil, die back, gall midge, powdery mildew, sooty mould, healthy |
| Banana | cordana, pestalotiopsis, sigatoka, bacterial wilt, healthy |
| Chilli | cercospora leaf spot, mites and thrips, nutrient deficiency, powdery mildew, healthy |
| Onion | iris yellow spot virus, leaf blight, purple blotch, healthy |
| Groundnut | alternaria leaf spot, tikka leaf spot, rosette, rust, healthy |
| Turmeric, tea, papaya, masoor, urad, Malabar spinach (poi), radish | 3-6 classes each |

How it works: the PlantVillage MobileNetV2 already turns each photo into a 1,280-number leaf description. The new
classifier is trained on top of that frozen description, so one pass through the network serves both models,
training takes minutes on a laptop CPU, and live scanning stays fast. Original photos are used rather than the
augmented copies some datasets include, so rotated duplicates can't leak between training and test sets.

```bat
python ml/fetch_agml.py          REM download datasets, save up to 300 photos per class
python ml/train_extra.py         REM extract features, pick the classifier on validation, test once
python scripts/build_extra_kb.py REM write advice for every class (agri/data/diseases_extra.json)
python ml/agml_sources.py        REM licences and citations shown on the model page
```

Results for each crop, and full dataset credits, are on the **The model** page. Cotton uses a CC BY-NC 4.0 dataset
(non-commercial use only); the others are CC BY 4.0.

### Training your own model

Install the training tools first: `pip install -r requirements-ml.txt`.

1. Download PlantVillage from Kaggle ("PlantVillage Dataset" or "New Plant Diseases Dataset"). Extract it so each class is a folder, for example `data/plantvillage/Tomato___Late_blight/`.
2. Train. A GPU is recommended; on Google Colab, upload this folder and run the same command.

   ```bat
   python ml/train.py --data data/plantvillage --epochs 5
   python ml/train.py --data data/plantvillage --base microsoft/resnet-50 --out models/resnet50-plant
   python ml/train.py --data data/plantvillage --base google/efficientnet-b0 --out models/effnet-plant
   ```

   Use `--max-per-class 100` for a quick CPU run.
3. The script saves the best checkpoint, `training_history.json` and `evaluation/` (metrics and confusion matrix) in the output folder. To use it in the app, copy the folder contents into `models/plant-disease-mobilenetv2/`.

`python ml/fetch_sample.py --per-class 20` downloads a small balanced sample for quick tests.

---

## Deploying

The website runs the disease models with **ONNX Runtime** (`models/plant-disease-mobilenetv2/model.onnx`),
so hosting needs only `requirements.txt` (about 150 MB installed, about 120 MB of memory). PyTorch and the other
training tools are in `requirements-ml.txt` and are only needed to retrain models. After retraining, run
`python scripts/export_onnx.py` to refresh the ONNX file.

### Vercel (free)
1. Push the project to GitHub.
2. On https://vercel.com choose **Add New > Project**, import the repository, keep the defaults, and add an
   environment variable `SECRET_KEY` with any long random text. Click **Deploy**.
3. `vercel.json` routes every request to `api/index.py`, which runs the Flask app as a serverless function.

Vercel functions have no permanent disk: the SQLite database and uploaded photos live in `/tmp` and can reset
whenever Vercel starts a fresh instance. The demo account is recreated automatically, so demos keep working.

### Render
**New > Blueprint** with this repository uses `render.yaml` (free plan). For data that survives deploys, switch
to a paid plan and enable the disk block in `render.yaml`.

### Hugging Face Spaces (free)
Create a Space with the **Gradio** SDK; it runs `app.py`. See the header at the top of this README.

## Tests

```bat
python -m unittest discover -s tests -v
```

There are 55 tests. They cover the knowledge base, the irrigation engine (rain delay, refill, area scaling, energy), the recommender (crop-context re-ranking, risk, spray window), image quality checks, offline weather fallback, and end-to-end web flows: register, login, CSRF, irrigation plan, a real model scan, the live-scan endpoint, the crop guide, money plant watering plans, and access control between users. The crop database tests check all 61 entries for missing fields and out-of-range values.

---

## Project structure

```
smart-agri-assistant/
├── run.py                      start the web app
├── start.bat                   double-click launcher (Windows)
├── requirements.txt
├── agri/
│   ├── __init__.py             app factory, config, CSRF, template helpers
│   ├── auth.py                 register / login / demo login
│   ├── views.py                pages: dashboard, scan, live scan, results, irrigation, weather, history, profile, model
│   ├── api.py                  JSON: location search, weather, live-scan frame prediction
│   ├── db.py                   SQLite schema and helpers
│   ├── services/
│   │   ├── disease_model.py    MobileNetV2 loading and inference
│   │   ├── image_quality.py    blur, brightness, resolution checks
│   │   ├── weather.py          Open-Meteo client, caching, advisories
│   │   ├── irrigation.py       FAO-56 water balance and energy model
│   │   ├── recommender.py      diagnosis interpretation and action plan
│   │   └── knowledge.py        loads the JSON knowledge base
│   ├── data/                   diseases.json, crops.json, soils.json
│   ├── templates/              Jinja2 HTML pages
│   └── static/                 CSS, JS (app.js, live.js), Chart.js, screenshots, sample leaves
├── ml/
│   ├── train.py                transfer learning with train/val/test split
│   ├── evaluate.py             accuracy, precision, recall, F1, confusion matrix
│   └── fetch_sample.py         download a PlantVillage sample
├── models/plant-disease-mobilenetv2/   model weights and evaluation results
├── scripts/                    download_model.py, seed_demo.py
├── tests/                      unit and end-to-end tests
└── instance/                   created at runtime: database, uploads, weather cache
```

**Tech stack:** Python, Flask, PyTorch, Hugging Face Transformers, scikit-learn, SQLite, Open-Meteo API, Chart.js, HTML, CSS and JavaScript.

---

## Suggested demo flow for the review (about 6 minutes)

1. **Landing page**: the product pitch, real screenshots, feature walkthrough, accuracy numbers and FAQ.
2. **Try the demo** (or log in on the split-screen login page), then the **Dashboard**: live weather, water lost vs rain chart, this week's advice, recent leaves.
3. **Check a leaf**: pick the *Tomato, late blight* sample, then **Check this leaf**. Walk through the diagnosis, confidence, top-3 guesses, what to do now, treatment, spray timing and water.
4. **Live scan**: start the camera and point it at a leaf, or at a leaf photo on another phone's screen. Watch the square turn red or green, then tap **Save report**.
5. Show the **crop-context** feature: click the *Potato, early blight* sample, change the crop back to *Tomato*, then analyse. The app warns that the photo may not show a tomato leaf.
6. **Irrigation planner**: wheat on flood versus drip; show the 7-day schedule, depletion chart and energy savings.
7. **The model** page: metrics, confusion matrix and the most common mix-ups. **About** page (inside the app after login): team, objectives mapped to features, architecture and methodology.

## Limitations and future scope

* PlantVillage images have plain backgrounds, so accuracy drops on cluttered field photos. Fine-tuning on field images (for example PlantDoc) would help.
* Only 14 crops are covered by disease detection. Other crops get irrigation and nutrition guidance.
* Soil moisture is estimated, not measured. IoT soil sensors or satellite data could calibrate it.
* Future work from the synopsis: Hindi and regional languages, SMS or WhatsApp alerts, IoT sensors, satellite imagery, and solar pump sizing.

## References

The full list is on the Project page and in the synopsis. Key sources: Mohanty et al. (2016); Hughes & Salathé (2015, PlantVillage); Allen et al. (1998), *FAO Irrigation and Drainage Paper 56*; Sandler et al. (2018), *MobileNetV2*.
