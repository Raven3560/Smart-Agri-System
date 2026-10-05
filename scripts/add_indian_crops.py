"""Add Indian crops and houseplants (money plant, tulsi) to agri/data/crops.json.

Crop coefficients (Kc), root depth and depletion fraction (p) come from FAO-56
Tables 12 and 22 where FAO lists the crop. Crops FAO does not list are
approximated from the closest listed crop and marked "kc_source": "Approximate".

Run once:  python scripts/add_indian_crops.py
"""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agri", "data", "crops.json")


def P(name, type_, signs, manage):
    return {"name": name, "type": type_, "signs": signs, "manage": manage}


# Hindi names, seasons and common problems for crops that were already in the database.
EXISTING = {
    "tomato": {"hindi": "Tamatar", "season": "Rabi / Kharif"},
    "potato": {"hindi": "Aloo", "season": "Rabi"},
    "bell_pepper": {"hindi": "Shimla mirch", "season": "Rabi"},
    "maize": {"hindi": "Makka", "season": "Kharif / Rabi"},
    "soybean": {"hindi": "Soyabean", "season": "Kharif", "problems": [
        P("Yellow mosaic virus", "Viral (whitefly)", "Bright yellow patches scattered on green leaves; small, few pods.",
          "Grow resistant varieties, pull out infected plants early, and control whitefly with yellow sticky traps."),
        P("Rust", "Fungal", "Tiny tan to reddish-brown pustules under the leaves; early leaf fall.",
          "Grow tolerant varieties and spray hexaconazole or propiconazole at first appearance."),
        P("Girdle beetle", "Pest", "Two rings cut around the stem or leaf stalk; the part above wilts and dries.",
          "Remove and destroy affected plant parts; spray a recommended insecticide if damage is widespread."),
    ]},
    "squash": {"hindi": "Chappan kaddu", "season": "Zaid"},
    "strawberry": {"hindi": "Strawberry", "season": "Rabi"},
    "apple": {"hindi": "Seb", "season": "Perennial"},
    "cherry": {"hindi": "Cherry", "season": "Perennial"},
    "peach": {"hindi": "Aadu", "season": "Perennial"},
    "orange": {"hindi": "Santra", "season": "Perennial"},
    "grape": {"hindi": "Angoor", "season": "Perennial"},
    "blueberry": {"hindi": "Blueberry", "season": "Perennial", "problems": [
        P("Iron chlorosis (high soil pH)", "Nutrition", "Young leaves turn yellow while the veins stay green.",
          "Bring soil pH down to 4.5-5.5 with elemental sulphur and use acidic mulch such as pine bark."),
        P("Root rot", "Oomycete", "Plants wilt and decline in wet, heavy soil.",
          "Plant on raised beds with good drainage and avoid overwatering."),
    ]},
    "raspberry": {"hindi": "Raspberry", "season": "Perennial", "problems": [
        P("Grey mould", "Fungal", "Grey fuzzy rot on ripe fruit, mostly in wet weather.",
          "Pick fruit often, remove rotten fruit, and keep rows narrow for air flow."),
        P("Cane blight", "Fungal", "Dark patches on canes near pruning wounds; side shoots wilt.",
          "Prune in dry weather and remove fruited canes after harvest."),
    ]},
    "wheat": {"hindi": "Gehun", "season": "Rabi", "problems": [
        P("Yellow (stripe) rust", "Fungal", "Yellow powdery stripes of pustules along the leaf veins, mostly in cool, humid weather in January and February.",
          "Grow resistant varieties. At the first stripes, spray propiconazole 25 EC @ 1 ml/L and repeat after 15 days if needed."),
        P("Loose smut", "Fungal (seed-borne)", "Ears come out as black powdery masses instead of grain.",
          "Sow certified seed treated with carboxin or tebuconazole. Pull out smutted plants in a bag and bury them."),
        P("Aphids", "Pest", "Small green insects clustered on leaves and ears, with sticky honeydew.",
          "Ladybird beetles usually keep them in check. Spray only if numbers are very high, using a recommended insecticide."),
    ]},
    "rice": {"hindi": "Dhan / Chawal", "season": "Kharif", "problems": [
        P("Blast", "Fungal", "Spindle-shaped spots with grey centres and brown edges on leaves. In neck blast the neck turns black and the panicle breaks.",
          "Avoid excess nitrogen and grow resistant varieties. Spray tricyclazole 75 WP @ 0.6 g/L at first symptoms and at heading."),
        P("Bacterial leaf blight", "Bacterial", "Leaves dry from the tip and edges in wavy yellow-white stripes.",
          "Use balanced nitrogen, drain the field during severe attack and grow resistant varieties. Antibiotic sprays are banned."),
        P("Brown planthopper", "Pest", "Plants yellow and dry in round patches (hopper burn). Brown insects sit at the base of the tillers.",
          "Avoid excess nitrogen, practise alternate wetting and drying, and leave gaps in the field for air. Spray only when numbers are high."),
    ]},
    "sugarcane": {"hindi": "Ganna", "season": "Annual (12-18 months)", "problems": [
        P("Red rot", "Fungal", "Top leaves dry. A split cane shows red tissue with white patches and smells sour.",
          "Plant healthy setts of resistant varieties. Uproot and burn affected clumps and don't ratoon an infected field."),
        P("Early shoot borer", "Pest", "Dead heart in young shoots that pulls out easily and smells bad.",
          "Trash mulching, timely earthing up, and release of Trichogramma egg parasitoids."),
        P("Grassy shoot", "Phytoplasma", "Many thin, pale, grassy shoots grow from one clump.",
          "Use healthy, hot-water-treated seed cane and pull out affected clumps."),
    ]},
    "cotton": {"hindi": "Kapas", "season": "Kharif", "problems": [
        P("Pink bollworm", "Pest", "Rosette-shaped flowers, holes in bolls, pink larvae inside and stained lint.",
          "Pheromone traps, timely end of the crop, and destroying crop residue. Follow local IPM advice for sprays."),
        P("Leaf curl virus (whitefly)", "Viral", "Leaves curl upward with thickened veins; whiteflies under the leaves.",
          "Resistant varieties, weed control, yellow sticky traps and neem oil. Avoid excess nitrogen."),
        P("Bacterial blight", "Bacterial", "Angular, water-soaked spots on leaves that turn black; black arm on stems.",
          "Use acid-delinted, treated seed and spray copper oxychloride 50 WP @ 3 g/L."),
    ]},
    "mustard": {"hindi": "Sarson", "season": "Rabi", "problems": [
        P("Alternaria blight", "Fungal", "Dark brown round spots with rings on leaves and pods.",
          "Sow on time and spray mancozeb 75 WP @ 2.5 g/L at first symptoms."),
        P("White rust", "Fungal", "White blister-like pustules under leaves; swollen, twisted flower shoots (stag head).",
          "Spray metalaxyl + mancozeb as per label and rotate crops."),
        P("Mustard aphid", "Pest", "Dense grey-green colonies on flower shoots and pods; poor pod set.",
          "Sow in October so the crop escapes peak aphid attack. Conserve ladybird beetles; spray only above the threshold."),
    ]},
    "chickpea": {"hindi": "Chana", "season": "Rabi", "problems": [
        P("Fusarium wilt", "Fungal", "Plants droop and dry in patches; brown-black streaks inside the stem.",
          "Grow resistant varieties, treat seed with Trichoderma, and rotate crops."),
        P("Pod borer", "Pest", "Holes in pods; green caterpillars eating the seeds.",
          "Pheromone traps, bird perches and NPV sprays. Use a recommended insecticide when larvae cross the threshold."),
        P("Ascochyta blight", "Fungal", "Brown spots with dark rings on leaves, stems and pods; plants collapse in wet weather.",
          "Use healthy seed and resistant varieties; spray mancozeb or chlorothalonil."),
    ]},
    "onion": {"hindi": "Pyaz", "season": "Rabi / Kharif", "problems": [
        P("Purple blotch", "Fungal", "Small white sunken spots on leaves that turn purple with a yellow margin.",
          "Spray mancozeb 75 WP @ 2.5 g/L with a sticker and rotate crops."),
        P("Thrips", "Pest", "Silvery white streaks on leaves; tips curl and dry.",
          "Blue sticky traps and a recommended insecticide. Avoid water stress, which makes damage worse."),
    ]},
}

NEW = {
    # ---------------- cereals and millets ----------------
    "bajra": {"name": "Pearl Millet", "hindi": "Bajra", "group": "Cereal", "season": "Kharif",
              "kc": [0.30, 1.00, 0.30], "root_m": 1.0, "p": 0.55, "perennial": False,
              "npk": "60-80 : 40 : 20 kg/ha",
              "tip": "Very drought tolerant. Tillering, flowering and grain filling are the stages where a missed irrigation hurts most. Avoid waterlogging.",
              "problems": [
                  P("Downy mildew (green ear)", "Fungal", "Yellow streaks on leaves with white downy growth underneath; ears turn into leafy structures.",
                    "Grow resistant hybrids, treat seed with metalaxyl, and pull out infected plants early."),
                  P("Ergot", "Fungal", "Pinkish, sticky droplets ooze from flowers; later dark hard bodies replace grains.",
                    "Soak seed in 10% salt water and discard floating bits. Time sowing so flowering avoids heavy rain."),
                  P("Smut", "Fungal", "Some grains become larger, green, then dark brown and full of black powder.",
                    "Grow resistant hybrids and rotate crops."),
              ]},
    "jowar": {"name": "Sorghum", "hindi": "Jowar", "group": "Cereal", "season": "Kharif / Rabi",
              "kc": [0.30, 1.05, 0.55], "root_m": 1.0, "p": 0.55, "perennial": False,
              "npk": "80-100 : 40 : 40 kg/ha",
              "tip": "Handles dry spells well. Booting, flowering and grain filling are the stages where water matters most.",
              "problems": [
                  P("Shoot fly", "Pest", "Central shoot of young seedlings dries (dead heart).",
                    "Sow early with the first rains, use a slightly higher seed rate, and treat seed with a recommended insecticide."),
                  P("Grain mould", "Fungal", "Grains turn pink, black or white and mouldy when it rains at maturity.",
                    "Harvest at maturity and dry the grain quickly; grow tolerant varieties."),
                  P("Anthracnose", "Fungal", "Reddish-purple oval spots on leaves that join together.",
                    "Resistant varieties, crop rotation and mancozeb spray at first symptoms."),
              ]},
    "ragi": {"name": "Finger Millet", "hindi": "Ragi / Mandua", "group": "Cereal", "season": "Kharif",
             "kc": [0.30, 1.00, 0.30], "root_m": 1.0, "p": 0.55, "perennial": False,
             "npk": "40-60 : 30-40 : 20-30 kg/ha",
             "tip": "Hardy and drought tolerant. In a dry spell, irrigate at tillering and flowering.",
             "problems": [
                 P("Blast", "Fungal", "Spindle-shaped spots on leaves; the neck and fingers of the ear turn black and dry.",
                   "Grow resistant varieties, treat seed with carbendazim, and spray tricyclazole at flowering if needed."),
                 P("Brown spot", "Fungal", "Small oval brown spots scattered on leaves.",
                   "Balanced fertilizer and mancozeb spray if spots spread."),
             ]},
    "barley": {"name": "Barley", "hindi": "Jau", "group": "Cereal", "season": "Rabi",
               "kc": [0.30, 1.15, 0.25], "root_m": 1.0, "p": 0.55, "perennial": False,
               "npk": "60 : 30 : 20 kg/ha",
               "tip": "Needs less water than wheat; two or three irrigations are usually enough.",
               "problems": [
                   P("Stripe rust", "Fungal", "Yellow stripes of powdery pustules on leaves.",
                     "Resistant varieties and a propiconazole spray at first appearance."),
                   P("Covered smut", "Fungal (seed-borne)", "Grains replaced by hard black smut balls.",
                     "Treat seed with carbendazim or tebuconazole before sowing."),
               ]},

    # ---------------- pulses ----------------
    "arhar": {"name": "Pigeon Pea", "hindi": "Arhar / Tur", "group": "Pulse", "season": "Kharif",
              "kc": [0.40, 1.15, 0.35], "kc_source": "Approximate", "root_m": 1.0, "p": 0.50, "perennial": False,
              "npk": "20 : 50 : 20 kg/ha + Rhizobium",
              "tip": "Deep-rooted and drought tolerant. Waterlogging causes wilt and root rot, so drain excess rain. Irrigate at flowering and pod filling if it is dry.",
              "problems": [
                  P("Fusarium wilt", "Fungal", "Plants wilt and dry, often in patches; brown-black streaks inside the stem.",
                    "Grow resistant varieties, rotate for three years, and treat seed with Trichoderma."),
                  P("Sterility mosaic", "Viral (mite-borne)", "Bushy, pale green plants with small leaves and no flowers.",
                    "Resistant varieties; pull out infected plants early and control mites."),
                  P("Pod borer", "Pest", "Holes in pods and caterpillars feeding on the seeds.",
                    "Pheromone traps and NPV; a recommended insecticide when larvae cross the threshold."),
              ]},
    "moong": {"name": "Green Gram", "hindi": "Moong", "group": "Pulse", "season": "Kharif / Zaid",
              "kc": [0.40, 1.05, 0.35], "root_m": 0.6, "p": 0.45, "perennial": False,
              "npk": "20 : 40 : 20 kg/ha + Rhizobium",
              "tip": "A short-duration crop. Keep the field drained; give a light irrigation at flowering and pod filling in the summer (Zaid) crop.",
              "problems": [
                  P("Yellow mosaic virus", "Viral (whitefly)", "Bright yellow and green patches on the leaves.",
                    "Grow resistant varieties, pull out infected plants, and control whitefly with yellow sticky traps."),
                  P("Powdery mildew", "Fungal", "White powder on leaves late in the season.",
                    "Wettable sulphur 80 WP @ 2 g/L at first symptoms."),
                  P("Cercospora leaf spot", "Fungal", "Brown spots with a grey centre and red-brown edge.",
                    "Crop rotation and a carbendazim or mancozeb spray."),
              ]},
    "urad": {"name": "Black Gram", "hindi": "Urad", "group": "Pulse", "season": "Kharif",
             "kc": [0.40, 1.05, 0.35], "root_m": 0.6, "p": 0.45, "perennial": False,
             "npk": "20 : 40 : 20 kg/ha + Rhizobium",
             "tip": "Sensitive to waterlogging; make drainage channels in the rainy season.",
             "problems": [
                 P("Yellow mosaic virus", "Viral (whitefly)", "Yellow mottling on leaves; plants stay small with few pods.",
                   "Resistant varieties, early removal of infected plants, and whitefly control."),
                 P("Leaf crinkle virus", "Viral", "Leaves become large, wrinkled and crinkled; flowers drop.",
                   "Use healthy seed and pull out infected plants."),
             ]},
    "masoor": {"name": "Lentil", "hindi": "Masoor", "group": "Pulse", "season": "Rabi",
               "kc": [0.40, 1.10, 0.30], "root_m": 0.6, "p": 0.50, "perennial": False,
               "npk": "20 : 40 : 20 kg/ha",
               "tip": "One or two light irrigations, at branching and at pod filling, are usually enough.",
               "problems": [
                   P("Rust", "Fungal", "Orange-brown pustules on leaves and stems.",
                     "Grow resistant varieties and spray mancozeb at first appearance."),
                   P("Wilt", "Fungal", "Plants yellow, droop and dry in patches.",
                     "Resistant varieties, seed treatment with Trichoderma, and rotation."),
               ]},
    "peas": {"name": "Garden Pea", "hindi": "Matar", "group": "Pulse", "season": "Rabi",
             "kc": [0.50, 1.15, 1.10], "root_m": 0.6, "p": 0.35, "perennial": False,
             "npk": "20-25 : 60 : 40 kg/ha",
             "tip": "Flowering and pod filling are critical. Give light irrigations and avoid standing water.",
             "problems": [
                 P("Powdery mildew", "Fungal", "White powdery coating on leaves, stems and pods.",
                   "Wettable sulphur 80 WP @ 2 g/L; early sowing helps escape it."),
                 P("Rust", "Fungal", "Yellow-orange pustules turning brown on leaves and stems.",
                   "Resistant varieties and a mancozeb spray."),
             ]},

    # ---------------- oilseeds ----------------
    "groundnut": {"name": "Groundnut", "hindi": "Moongphali", "group": "Oilseed", "season": "Kharif",
                  "kc": [0.40, 1.15, 0.60], "root_m": 0.5, "p": 0.50, "perennial": False,
                  "npk": "20-25 : 40-60 : 30-40 kg/ha + gypsum at pegging",
                  "tip": "Pegging and pod development are critical. Keep the soil moist and loose when pegs enter the soil.",
                  "problems": [
                      P("Tikka leaf spot", "Fungal", "Brown to black round spots on leaves, often with a yellow halo; heavy leaf fall.",
                        "Crop rotation and a carbendazim + mancozeb or tebuconazole spray."),
                      P("Stem rot", "Fungal", "Plant wilts; white cottony fungus with mustard-seed-like bodies at the stem base.",
                        "Deep summer ploughing, Trichoderma in the soil, and avoid heaping soil on the stem."),
                      P("Leaf miner", "Pest", "Brown blotches on leaves; leaves fold and dry.",
                        "Light traps and a recommended insecticide when damage is high."),
                  ]},
    "sunflower": {"name": "Sunflower", "hindi": "Surajmukhi", "group": "Oilseed", "season": "Rabi / Zaid",
                  "kc": [0.35, 1.08, 0.35], "root_m": 0.8, "p": 0.45, "perennial": False,
                  "npk": "60-90 : 60-90 : 40-60 kg/ha",
                  "tip": "Button stage, flowering and seed filling are the critical stages for water.",
                  "problems": [
                      P("Alternaria blight", "Fungal", "Dark brown spots with rings on leaves and stems.",
                        "Mancozeb 75 WP @ 2.5 g/L at first symptoms."),
                      P("Head rot", "Fungal", "Soft, water-soaked rot on the back of the head after rain.",
                        "Avoid injury to heads and spray mancozeb if rain is expected at flowering."),
                  ]},
    "sesame": {"name": "Sesame", "hindi": "Til", "group": "Oilseed", "season": "Kharif",
               "kc": [0.35, 1.10, 0.25], "root_m": 1.0, "p": 0.60, "perennial": False,
               "npk": "40 : 20-40 : 20 kg/ha",
               "tip": "Very sensitive to waterlogging. Irrigate lightly only in long dry spells.",
               "problems": [
                   P("Phyllody", "Phytoplasma (leafhopper)", "Flowers turn into green leafy structures and no pods form.",
                     "Pull out affected plants and control leafhoppers."),
                   P("Stem and root rot", "Fungal", "Plants wilt; black dots on the stem base and roots.",
                     "Seed treatment with Trichoderma or carbendazim and good drainage."),
               ]},
    "castor": {"name": "Castor", "hindi": "Arandi", "group": "Oilseed", "season": "Kharif",
               "kc": [0.35, 1.15, 0.55], "root_m": 1.0, "p": 0.50, "perennial": False,
               "npk": "40-60 : 40 : 20 kg/ha",
               "tip": "Drought tolerant, but irrigation during spike development raises yield.",
               "problems": [
                   P("Grey rot", "Fungal", "Grey fungal growth on spikes and capsules in wet weather.",
                     "Remove affected spikes and spray carbendazim when rain is forecast at flowering."),
                   P("Semilooper", "Pest", "Caterpillars that move in loops eat the leaves.",
                     "Hand-pick young larvae and spray a recommended insecticide if defoliation is severe."),
               ]},

    # ---------------- vegetables ----------------
    "brinjal": {"name": "Brinjal", "hindi": "Baingan", "group": "Vegetable", "season": "All seasons",
                "kc": [0.60, 1.05, 0.90], "root_m": 0.7, "p": 0.45, "perennial": False,
                "npk": "100-120 : 60 : 50 kg/ha",
                "tip": "Irrigate every 3-4 days in summer and every 7-10 days in winter. Avoid stress at flowering and fruiting.",
                "problems": [
                    P("Shoot and fruit borer", "Pest", "Tips of shoots wilt; fruits have holes with frass.",
                      "Cut and destroy affected shoots and fruits every week, use pheromone traps, and spray a recommended insecticide."),
                    P("Phomopsis blight", "Fungal", "Grey-brown spots on leaves; sunken, rotting patches on fruit.",
                      "Use healthy seed, rotate crops, and spray mancozeb or carbendazim."),
                    P("Little leaf", "Phytoplasma (leafhopper)", "Very small, narrow leaves and a bushy plant with no fruit.",
                      "Pull out affected plants early and control leafhoppers."),
                ]},
    "okra": {"name": "Okra", "hindi": "Bhindi", "group": "Vegetable", "season": "Kharif / Zaid",
             "kc": [0.50, 1.10, 0.80], "kc_source": "Approximate", "root_m": 0.6, "p": 0.45, "perennial": False,
             "npk": "100 : 50 : 50 kg/ha",
             "tip": "Needs regular moisture during flowering and picking. In summer, irrigate every 4-5 days.",
             "problems": [
                 P("Yellow vein mosaic virus", "Viral (whitefly)", "Leaf veins turn yellow in a net pattern; fruits are pale and small.",
                   "Grow tolerant hybrids, pull out infected plants, and control whitefly."),
                 P("Shoot and fruit borer", "Pest", "Drooping shoot tips and bored, misshapen pods.",
                   "Remove affected shoots and pods, use pheromone traps, and spray if damage is heavy."),
                 P("Powdery mildew", "Fungal", "White powder on older leaves.",
                   "Wettable sulphur 80 WP @ 2 g/L."),
             ]},
    "chilli": {"name": "Chilli", "hindi": "Mirch", "group": "Vegetable", "season": "Kharif / Rabi",
               "kc": [0.60, 1.05, 0.90], "root_m": 0.5, "p": 0.30, "perennial": False,
               "npk": "100-120 : 50-60 : 50-60 kg/ha",
               "tip": "Chilli dislikes both drought and waterlogging. Light, frequent irrigation; drip works well.",
               "problems": [
                   P("Leaf curl", "Viral (whitefly, thrips)", "Leaves curl, crinkle and shrink; plants are stunted.",
                     "Raise seedlings under insect net, pull out infected plants, and control whitefly and thrips."),
                   P("Die-back and fruit rot", "Fungal", "Twigs dry from the tip; sunken dark spots on ripe fruit.",
                     "Prune affected twigs and spray carbendazim or mancozeb."),
                   P("Thrips and mites", "Pest", "Leaves curl upward (thrips) or downward (mites) and look bronzed.",
                     "Blue sticky traps, neem oil, and a recommended miticide or insecticide."),
               ]},
    "cauliflower": {"name": "Cauliflower", "hindi": "Phool gobhi", "group": "Vegetable", "season": "Rabi",
                    "kc": [0.70, 1.05, 0.95], "root_m": 0.4, "p": 0.45, "perennial": False,
                    "npk": "120 : 60 : 60 kg/ha + boron",
                    "tip": "Keep the soil evenly moist during curd formation. Boron shortage causes brown, hollow curds.",
                    "problems": [
                        P("Black rot", "Bacterial", "V-shaped yellow patches from the leaf edge with black veins.",
                          "Hot-water treated seed, crop rotation, and copper oxychloride sprays."),
                        P("Diamondback moth", "Pest", "Small green caterpillars make windows and holes in leaves.",
                          "Grow mustard as a trap crop, use pheromone traps, and spray Bt or a recommended insecticide."),
                    ]},
    "cabbage": {"name": "Cabbage", "hindi": "Patta gobhi", "group": "Vegetable", "season": "Rabi",
                "kc": [0.70, 1.05, 0.95], "root_m": 0.5, "p": 0.45, "perennial": False,
                "npk": "120 : 60 : 60 kg/ha",
                "tip": "Uneven watering causes heads to split. Keep moisture steady as heads form.",
                "problems": [
                    P("Diamondback moth", "Pest", "Holes and windows in leaves; small green caterpillars.",
                      "Mustard trap crop, pheromone traps, and Bt sprays."),
                    P("Black rot", "Bacterial", "Yellow V-shaped patches from leaf edges with blackened veins.",
                      "Treated seed, rotation and copper oxychloride."),
                ]},
    "cucumber": {"name": "Cucumber", "hindi": "Kheera", "group": "Vegetable", "season": "Zaid / Kharif",
                 "kc": [0.60, 1.00, 0.75], "root_m": 0.7, "p": 0.50, "perennial": False,
                 "npk": "80-100 : 50 : 50 kg/ha",
                 "tip": "Water at the base, not on the leaves. Uneven watering gives bitter, misshapen fruit.",
                 "problems": [
                     P("Downy mildew", "Oomycete", "Angular yellow patches on the upper leaf; grey-purple growth underneath.",
                       "Wider spacing, drip irrigation, and metalaxyl + mancozeb sprays."),
                     P("Fruit fly", "Pest", "Fruits rot with maggots inside.",
                       "Collect and destroy fallen fruit, and use cue-lure traps."),
                 ]},
    "bottle_gourd": {"name": "Bottle Gourd", "hindi": "Lauki", "group": "Vegetable", "season": "Zaid / Kharif",
                     "kc": [0.50, 1.00, 0.80], "kc_source": "Approximate", "root_m": 1.0, "p": 0.35, "perennial": False,
                     "npk": "80 : 40 : 40 kg/ha",
                     "tip": "Grows fast in heat. Irrigate every 4-5 days in summer and train vines on a trellis.",
                     "problems": [
                         P("Fruit fly", "Pest", "Fruits turn soft and rot with maggots inside.",
                           "Destroy infested fruit and use cue-lure traps."),
                         P("Red pumpkin beetle", "Pest", "Orange beetles eat holes in seedling leaves.",
                           "Hand-pick beetles in the morning and protect seedlings early."),
                         P("Downy mildew", "Oomycete", "Yellow angular patches on leaves.",
                           "Mancozeb sprays and good air flow."),
                     ]},
    "bitter_gourd": {"name": "Bitter Gourd", "hindi": "Karela", "group": "Vegetable", "season": "Zaid / Kharif",
                     "kc": [0.60, 1.00, 0.75], "kc_source": "Approximate", "root_m": 0.7, "p": 0.50, "perennial": False,
                     "npk": "80 : 50 : 50 kg/ha",
                     "tip": "Keep soil moist but drained; a trellis keeps fruit clean and reduces disease.",
                     "problems": [
                         P("Fruit fly", "Pest", "Fruits with sting marks rot and drop.",
                           "Bag young fruits where practical and use cue-lure traps."),
                         P("Powdery mildew", "Fungal", "White powder on leaves.",
                           "Wettable sulphur on cool mornings."),
                     ]},
    "pumpkin": {"name": "Pumpkin", "hindi": "Kaddu / Sitaphal", "group": "Vegetable", "season": "Zaid / Kharif",
                "kc": [0.50, 1.00, 0.80], "root_m": 1.0, "p": 0.35, "perennial": False,
                "npk": "80 : 40 : 40 kg/ha",
                "tip": "Deep watering once or twice a week is better than daily sprinkling.",
                "problems": [
                    P("Powdery mildew", "Fungal", "White powder spreading over leaves.",
                      "Wettable sulphur or hexaconazole at first spots."),
                    P("Red pumpkin beetle", "Pest", "Holes in young leaves.",
                      "Hand-pick beetles and protect seedlings."),
                ]},
    "watermelon": {"name": "Watermelon", "hindi": "Tarbooz", "group": "Vegetable", "season": "Zaid",
                   "kc": [0.40, 1.00, 0.75], "root_m": 0.8, "p": 0.40, "perennial": False,
                   "npk": "100 : 50 : 50 kg/ha",
                   "tip": "Cut back irrigation as fruits ripen for sweeter fruit and less cracking.",
                   "problems": [
                       P("Fusarium wilt", "Fungal", "Vines wilt in the day and die; brown streaks inside the stem.",
                         "Resistant varieties and long crop rotation."),
                       P("Anthracnose", "Fungal", "Dark sunken spots on leaves and fruit.",
                         "Mancozeb or carbendazim sprays and healthy seed."),
                   ]},
    "carrot": {"name": "Carrot", "hindi": "Gajar", "group": "Vegetable", "season": "Rabi",
               "kc": [0.70, 1.05, 0.95], "root_m": 0.5, "p": 0.35, "perennial": False,
               "npk": "60-80 : 40-60 : 60-80 kg/ha",
               "tip": "Even moisture gives straight, smooth roots. Heavy watering after dry spells makes roots crack.",
               "problems": [
                   P("Root cracking and forking", "Physiological", "Split or branched roots.",
                     "Even watering, loose stone-free soil, and no fresh manure."),
               ]},
    "radish": {"name": "Radish", "hindi": "Mooli", "group": "Vegetable", "season": "Rabi",
               "kc": [0.70, 0.90, 0.85], "root_m": 0.3, "p": 0.30, "perennial": False,
               "npk": "60 : 40 : 40 kg/ha",
               "tip": "Shallow roots. Water lightly and often; dry soil makes roots pithy and hot.",
               "problems": [
                   P("Aphids", "Pest", "Colonies of small insects under leaves; leaves curl.",
                     "Neem oil and a strong water spray; insecticide only if severe."),
               ]},
    "spinach": {"name": "Spinach", "hindi": "Palak", "group": "Vegetable", "season": "Rabi",
                "kc": [0.70, 1.00, 0.95], "root_m": 0.3, "p": 0.20, "perennial": False,
                "npk": "80-100 : 40 : 40 kg/ha",
                "tip": "Keep the soil moist all the time; give nitrogen after each cutting.",
                "problems": [
                    P("Leaf spot", "Fungal", "Small round brown spots on leaves.",
                      "Remove spotted leaves and avoid overhead watering."),
                ]},
    "garlic": {"name": "Garlic", "hindi": "Lahsun", "group": "Vegetable", "season": "Rabi",
               "kc": [0.70, 1.00, 0.70], "root_m": 0.3, "p": 0.30, "perennial": False,
               "npk": "100 : 50 : 50 kg/ha",
               "tip": "Shallow roots; irrigate every 7-10 days and stop 2-3 weeks before harvest.",
               "problems": [
                   P("Purple blotch", "Fungal", "Purple spots with yellow margins on leaves.",
                     "Mancozeb sprays with a sticker."),
                   P("Thrips", "Pest", "Silvery streaks on leaves.",
                     "Blue sticky traps and a recommended insecticide."),
               ]},
    "malabar_spinach": {"name": "Malabar Spinach", "hindi": "Poi", "group": "Vegetable", "season": "Kharif / Zaid",
                        "kc": [0.70, 1.00, 0.95], "kc_source": "Approximate", "root_m": 0.4, "p": 0.30,
                        "perennial": False, "npk": "60-80 : 40 : 40 kg/ha",
                        "tip": "A climbing vine that loves heat and moisture. Give it a trellis, keep the soil moist, and pick leaves often.",
                        "problems": []},
    "sweet_potato": {"name": "Sweet Potato", "hindi": "Shakarkand", "group": "Vegetable", "season": "Kharif",
                     "kc": [0.50, 1.15, 0.65], "root_m": 1.0, "p": 0.65, "perennial": False,
                     "npk": "50-75 : 50 : 75 kg/ha",
                     "tip": "Tolerates dry spells; irrigate during tuber formation if it is dry.",
                     "problems": [
                         P("Sweet potato weevil", "Pest", "Tunnels in tubers with a bitter smell.",
                           "Use clean vine cuttings, earth up to cover cracks, and rotate crops."),
                     ]},

    # ---------------- spices ----------------
    "turmeric": {"name": "Turmeric", "hindi": "Haldi", "group": "Spice", "season": "Kharif (about 9 months)",
                 "kc": [0.60, 1.10, 0.80], "kc_source": "Approximate", "root_m": 0.5, "p": 0.45, "perennial": False,
                 "npk": "60 : 50 : 120 kg/ha + farmyard manure",
                 "tip": "Needs steady moisture and good drainage. Mulch the beds with leaves after planting.",
                 "problems": [
                     P("Rhizome rot", "Oomycete", "Lower leaves yellow; collar becomes soft and the rhizome rots.",
                       "Good drainage, healthy seed rhizomes treated with mancozeb or Trichoderma, and removal of affected clumps."),
                     P("Leaf blotch", "Fungal", "Many small yellowish spots on both sides of the leaf.",
                       "Mancozeb or carbendazim spray."),
                 ]},
    "ginger": {"name": "Ginger", "hindi": "Adrak", "group": "Spice", "season": "Kharif",
               "kc": [0.60, 1.10, 0.80], "kc_source": "Approximate", "root_m": 0.4, "p": 0.45, "perennial": False,
               "npk": "75 : 50 : 50 kg/ha + farmyard manure",
               "tip": "Likes partial shade, moist soil and excellent drainage. Mulch heavily.",
               "problems": [
                   P("Soft rot", "Oomycete", "Pseudostem yellows and collapses; rhizome becomes soft and smelly.",
                     "Drainage, treated seed rhizomes, and removal of affected clumps."),
                   P("Bacterial wilt", "Bacterial", "Sudden wilting; milky ooze from cut stems.",
                     "Use disease-free seed and rotate away from tomato, potato and chilli."),
               ]},

    # ---------------- fruits and plantation ----------------
    "banana": {"name": "Banana", "hindi": "Kela", "group": "Fruit tree", "season": "Perennial",
               "kc": [0.50, 1.10, 1.00], "root_m": 0.5, "p": 0.35, "perennial": True,
               "npk": "200 : 60 : 300 g per plant per crop, in splits",
               "tip": "Needs plenty of water. Drip irrigation with mulch can save about 40-50% water.",
               "problems": [
                   P("Panama wilt", "Fungal", "Older leaves yellow and hang down; the pseudostem splits; brown streaks inside.",
                     "Use tissue-culture plants, remove infected plants, and don't replant banana in the same pit."),
                   P("Sigatoka leaf spot", "Fungal", "Yellow streaks that become brown spots with grey centres.",
                     "Remove infected leaves and spray propiconazole with mineral oil."),
                   P("Bunchy top", "Viral (aphid)", "Narrow, upright, bunched leaves with dark green streaks.",
                     "Pull out infected plants and use virus-free tissue-culture plants."),
               ]},
    "mango": {"name": "Mango", "hindi": "Aam", "group": "Fruit tree", "season": "Perennial",
              "kc": [0.60, 0.85, 0.75], "kc_source": "Approximate", "root_m": 1.0, "p": 0.65, "perennial": True,
              "npk": "About 1 kg N, 0.5 kg P2O5 and 1 kg K2O per year for a 10-year tree, in splits",
              "tip": "Stop irrigation for 2-3 months before flowering to encourage blossoms, then irrigate during fruit development.",
              "problems": [
                  P("Powdery mildew", "Fungal", "White powder on flowers and young fruits, which then drop.",
                    "Wettable sulphur @ 2 g/L when panicles appear."),
                  P("Anthracnose", "Fungal", "Black spots on leaves, flowers and ripening fruit.",
                    "Carbendazim or copper oxychloride sprays; prune dead twigs."),
                  P("Mango hopper", "Pest", "Flowers dry and drop; sticky honeydew and black sooty mould.",
                    "Spray a recommended insecticide at flower-bud stage; keep the orchard open and clean."),
              ]},
    "guava": {"name": "Guava", "hindi": "Amrood", "group": "Fruit tree", "season": "Perennial",
              "kc": [0.60, 0.85, 0.75], "kc_source": "Approximate", "root_m": 1.0, "p": 0.50, "perennial": True,
              "npk": "Per tree, based on tree age; split doses before flowering",
              "tip": "Hardy tree. Irrigate during flowering and fruit growth; avoid waterlogging.",
              "problems": [
                  P("Wilt", "Fungal", "Leaves yellow and branches dry one after another.",
                    "Remove affected trees, improve drainage, and add Trichoderma to the soil."),
                  P("Fruit fly", "Pest", "Fruits rot with maggots inside, mostly in the rainy season.",
                    "Collect fallen fruit and use methyl eugenol traps."),
              ]},
    "papaya": {"name": "Papaya", "hindi": "Papita", "group": "Fruit tree", "season": "Perennial",
               "kc": [0.60, 1.00, 0.85], "kc_source": "Approximate", "root_m": 0.6, "p": 0.40, "perennial": True,
               "npk": "200 : 200 : 400 g per plant per year, in splits",
               "tip": "Very sensitive to waterlogging; a few hours of standing water can kill plants. Use raised beds.",
               "problems": [
                   P("Ring spot virus", "Viral (aphid)", "Mottled leaves; ring-shaped spots on fruit.",
                     "Use healthy seedlings, grow a border crop such as maize, and pull out infected plants."),
                   P("Foot rot", "Oomycete", "Water-soaked rot at the stem base; the plant topples.",
                     "Good drainage and keep water away from the stem."),
               ]},
    "pomegranate": {"name": "Pomegranate", "hindi": "Anar", "group": "Fruit tree", "season": "Perennial",
                    "kc": [0.45, 0.85, 0.65], "kc_source": "Approximate", "root_m": 1.0, "p": 0.50, "perennial": True,
                    "npk": "Per tree, based on tree age and crop regulation (bahar)",
                    "tip": "Drought tolerant, but uneven watering cracks the fruit. Use drip and keep moisture steady.",
                    "problems": [
                        P("Bacterial blight", "Bacterial", "Oily, water-soaked spots on leaves and fruit that crack.",
                          "Prune and burn infected parts, and spray copper oxychloride. Antibiotic sprays are banned."),
                        P("Fruit borer", "Pest", "Holes in fruit with rotting inside.",
                          "Bag fruits and remove damaged fruit."),
                    ]},
    "coconut": {"name": "Coconut", "hindi": "Nariyal", "group": "Plantation", "season": "Perennial",
                "kc": [0.95, 1.00, 1.00], "root_m": 0.7, "p": 0.65, "perennial": True,
                "npk": "500 : 320 : 1200 g per palm per year, in two splits",
                "tip": "Irrigate regularly in summer; basin irrigation with husk burial or drip saves water.",
                "problems": [
                    P("Bud rot", "Oomycete", "The spear leaf yellows and pulls out; the crown rots and smells foul.",
                      "Remove rotten tissue and apply Bordeaux paste; spray Bordeaux mixture before the monsoon."),
                    P("Rhinoceros beetle", "Pest", "V-shaped cuts in opened leaves.",
                      "Hook out beetles, keep the area clean of manure pits, and use pheromone traps."),
                ]},
    "tea": {"name": "Tea", "hindi": "Chai", "group": "Plantation", "season": "Perennial",
            "kc": [0.95, 1.00, 1.00], "root_m": 0.9, "p": 0.40, "perennial": True,
            "npk": "Based on yield and soil test; split through the plucking season",
            "tip": "Needs well-distributed rain; sprinkler irrigation in dry months keeps bushes flushing.",
            "problems": [
                P("Blister blight", "Fungal", "Pale translucent spots on young leaves that blister underneath.",
                  "Copper-based sprays during the wet season and shorter plucking rounds."),
                P("Tea mosquito bug", "Pest", "Dark spots on young shoots, which dry.",
                  "Remove shade-tree weeds and spray a recommended insecticide."),
            ]},
    "coffee": {"name": "Coffee", "hindi": "Coffee", "group": "Plantation", "season": "Perennial",
               "kc": [0.90, 0.95, 0.95], "root_m": 0.9, "p": 0.40, "perennial": True,
               "npk": "Based on yield and soil test; split before and after the monsoon",
               "tip": "A blossom irrigation (about 25 mm) in February-March triggers uniform flowering.",
               "problems": [
                   P("Leaf rust", "Fungal", "Orange powdery spots under the leaves; heavy leaf fall.",
                     "Resistant varieties and Bordeaux mixture or systemic fungicide sprays."),
                   P("White stem borer", "Pest", "Yellowing branches and holes in the main stem.",
                     "Maintain shade, scrub the stem bark, and uproot badly affected plants."),
               ]},

    # ---------------- houseplants ----------------
    "money_plant": {"name": "Money Plant", "hindi": "Pothos", "group": "Houseplant", "season": "Year-round",
                    "kind": "houseplant", "kc": [0.30, 0.30, 0.30], "root_m": 0.2, "p": 0.50, "perennial": True,
                    "npk": "Balanced liquid fertilizer once a month in spring and summer",
                    "tip": "Most money plant problems come from overwatering, not underwatering.",
                    "care": {
                        "water_days": {"hot": 6, "warm": 8, "cool": 12},
                        "light": "Bright, indirect light. Gentle morning sun is fine; harsh afternoon sun scorches the leaves.",
                        "watering": "Water when the top 2-3 cm of soil feel dry, until water drains from the bottom. Empty the saucer after 15 minutes.",
                        "water_grown": "Growing it in a bottle of water? Change the water every 7-10 days and keep the nodes under water, not the leaves.",
                        "fertilizer": "A balanced liquid fertilizer (such as NPK 19:19:19 at 1 g per litre) once a month in spring and summer. No feeding in winter.",
                    },
                    "problems": [
                        P("Root rot (overwatering)", "Fungal", "Yellow leaves, black mushy stems at the soil line, and a sour smell from the pot.",
                          "Let the soil dry out, cut away black roots, and repot in fresh mix in a pot with a drainage hole."),
                        P("Brown, crispy leaf edges", "Care", "Leaf tips and edges turn brown and dry.",
                          "Water thoroughly when the topsoil is dry, keep it away from heater or AC vents, and flush the soil every few months."),
                        P("Mealybugs", "Pest", "White cottony clusters in leaf joints; sticky leaves.",
                          "Wipe them off with cotton dipped in rubbing alcohol, then spray neem oil (5 ml per litre with a few drops of soap) weekly."),
                        P("Leaf spot", "Fungal / bacterial", "Brown spots with yellow halos on leaves.",
                          "Remove affected leaves, water the soil rather than the leaves, and improve air flow."),
                    ]},
    "tulsi": {"name": "Tulsi", "hindi": "Holy basil", "group": "Houseplant", "season": "Year-round",
              "kind": "houseplant", "kc": [0.50, 0.50, 0.50], "root_m": 0.2, "p": 0.40, "perennial": True,
              "npk": "Compost or vermicompost every 4-6 weeks",
              "tip": "Pinch off the flower spikes (manjari) to keep the plant bushy and leafy.",
              "care": {
                  "water_days": {"hot": 1, "warm": 2, "cool": 4},
                  "light": "At least 4-6 hours of direct sun. A sunny balcony, terrace or courtyard is ideal.",
                  "watering": "Keep the soil lightly moist but never soggy. In peak summer a pot may need water every day.",
                  "water_grown": "",
                  "fertilizer": "Compost or vermicompost every 4-6 weeks. Avoid chemical sprays on leaves you will use.",
              },
              "problems": [
                  P("Wilting from overwatering", "Care", "Leaves droop and blacken even though the soil is wet.",
                    "Let the topsoil dry before watering again and make sure the pot drains."),
                  P("Downy mildew", "Oomycete", "Leaves yellow, with grey-purple fuzz underneath.",
                    "Remove affected leaves, give more sun and air, and avoid wetting the leaves."),
                  P("Winter dieback", "Care", "Leaves drop and stems blacken in cold weather.",
                    "Move the pot to a sunny, sheltered spot or indoors near a window, and water less in winter."),
              ]},
}

GROUP_ORDER = ["Cereal", "Pulse", "Oilseed", "Vegetable", "Fruit", "Fruit tree", "Fruit vine", "Fruit bush",
               "Spice", "Plantation", "Cash crop", "Houseplant"]


def main():
    with open(PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    crops = data["crops"]
    for key, extra in EXISTING.items():
        crops[key].update(extra)
    added = 0
    for key, crop in NEW.items():
        crop.setdefault("kc_source", "FAO-56")
        crop.setdefault("kind", "field")
        if key not in crops:
            added += 1
        crops[key] = crop
    for crop in crops.values():
        crop.setdefault("kc_source", "FAO-56")
        crop.setdefault("kind", "field")
        crop.setdefault("problems", [])
    data["groups"] = GROUP_ORDER
    data["_source"] = (
        "Crop coefficients (Kc) and depletion fraction (p) follow FAO Irrigation and Drainage Paper 56 (Allen et al., 1998), "
        "Tables 12 and 22. Root depths use the lower end of the FAO-56 Table 22 ranges, which FAO recommends for frequently "
        "irrigated crops. Crops not listed by FAO are approximated from the closest listed crop and marked "
        "kc_source = Approximate. NPK ranges are general reference values; always confirm with a soil test (Soil Health Card).")
    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print(f"Added {added} crops; database now has {len(crops)} crops.")


if __name__ == "__main__":
    main()
