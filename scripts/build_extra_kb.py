"""Build agri/data/diseases_extra.json: advice for every class of the extra-crops model.

Keys follow "<crop>___<class>", the folder names written by ml/fetch_agml.py.
Healthy entries are generated from the crop database. Run after editing:

    python scripts/build_extra_kb.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NO_ANTIBIOTICS = "Antibiotic sprays (streptomycin, tetracycline) are banned for farm use in India"


def wp(t_min, t_max, rh_min=0, rain=False, rh_max=None):
    p = {"t_min": t_min, "t_max": t_max, "rh_min": rh_min, "needs_rain": rain}
    if rh_max is not None:
        p = {"t_min": t_min, "t_max": t_max, "rh_max": rh_max, "needs_rain": False}
    return p


def D(name, type_, pathogen, impact, summary, symptoms, conditions, profile, cultural, organic, chemical,
      fertilizer, prevention):
    return {"name": name, "type": type_, "pathogen": pathogen, "impact": impact, "summary": summary,
            "symptoms": symptoms, "conditions": conditions, "weather_profile": profile,
            "treatment": {"cultural": cultural, "organic": organic, "chemical": chemical},
            "fertilizer": fertilizer, "prevention": prevention}


ENTRIES = {
    # ------------------------------------------------------------------ money plant
    "money_plant___bacterial_wilt": D(
        "Money Plant Bacterial Wilt", "Bacterial", "Bacteria such as Ralstonia and Xanthomonas species", "High",
        "A bacterial infection that causes dark, water-soaked patches, yellowing and drooping vines. It spreads quickly "
        "in warm, wet conditions and through cuttings and scissors.",
        ["Dark brown or black water-soaked patches on leaves, often with a yellow halo",
         "Vines droop even though the soil is moist"],
        "Warm temperatures, overwatering, leaves that stay wet, and infected cuttings or tools.", wp(24, 35, 80),
        ["Cut off and throw away infected leaves and vines; don't compost them",
         "Let the topsoil dry between waterings and water the soil, not the leaves",
         "Wipe scissors with alcohol after every cut"],
        ["Keep the plant apart from your other plants until new growth is clean"],
        ["Copper oxychloride 50 WP @ 2 g/L as a protective spray on the remaining leaves", NO_ANTIBIOTICS],
        ["Stop feeding until the plant recovers, then go back to light monthly feeding"],
        ["Take cuttings only from healthy vines", "Use a pot with a drainage hole and fresh potting mix"]),
    "money_plant___manganese_toxicity": D(
        "Money Plant Manganese Toxicity", "Nutritional disorder", "Not an infection: too much manganese in the soil",
        "Moderate",
        "Too much manganese reaches the plant, usually from acidic, waterlogged potting mix or extra micronutrient "
        "fertilizer. Leaves get brown speckles and yellowing.",
        ["Small brown or black specks on older leaves", "Yellowing between the veins and crinkled leaf edges"],
        "Very acidic or waterlogged potting mix, and fertilizers or sprays rich in micronutrients.", None,
        ["Flush the pot with plenty of clean water to wash out excess salts",
         "Repot into fresh, well-draining potting mix"],
        ["If the mix is very acidic, stir in a little garden lime or wood ash (check the pH first)"],
        ["Stop micronutrient sprays and fertilizers that contain manganese"],
        ["Use a plain balanced NPK fertilizer without micronutrients until new leaves come out clean"],
        ["Avoid overwatering: waterlogged, acidic soil releases more manganese", "Repot every 1-2 years"]),

    # ------------------------------------------------------------------ rice
    "rice___bacterial_blight": D(
        "Rice Bacterial Leaf Blight", "Bacterial", "Xanthomonas oryzae pv. oryzae", "High",
        "One of the most damaging rice diseases in India. Leaves dry from the tip in wavy yellow-white stripes, and "
        "early attacks (kresek) can kill young plants.",
        ["Leaves dry from the tip and edges in wavy yellow-white stripes",
         "Milky drops of bacterial ooze on young lesions in the morning"],
        "Warm, humid, windy and rainy weather, flooding, and heavy nitrogen.", wp(25, 34, 80, True),
        ["Drain the field for a few days during severe attack", "Apply nitrogen in splits and avoid excess"],
        ["Pseudomonas fluorescens seed treatment and spray, as per label"],
        ["Copper hydroxide 77 WP @ 2 g/L can slow the spread", NO_ANTIBIOTICS],
        ["Keep potassium adequate; it reduces blight"],
        ["Grow resistant varieties", "Remove weeds and stubble that carry the bacteria"]),
    "rice___blast": D(
        "Rice Blast", "Fungal", "Magnaporthe oryzae", "Severe",
        "A fungal disease that attacks leaves, nodes and the panicle neck. Neck blast can cause heavy grain loss.",
        ["Spindle-shaped spots with grey centres and brown edges on leaves",
         "The panicle neck turns black and the panicle breaks (neck blast)"],
        "Cool nights, long dew periods, high humidity and excess nitrogen.", wp(20, 28, 85),
        ["Avoid excess nitrogen and apply it in splits", "Destroy infected straw and stubble"],
        ["Seed treatment with Pseudomonas fluorescens or Trichoderma"],
        ["Tricyclazole 75 WP @ 0.6 g/L at first symptoms and again at heading",
         "Or azoxystrobin 23 SC @ 1 ml/L (rotate groups)"],
        ["Hold back the nitrogen top dressing while blast is active; keep potassium adequate"],
        ["Grow resistant varieties", "Treat seed with carbendazim or tricyclazole"]),
    "rice___brown_spot": D(
        "Rice Brown Spot", "Fungal", "Bipolaris oryzae", "Moderate",
        "A fungal leaf spot that is worst on poorly fed or drought-stressed rice. It also discolours grain.",
        ["Oval brown spots with grey centres, like sesame seeds, scattered over the leaf",
         "Dark spots on husks and discoloured grain"],
        "Nutrient-poor soils (low potassium, silicon or zinc), water stress and humid weather.", wp(25, 30, 85),
        ["Correct soil fertility, especially potassium", "Avoid water stress"],
        ["Seed treatment with Trichoderma or Pseudomonas fluorescens"],
        ["Mancozeb 75 WP @ 2.5 g/L or propiconazole 25 EC @ 1 ml/L"],
        ["Apply balanced NPK with potassium and zinc; brown spot is often a sign of poor nutrition"],
        ["Use clean, treated seed", "Keep soil fertility up with organic manure"]),
    "rice___tungro": D(
        "Rice Tungro", "Viral (leafhopper-borne)", "Rice tungro viruses, spread by green leafhoppers", "Severe",
        "A virus disease spread by green leafhoppers. Infected plants turn yellow-orange and stay stunted. There is no cure.",
        ["Yellow to orange leaves, starting from the tip", "Stunted plants with fewer tillers"],
        "High green leafhopper numbers and fields planted at different times in the same area.", None,
        ["Pull out and destroy infected hills early", "Plant at the same time as neighbouring fields"],
        ["Light traps to monitor leafhoppers"],
        ["No cure for the virus; control green leafhoppers with a recommended insecticide when numbers are high"],
        ["Balanced fertilizer; avoid excess nitrogen, which attracts leafhoppers"],
        ["Grow resistant varieties", "Remove ratoons and volunteer rice between seasons"]),

    # ------------------------------------------------------------------ sugarcane
    "sugarcane___banded_chlorosis": D(
        "Sugarcane Banded Chlorosis", "Physiological (cold injury)", "Not an infection: low night temperature",
        "Low",
        "Pale bands across the leaves caused by cold nights. The cane usually grows out of it when the weather warms.",
        ["Pale yellow-white bands running across the leaf blade", "Bands appear after cold nights"],
        "Night temperatures below about 10 °C.", None,
        ["No spray is needed; new leaves come out normal as it warms up",
         "A light irrigation before a forecast cold night reduces injury"],
        [], ["No chemical treatment needed"],
        ["Balanced nutrition helps new leaves grow out healthy"],
        ["Plant at the recommended time so young cane escapes cold spells"]),
    "sugarcane___brown_spot": D(
        "Sugarcane Brown Spot", "Fungal", "Cercospora longipes", "Moderate",
        "Reddish-brown leaf spots that join up and dry the leaves early in humid weather.",
        ["Small reddish-brown oval spots with a yellow halo on both leaf surfaces", "Spots join and leaves dry early"],
        "Warm, humid monsoon weather.", wp(24, 32, 85),
        ["Strip and burn badly infected lower leaves", "Avoid very dense planting"], [],
        ["Mancozeb 75 WP @ 2.5 g/L or carbendazim 50 WP @ 1 g/L"],
        ["Balanced NPK"], ["Grow resistant varieties"]),
    "sugarcane___brown_rust": D(
        "Sugarcane Brown Rust", "Fungal", "Puccinia melanocephala", "Moderate",
        "A rust that forms brown pustules under the leaves and dries them early, reducing cane growth.",
        ["Long orange-brown to dark brown pustules on the underside of leaves", "Leaves turn brown and dry"],
        "Mild temperatures with high humidity and heavy dew.", wp(18, 28, 85),
        ["Grow resistant varieties", "Avoid excess nitrogen"], [],
        ["Propiconazole 25 EC @ 1 ml/L or mancozeb 75 WP @ 2.5 g/L at first appearance"],
        ["Avoid excess nitrogen"], ["Grow resistant varieties"]),
    "sugarcane___grassy_shoot": D(
        "Sugarcane Grassy Shoot", "Phytoplasma (insect-borne)", "Sugarcane grassy shoot phytoplasma", "High",
        "A phytoplasma disease that makes a clump produce many thin, pale, grassy shoots and no usable cane.",
        ["Many thin, pale or white grassy shoots from one clump", "Stunted stalks with no millable cane"],
        "Spread through infected seed cane and leafhoppers.", None,
        ["Uproot and burn affected clumps", "Don't ratoon infected fields"], [],
        ["No cure; control leafhoppers with a recommended insecticide"],
        ["Balanced fertilizer keeps healthy clumps vigorous"],
        ["Plant seed cane treated with hot water or moist hot air (50-54 °C)",
         "Buy seed from certified, disease-free nurseries"]),
    "sugarcane___pokkah_boeng": D(
        "Sugarcane Pokkah Boeng", "Fungal", "Fusarium species", "Moderate",
        "A fungal disease of the youngest leaves during fast monsoon growth. Tops become twisted and pale; severe "
        "cases rot the top.",
        ["Young top leaves are crinkled, twisted and yellow-white at the base", "The top rots in severe cases"],
        "Hot, humid weather following a dry spell, during rapid growth.", wp(25, 32, 80),
        ["Remove and destroy severely affected tops"], [],
        ["Carbendazim 50 WP @ 1 g/L or copper oxychloride 50 WP @ 2 g/L, 2-3 sprays 10-15 days apart"],
        ["Balanced nutrition"], ["Grow tolerant varieties"]),
    "sugarcane___smut": D(
        "Sugarcane Smut", "Fungal", "Sporisorium scitamineum", "High",
        "A smut fungus that grows a long black whip from the top of the cane. Spores spread by wind to nearby clumps.",
        ["A long black whip grows out of the top of the cane", "Thin, grassy stalks with many tillers"],
        "Spread by wind-blown spores and infected setts; worse in ratoon crops.", None,
        ["Cover the whip with a bag, then cut and burn it before spores spread",
         "Don't ratoon heavily infected fields"], [],
        ["Dip setts in a recommended fungicide (such as propiconazole) before planting"],
        ["Balanced fertilizer"], ["Grow resistant varieties and plant healthy, treated setts"]),
    "sugarcane___mosaic": D(
        "Sugarcane Mosaic", "Viral (aphid-borne)", "Sugarcane mosaic virus and related viruses", "Moderate",
        "A virus disease that causes mosaic streaks on young leaves and can stunt the crop. It travels in seed cane.",
        ["Light and dark green mosaic patches or streaks on young leaves", "Stunted growth in severe cases"],
        "Spread through infected seed cane and aphids.", None,
        ["Remove infected clumps", "Control weeds that host aphids"], [],
        ["No cure; use virus-free seed cane"], ["Balanced fertilizer"],
        ["Plant virus-free seed cane and resistant varieties"]),
    "sugarcane___yellow_leaf": D(
        "Sugarcane Yellow Leaf", "Viral (aphid-borne)", "Sugarcane yellow leaf virus", "Moderate",
        "A virus disease that yellows the leaf midrib and can reduce cane yield and sugar.",
        ["Yellowing of the midrib on the underside of older leaves, spreading into the blade",
         "Leaves dry from the tip; tops look bunched"],
        "Spread through infected seed cane and aphids.", None,
        ["Use healthy seed cane", "Control aphids"], [], ["No cure; manage aphids if numbers are high"],
        ["Balanced fertilizer"], ["Plant virus-free (tissue-culture) seed cane", "Grow resistant varieties"]),

    # ------------------------------------------------------------------ cotton
    "cotton___alternaria_leaf_spot": D(
        "Cotton Alternaria Leaf Spot", "Fungal", "Alternaria macrospora", "Moderate",
        "Brown spots with rings that cause early leaf fall, especially on potassium-hungry plants.",
        ["Small brown spots with concentric rings on leaves", "Spots join and leaves drop early"],
        "Warm, humid weather and stressed, potassium-deficient plants.", wp(25, 30, 80),
        ["Remove infected leaves and crop debris"], [],
        ["Mancozeb 75 WP @ 2.5 g/L or propiconazole 25 EC @ 1 ml/L"],
        ["Correct potassium deficiency; stressed plants get more spots"],
        ["Rotate crops", "Use balanced fertilizer"]),
    "cotton___bacterial_blight": D(
        "Cotton Bacterial Blight", "Bacterial", "Xanthomonas citri pv. malvacearum", "High",
        "Angular leaf spots and black streaks on stems (black arm). Spreads with rain splash and infected seed.",
        ["Angular, water-soaked spots on leaves that turn brown-black", "Black streaks on stems and bolls"],
        "Warm, wet weather with wind-driven rain.", wp(25, 35, 85, True),
        ["Use acid-delinted, treated seed", "Remove infected crop residue"], [],
        ["Copper oxychloride 50 WP @ 3 g/L", NO_ANTIBIOTICS],
        ["Balanced fertilizer; avoid excess nitrogen"], ["Grow resistant varieties"]),
    "cotton___fusarium_wilt": D(
        "Cotton Fusarium Wilt", "Fungal (soil-borne)", "Fusarium oxysporum f. sp. vasinfectum", "High",
        "A soil-borne wilt that blocks the plant's water pipes. Once a plant wilts it can't be saved.",
        ["Leaves yellow and wilt, starting from the lower leaves", "Brown streaks inside the stem when cut"],
        "Warm soils, sandy acidic soils and root-knot nematodes.", None,
        ["Uproot and burn wilted plants", "Long crop rotation"],
        ["Apply Trichoderma mixed with farmyard manure to the soil"],
        ["No cure once wilted; seed treatment with carbendazim helps prevent it"],
        ["Adequate potassium reduces wilt"], ["Grow resistant varieties"]),
    "cotton___verticillium_wilt": D(
        "Cotton Verticillium Wilt", "Fungal (soil-borne)", "Verticillium dahliae", "High",
        "A soil-borne wilt that gives leaves a yellow tiger-stripe pattern before they drop.",
        ["Yellow patches between the veins that turn brown (tiger-stripe look)",
         "Leaves drop; brown streaks inside the stem"],
        "Cool, moist soil and heavy irrigation.", None,
        ["Destroy infected stalks after harvest", "Rotate with cereals"],
        ["Apply Trichoderma to the soil"], ["No effective chemical cure"],
        ["Avoid excess nitrogen"], ["Grow resistant varieties", "Avoid over-irrigation"]),

    # ------------------------------------------------------------------ mango
    "mango___anthracnose": D(
        "Mango Anthracnose", "Fungal", "Colletotrichum gloeosporioides", "High",
        "The most common mango disease. It spots leaves, blackens flowers and rots ripening fruit.",
        ["Dark brown to black irregular spots on leaves", "Spots join and leaves dry; black spots on flowers and fruit"],
        "Warm, wet weather, especially during new leaf flushes and flowering.", wp(24, 32, 85, True),
        ["Prune and burn diseased twigs and fallen leaves", "Open up the canopy for air flow"],
        ["Copper oxychloride 50 WP @ 3 g/L"],
        ["Carbendazim 50 WP @ 1 g/L or mancozeb 75 WP @ 2.5 g/L at new flush and at flowering"],
        ["Balanced manure and fertilizer for tree vigour"], ["Spray before flowering in rainy areas"]),
    "mango___bacterial_canker": D(
        "Mango Bacterial Canker", "Bacterial", "Xanthomonas campestris pv. mangiferaeindicae", "High",
        "Raised black spots on leaves and cracked cankers on twigs and fruit, spread by rain and wind.",
        ["Small water-soaked spots that turn black and raised, with a yellow halo",
         "Cracked cankers on twigs and fruit"],
        "Rain, wind and wounds.", wp(25, 35, 80, True),
        ["Prune and burn infected twigs", "Avoid injuring leaves and fruit"], [],
        ["Copper oxychloride 50 WP @ 3 g/L sprays", NO_ANTIBIOTICS],
        ["Balanced fertilizer"], ["Plant windbreaks", "Use healthy planting material"]),
    "mango___cutting_weevil": D(
        "Mango Leaf-cutting Weevil", "Pest", "Deporaus marginatus", "Moderate",
        "A weevil that cuts tender new leaves near the base. Cut leaves fall under the tree with eggs inside.",
        ["Young tender leaves cut cleanly near the base, as if with scissors", "Cut leaves lying under the tree"],
        "New leaf flushes in the rainy season.", None,
        ["Collect and destroy fallen cut leaves, which hold the eggs", "Plough the soil around the tree"], [],
        ["Spray a recommended insecticide on new flushes if damage is heavy"],
        ["Balanced fertilizer"], ["Watch new flushes closely"]),
    "mango___die_back": D(
        "Mango Die Back", "Fungal", "Lasiodiplodia theobromae", "High",
        "Twigs dry from the tip downward and branches may ooze gum. Stressed trees are hit hardest.",
        ["Twigs dry from the tip down; leaves turn brown and roll", "Gum oozes from cracks on branches"],
        "Stressed trees, rainy weather and pruning wounds.", None,
        ["Cut diseased twigs 5-8 cm below the dry part and burn them", "Paint cut ends with Bordeaux paste"], [],
        ["Copper oxychloride 50 WP @ 3 g/L after pruning"],
        ["Balanced manure and fertilizer to keep trees vigorous"], ["Avoid water stress and bark wounds"]),
    "mango___gall_midge": D(
        "Mango Gall Midge", "Pest", "Procontarinia species", "Moderate",
        "Tiny flies whose larvae form wart-like galls on leaves and attack flowers.",
        ["Small raised wart-like galls on leaves", "Deformed leaves; galls on flowers cause flower drop"],
        "Flushing and flowering periods.", None,
        ["Remove and destroy galled leaves and shoots", "Plough under the tree to expose pupae"], [],
        ["Spray a recommended insecticide at bud burst if galls were heavy last season"],
        ["Balanced fertilizer"], ["Monitor new flushes"]),
    "mango___powdery_mildew": D(
        "Mango Powdery Mildew", "Fungal", "Oidium mangiferae", "High",
        "White powder on flowers and tiny fruits that makes them drop. Can wipe out a season's fruit set.",
        ["White powdery coating on young leaves, flowers and tiny fruits", "Flowers and young fruits drop"],
        "Cool nights, warm days and cloudy, humid weather at flowering.", wp(15, 28, 60),
        ["Prune for air flow"], ["Wettable sulphur 80 WP @ 2 g/L when panicles emerge"],
        ["Hexaconazole 5 EC @ 1 ml/L or propiconazole 25 EC @ 1 ml/L"],
        ["Balanced fertilizer"], ["Spray at the start of flowering in prone areas"]),
    "mango___sooty_mould": D(
        "Mango Sooty Mould", "Fungal (grows on insect honeydew)", "Capnodium and related fungi", "Moderate",
        "A black coating that grows on the sticky honeydew of hoppers, scales and mealybugs. It blocks light rather "
        "than infecting the leaf.",
        ["Black, soot-like coating on the upper leaf that can be rubbed off",
         "Sap-sucking insects such as hoppers or scales nearby"],
        "Heavy populations of honeydew-producing insects.", None,
        ["Control the sap-sucking insects causing the honeydew",
         "Spray a 2% starch solution; it dries and peels off with the mould"],
        ["Neem oil 1500 ppm @ 3-5 ml/L against hoppers and scales"],
        ["Spray a recommended insecticide against hoppers if numbers are high"],
        ["Balanced fertilizer"], ["Control mango hoppers at flowering"]),

    # ------------------------------------------------------------------ banana
    "banana___cordana_leaf_spot": D(
        "Banana Cordana Leaf Spot", "Fungal", "Cordana musae", "Moderate",
        "Pale brown oval spots with a yellow halo that join into large dead patches in wet weather.",
        ["Pale brown oval spots with a yellow halo, often near the leaf edge", "Spots join into large dead patches"],
        "Wet, humid weather.", wp(22, 30, 85, True),
        ["Remove and burn infected leaves"], [],
        ["Mancozeb 75 WP @ 2.5 g/L or propiconazole 25 EC @ 1 ml/L"],
        ["Balanced fertilizer with enough potassium"], ["Good drainage and spacing"]),
    "banana___pestalotiopsis_leaf_spot": D(
        "Banana Pestalotiopsis Leaf Spot", "Fungal", "Pestalotiopsis species", "Low",
        "Grey-brown spots on older leaves, usually after injury. Rarely serious if the plantation is kept clean.",
        ["Grey-brown spots with dark margins, mostly on older leaves", "Tiny black dots in the spots"],
        "Wounds and humid weather.", wp(22, 32, 80),
        ["Remove dead and spotted leaves"], [],
        ["Carbendazim 50 WP @ 1 g/L or mancozeb 75 WP @ 2.5 g/L"],
        ["Balanced fertilizer"], ["Avoid wounds and keep the plantation clean"]),
    "banana___sigatoka": D(
        "Banana Sigatoka Leaf Spot", "Fungal", "Mycosphaerella species (yellow and black Sigatoka)", "High",
        "The most important banana leaf disease. It destroys leaf area so bunches fill poorly.",
        ["Pale yellow streaks that turn into brown spots with grey centres",
         "Large parts of leaves dry; bunches fill poorly"],
        "Warm, humid, rainy weather.", wp(24, 30, 85, True),
        ["Cut and burn badly infected leaves", "Improve drainage and spacing"], [],
        ["Propiconazole 25 EC @ 1 ml/L with mineral oil, as per label, alternated with mancozeb"],
        ["Adequate potassium"], ["Remove infected leaves regularly through the season"]),
    "banana___xanthomonas_wilt": D(
        "Banana Bacterial Wilt", "Bacterial", "Xanthomonas species", "Severe",
        "A serious bacterial wilt. Leaves yellow and wilt, fruit ripens unevenly and rots. There is no cure.",
        ["Leaves turn yellow and wilt, starting with the youngest",
         "Yellow bacterial ooze from cut stems; fruit ripens unevenly and rots"],
        "Spread by infected tools, planting material and insects visiting the male flower.", None,
        ["Uproot and destroy infected plants", "Clean tools with fire or bleach between plants",
         "Remove the male bud with a forked stick"], [], ["No chemical cure"],
        ["Balanced fertilizer"], ["Use clean, tissue-culture planting material"]),

    # ------------------------------------------------------------------ chilli
    "chilli___cercospora_leaf_spot": D(
        "Chilli Cercospora Leaf Spot (Frog-eye)", "Fungal", "Cercospora capsici", "Moderate",
        "Round 'frog-eye' spots that make leaves yellow and fall, weakening the plant.",
        ["Round spots with light grey centres and dark brown margins", "Leaves yellow and drop"],
        "Warm, humid weather.", wp(22, 30, 85),
        ["Remove infected leaves", "Rotate crops"], [],
        ["Mancozeb 75 WP @ 2.5 g/L or carbendazim 50 WP @ 1 g/L"],
        ["Balanced fertilizer"], ["Use healthy, treated seed"]),
    "chilli___mites_and_thrips": D(
        "Chilli Mites and Thrips (Leaf Curl)", "Pest", "Yellow mite and chilli thrips", "High",
        "Tiny sucking pests that curl and bronze chilli leaves. Thrips curl leaves upward; mites curl them downward.",
        ["Leaves curl upward and become boat-shaped (thrips) or downward with a bronze look (mites)",
         "Silvery scratches or tiny moving insects under the leaves"],
        "Hot, dry weather.", wp(28, 38, rh_max=60),
        ["Remove heavily infested leaves", "Spray water on leaf undersides"],
        ["Blue sticky traps for thrips", "Neem oil 1500 ppm @ 3-5 ml/L"],
        ["Mites: a recommended miticide such as spiromesifen 22.9 SC @ 1 ml/L",
         "Thrips: a recommended insecticide such as fipronil 5 SC @ 1.5 ml/L (rotate groups)"],
        ["Avoid excess nitrogen"], ["Grow 2-3 border rows of maize or sorghum"]),
    "chilli___nutrient_deficiency": D(
        "Chilli Nutrient Deficiency", "Nutritional disorder", "Shortage of nitrogen, magnesium, zinc or other nutrients",
        "Moderate",
        "Yellowing and poor growth caused by missing nutrients rather than disease.",
        ["Yellowing between the veins or of whole older leaves", "Pale, small new leaves"],
        "Poor or unbalanced soil, leaching rain, or root damage.", None,
        ["Get a soil test to find the missing nutrient"],
        ["Apply well-rotted compost or vermicompost"],
        ["Foliar spray of a micronutrient mix as per label; urea 1% if nitrogen is short"],
        ["Apply nitrogen in splits; correct magnesium (magnesium sulphate) and zinc (zinc sulphate) if deficient"],
        ["Fertilize based on a soil test"]),
    "chilli___powdery_mildew": D(
        "Chilli Powdery Mildew", "Fungal", "Leveillula taurica", "Moderate",
        "White powder under the leaves with yellow blotches on top, causing early leaf fall.",
        ["White powdery patches under leaves and yellow blotches on top", "Leaves fall early"],
        "Warm, dry days with humid nights.", wp(20, 30, 50),
        ["Remove the worst affected leaves"], ["Wettable sulphur 80 WP @ 2 g/L (not above 32 °C)"],
        ["Hexaconazole 5 EC @ 1 ml/L or azoxystrobin 23 SC @ 1 ml/L"],
        ["Balanced fertilizer"], ["Spray at the first spots"]),

    # ------------------------------------------------------------------ onion
    "onion___iris_yellow_spot_virus": D(
        "Onion Iris Yellow Spot Virus", "Viral (thrips-borne)", "Iris yellow spot virus, spread by onion thrips",
        "Moderate",
        "A thrips-spread virus that makes eye-shaped straw-coloured spots and early leaf drying.",
        ["Straw-coloured, diamond- or eye-shaped spots on leaves and flower stalks", "Leaves fall over and dry early"],
        "High thrips numbers in hot, dry weather.", None,
        ["Control thrips", "Remove volunteer onions and weeds"], ["Blue sticky traps"],
        ["No cure; control thrips with a recommended insecticide"],
        ["Balanced fertilizer"], ["Rotate crops and avoid planting next to older onion fields"]),
    "onion___leaf_blight": D(
        "Onion Leaf Blight", "Fungal", "Stemphylium vesicarium and Colletotrichum species", "High",
        "Spots that grow into long lesions and burn the leaf tips, cutting bulb size.",
        ["Small yellow to brown water-soaked spots that grow into long lesions", "Leaf tips burn and dry"],
        "Warm, humid weather and long dew periods.", wp(18, 30, 85),
        ["Remove crop debris", "Improve drainage"], [],
        ["Mancozeb 75 WP @ 2.5 g/L with a sticker, or tebuconazole 25.9 EC @ 1 ml/L"],
        ["Balanced fertilizer"], ["Rotate crops", "Avoid overhead irrigation"]),
    "onion___purple_blotch": D(
        "Onion Purple Blotch", "Fungal", "Alternaria porri", "High",
        "Purple lesions with yellow margins that can collapse leaves and seed stalks.",
        ["Small white sunken spots that become purple lesions with yellow margins", "Leaves collapse"],
        "Warm, humid weather.", wp(20, 30, 80),
        ["Remove crop debris"], [],
        ["Mancozeb 75 WP @ 2.5 g/L with a sticker every 10 days"],
        ["Balanced fertilizer"], ["Rotate crops", "Use healthy seed"]),

    # ------------------------------------------------------------------ groundnut
    "groundnut___alternaria_leaf_spot": D(
        "Groundnut Alternaria Leaf Spot", "Fungal", "Alternaria arachidis", "Moderate",
        "Brown spots that burn the leaf tips, mostly late in the season.",
        ["Small brown spots with a yellow halo, often at leaf tips", "Leaf tips dry and curl"],
        "Warm, humid weather late in the season.", wp(22, 30, 80),
        ["Remove crop debris"], [], ["Mancozeb 75 WP @ 2.5 g/L"],
        ["Balanced fertilizer with gypsum at pegging"], ["Rotate crops"]),
    "groundnut___tikka_leaf_spot": D(
        "Groundnut Tikka Leaf Spot", "Fungal", "Cercospora arachidicola and Phaeoisariopsis personata", "High",
        "Early and late leaf spots that strip plants of leaves before harvest.",
        ["Round brown to black spots on leaves, early ones with a yellow halo", "Heavy leaf fall before harvest"],
        "Warm, humid weather.", wp(24, 30, 85),
        ["Rotate with cereals", "Remove volunteer plants"], [],
        ["Carbendazim 12% + mancozeb 63% WP @ 2 g/L or tebuconazole 25.9 EC @ 1 ml/L"],
        ["Balanced fertilizer"], ["Grow resistant varieties"]),
    "groundnut___rosette": D(
        "Groundnut Rosette", "Viral (aphid-borne)", "Groundnut rosette virus complex", "High",
        "A virus that stunts plants into bushy rosettes with few or no pods. There is no cure.",
        ["Stunted, bushy plants with small, yellow or mottled leaves", "Few or no pods"],
        "Spread by aphids.", None,
        ["Pull out infected plants early", "Sow early and at close spacing"], [],
        ["No cure; control aphids if numbers are high"],
        ["Balanced fertilizer"], ["Grow resistant varieties"]),
    "groundnut___rust": D(
        "Groundnut Rust", "Fungal", "Puccinia arachidis", "High",
        "Orange-brown pustules under the leaves that dry the foliage and cut pod yield.",
        ["Orange-brown powdery pustules on the underside of leaves", "Leaves dry but stay attached"],
        "Warm, humid weather.", wp(20, 30, 85),
        ["Remove volunteer plants"], [],
        ["Chlorothalonil 75 WP @ 2 g/L or tebuconazole 25.9 EC @ 1 ml/L"],
        ["Balanced fertilizer"], ["Grow resistant varieties"]),

    # ------------------------------------------------------------------ turmeric
    "turmeric___aphids": D(
        "Turmeric Aphids", "Pest", "Aphid species", "Low",
        "Soft-bodied insects that suck sap from young leaves, leaving them curled and sticky.",
        ["Colonies of small soft insects on young leaves", "Leaves curl and become sticky"],
        "Mild weather and lush new growth.", None,
        ["Spray a strong jet of water to knock them off"], ["Neem oil 1500 ppm @ 3-5 ml/L"],
        ["Imidacloprid 17.8 SL @ 0.3 ml/L only for heavy infestations"],
        ["Avoid excess nitrogen"], ["Conserve ladybird beetles"]),
    "turmeric___leaf_blotch": D(
        "Turmeric Leaf Blotch", "Fungal", "Taphrina maculans", "Moderate",
        "Many small yellowish spots that join and give the leaves a reddish-brown, dried look.",
        ["Many small yellowish spots on both sides of leaves", "Spots join; leaves look reddish-brown and dry"],
        "Humid weather in the monsoon.", wp(20, 28, 80),
        ["Remove infected leaves"], [],
        ["Mancozeb 75 WP @ 2.5 g/L or propiconazole 25 EC @ 1 ml/L"],
        ["Balanced fertilizer"], ["Rotate crops"]),
    "turmeric___leaf_spot": D(
        "Turmeric Leaf Spot", "Fungal", "Colletotrichum capsici", "Moderate",
        "Oval brown spots with grey-white centres that dry the leaves.",
        ["Oval brown spots with grey-white centres on leaves", "Spots join and leaves dry"],
        "Humid weather.", wp(22, 30, 80),
        ["Remove infected leaves"], [],
        ["Carbendazim 50 WP @ 1 g/L or mancozeb 75 WP @ 2.5 g/L"],
        ["Balanced fertilizer"], ["Use healthy seed rhizomes", "Rotate crops"]),

    # ------------------------------------------------------------------ tea
    "tea___leaf_blight": D(
        "Tea Leaf Blight", "Fungal", "Colletotrichum and Pestalotiopsis species (brown and grey blight)", "Moderate",
        "Brown patches that start at the leaf edge or tip, often after plucking or hail injury.",
        ["Brown patches with dark margins starting at the leaf edge or tip", "Grey centres with tiny black dots"],
        "Wounds from plucking or hail, and humid weather.", wp(22, 30, 85),
        ["Prune affected shoots", "Avoid injuries during plucking"], [],
        ["Copper oxychloride 50 WP @ 2.5 g/L"], ["Balanced nutrition"], ["Keep bushes vigorous"]),
    "tea___red_leaf_spot": D(
        "Tea Red Leaf Spot", "Fungal", "Leaf-spotting fungi", "Low",
        "Small reddish-brown spots on mature leaves that can cause early leaf fall.",
        ["Small reddish-brown spots on mature leaves", "Spots enlarge and leaves fall early"],
        "Humid weather and stressed bushes.", wp(22, 30, 80),
        ["Remove and destroy fallen leaves"], [], ["Copper oxychloride 50 WP @ 2.5 g/L"],
        ["Balanced nutrition"], ["Keep bushes vigorous"]),
    "tea___red_scab": D(
        "Tea Red Scab", "Algal / fungal", "Often linked to red rust (Cephaleuros) on weak bushes", "Moderate",
        "Orange-red scabby patches on leaves and stems, usually on bushes weakened by poor drainage or nutrition.",
        ["Orange-red scabby or velvety patches on leaves and stems", "Affected shoots die back"],
        "Poor drainage, low potassium and humid weather.", wp(22, 32, 85),
        ["Improve drainage and nutrition, especially potassium"], [],
        ["Copper oxychloride 50 WP @ 2.5 g/L"], ["Adequate potassium"], ["Keep bushes vigorous"]),

    # ------------------------------------------------------------------ papaya
    "papaya___leaf_curl": D(
        "Papaya Leaf Curl", "Viral (whitefly-borne)", "Papaya leaf curl virus", "Severe",
        "A whitefly-spread virus that curls the leaves into cups and stunts the plant. There is no cure.",
        ["Leaves curl downward and inward into cups, with thickened veins", "Stunted plants with few fruits"],
        "High whitefly numbers in warm weather.", None,
        ["Uproot and destroy infected plants", "Raise seedlings under insect net"],
        ["Yellow sticky traps and neem oil"],
        ["No cure; control whitefly with a recommended insecticide"],
        ["Balanced fertilizer"], ["Don't grow papaya next to tomato or chilli with leaf curl"]),
    "papaya___mealybug": D(
        "Papaya Mealybug", "Pest", "Paracoccus marginatus", "High",
        "White, cottony insects that cover leaves, stems and fruit and cause sooty mould.",
        ["White cottony masses on leaves, stems and fruit", "Yellow, crinkled leaves and black sooty mould"],
        "Warm, dry weather.", None,
        ["Prune and burn heavily infested parts"],
        ["Neem oil 1500 ppm @ 5 ml/L with a little soap",
         "Release of the parasitoid Acerophagus papayae where available"],
        ["Spray a recommended insecticide on heavy infestations"],
        ["Balanced fertilizer"], ["Check new plants before planting"]),
    "papaya___mites": D(
        "Papaya Mites", "Pest", "Red spider mite", "Moderate",
        "Tiny mites that speckle and bronze the leaves in hot, dry weather.",
        ["Fine yellow speckling and bronzing on leaves", "Fine webbing under the leaves"],
        "Hot, dry weather.", wp(28, 38, rh_max=55),
        ["Spray water under the leaves"], ["Wettable sulphur 80 WP @ 2 g/L"],
        ["A recommended miticide such as spiromesifen, as per label"],
        ["Keep plants well watered"], ["Check leaf undersides weekly in summer"]),
    "papaya___mosaic": D(
        "Papaya Mosaic", "Viral (aphid-borne)", "Papaya mosaic and related viruses", "High",
        "A virus that mottles and distorts young leaves. There is no cure.",
        ["Light and dark green mosaic pattern on young leaves", "Small, distorted leaves"],
        "Spread by aphids.", None,
        ["Remove infected plants", "Grow maize as a border crop to intercept aphids"], [],
        ["No cure; manage aphids"], ["Balanced fertilizer"], ["Use healthy seedlings"]),
    "papaya___ring_spot": D(
        "Papaya Ring Spot", "Viral (aphid-borne)", "Papaya ringspot virus", "Severe",
        "The most destructive papaya disease. Leaves become thin and mottled, and fruit shows dark rings.",
        ["Mottling and narrow, shoestring-like leaves", "Dark green rings on the fruit"],
        "Spread by aphids.", None,
        ["Remove infected plants early", "Grow maize as a border crop"], [],
        ["No cure; manage aphids"], ["Balanced fertilizer"], ["Use healthy seedlings and isolate new plantings"]),

    # ------------------------------------------------------------------ masoor (lentil)
    "masoor___ascochyta_blight": D(
        "Lentil Ascochyta Blight", "Fungal", "Ascochyta lentis", "High",
        "Tan spots on leaves, stems and pods that can break stems in wet weather.",
        ["Tan spots with dark borders on leaves, stems and pods", "Leaves drop; stems break in severe cases"],
        "Cool, wet weather.", wp(15, 25, 85, True),
        ["Remove crop debris"], [],
        ["Mancozeb 75 WP @ 2.5 g/L or chlorothalonil 75 WP @ 2 g/L"],
        ["Balanced fertilizer"], ["Use healthy seed", "Rotate crops"]),
    "masoor___rust": D(
        "Lentil Rust", "Fungal", "Uromyces viciae-fabae", "High",
        "Pustules on leaves and stems that dry plants early and shrivel the seed.",
        ["Yellowish, then brown-black pustules on leaves and stems", "Plants dry early"],
        "Mild, humid weather.", wp(17, 25, 80),
        ["Remove volunteer plants"], [],
        ["Mancozeb 75 WP @ 2.5 g/L or hexaconazole 5 EC @ 1 ml/L at first appearance"],
        ["Balanced fertilizer"], ["Grow resistant varieties", "Sow on time"]),
    "masoor___powdery_mildew": D(
        "Lentil Powdery Mildew", "Fungal", "Erysiphe species", "Moderate",
        "White powder on leaves and stems late in the season.",
        ["White powder on leaves and stems"], "Dry days with cool nights.", wp(15, 28, 50),
        ["Remove the worst affected plants"], ["Wettable sulphur 80 WP @ 2 g/L"],
        ["Hexaconazole 5 EC @ 1 ml/L"], ["Balanced fertilizer"], ["Sow on time"]),

    # ------------------------------------------------------------------ urad (black gram)
    "urad___anthracnose": D(
        "Black Gram Anthracnose", "Fungal", "Colletotrichum lindemuthianum", "Moderate",
        "Dark sunken spots on leaves, stems and pods, worse in wet weather.",
        ["Dark brown sunken spots with red-brown edges on leaves, stems and pods"],
        "Warm, wet weather.", wp(22, 30, 85, True),
        ["Remove crop debris"], [],
        ["Carbendazim 50 WP @ 1 g/L or mancozeb 75 WP @ 2.5 g/L"],
        ["Balanced fertilizer"], ["Use treated seed", "Rotate crops"]),
    "urad___leaf_crinkle": D(
        "Black Gram Leaf Crinkle", "Viral", "Urdbean leaf crinkle virus", "High",
        "A seed-borne virus that makes leaves large and crinkled and causes flower drop.",
        ["Leaves become large, crinkled and puckered", "Flowers drop; few pods"],
        "Infected seed and insects.", None,
        ["Pull out infected plants early"], [], ["No cure"],
        ["Balanced fertilizer"], ["Use healthy seed from disease-free fields"]),
    "urad___powdery_mildew": D(
        "Black Gram Powdery Mildew", "Fungal", "Erysiphe polygoni", "Moderate",
        "White powder on leaves that dries them early.",
        ["White powder on the upper leaf surface"], "Dry days with cool nights.", wp(18, 30, 50),
        ["Remove the worst affected plants"], ["Wettable sulphur 80 WP @ 2 g/L"],
        ["Hexaconazole 5 EC @ 1 ml/L"], ["Balanced fertilizer"], ["Grow tolerant varieties"]),
    "urad___yellow_mosaic": D(
        "Black Gram Yellow Mosaic", "Viral (whitefly-borne)", "Mungbean yellow mosaic India virus", "Severe",
        "The most serious disease of urad and moong in India. Bright yellow patches and very poor pod set.",
        ["Bright yellow and green patches on leaves", "Small, few pods"],
        "High whitefly numbers.", None,
        ["Pull out infected plants early", "Use yellow sticky traps"], ["Neem oil against whitefly"],
        ["No cure; control whitefly with a recommended insecticide"],
        ["Balanced fertilizer"], ["Grow resistant varieties"]),

    # ------------------------------------------------------------------ malabar spinach (poi)
    "malabar_spinach___anthracnose": D(
        "Malabar Spinach Anthracnose", "Fungal", "Colletotrichum species", "Moderate",
        "Water-soaked spots that turn tan with dark specks and spoil the leaves for sale.",
        ["Small water-soaked spots that turn tan with dark specks"], "Wet, warm weather.", wp(18, 28, 85, True),
        ["Remove infected leaves", "Avoid overhead watering"], [], ["Mancozeb 75 WP @ 2.5 g/L"],
        ["Balanced fertilizer"], ["Rotate crops"]),
    "malabar_spinach___bacterial_spot": D(
        "Malabar Spinach Bacterial Spot", "Bacterial", "Pseudomonas and Xanthomonas species", "Moderate",
        "Small dark angular spots that spread with splashing water.",
        ["Small dark, water-soaked angular spots"], "Wet leaves and splashing water.", wp(15, 28, 85, True),
        ["Avoid overhead watering", "Rotate crops"], [], ["Copper oxychloride 50 WP @ 2 g/L", NO_ANTIBIOTICS],
        ["Balanced fertilizer"], ["Use clean seed"]),
    "malabar_spinach___downy_mildew": D(
        "Malabar Spinach Downy Mildew", "Oomycete", "Downy mildew pathogens (oomycetes)", "High",
        "Yellow patches on top of the leaf with grey fuzz underneath, in damp, humid weather.",
        ["Yellow patches on top of leaves with grey fuzz underneath"], "Damp, humid weather with wet leaves.",
        wp(18, 28, 85),
        ["Space plants for air flow", "Avoid wet leaves"], [], ["Metalaxyl + mancozeb, as per label"],
        ["Balanced fertilizer"], ["Grow resistant varieties"]),
    "malabar_spinach___pest_damage": D(
        "Malabar Spinach Pest Damage", "Pest", "Leaf-eating caterpillars, beetles and leaf miners", "Low",
        "Holes, tunnels or chewed edges from leaf-eating insects.",
        ["Holes, tunnels or chewed edges on leaves"], "Warm weather.", None,
        ["Hand-pick caterpillars", "Remove leaves with miner tunnels"], ["Neem oil 1500 ppm @ 3-5 ml/L"],
        ["Spinosad or another recommended insecticide only if damage is heavy; observe the waiting period before harvest"],
        ["Balanced fertilizer"], ["Use insect net on small plots"]),

    # ------------------------------------------------------------------ radish
    "radish___black_leaf_spot": D(
        "Radish Black Leaf Spot", "Fungal", "Alternaria species", "Moderate",
        "Dark spots with rings that dry the leaves.",
        ["Dark brown to black round spots with rings on leaves"], "Warm, humid weather.", wp(18, 28, 80),
        ["Remove crop debris"], [], ["Mancozeb 75 WP @ 2.5 g/L"],
        ["Balanced fertilizer"], ["Rotate crops", "Use healthy seed"]),
    "radish___downy_mildew": D(
        "Radish Downy Mildew", "Oomycete", "Hyaloperonospora parasitica", "Moderate",
        "Yellow patches above and white-grey growth below the leaf in cool, damp weather.",
        ["Yellow patches on top of leaves, white-grey growth underneath"], "Cool, damp weather.", wp(10, 22, 85),
        ["Space plants for air flow"], [], ["Metalaxyl + mancozeb, as per label"],
        ["Balanced fertilizer"], ["Rotate crops"]),
    "radish___mosaic": D(
        "Radish Mosaic", "Viral (aphid-borne)", "Turnip mosaic virus", "Moderate",
        "Mottled, distorted leaves from an aphid-spread virus. There is no cure.",
        ["Mottled light and dark green leaves", "Distorted leaves"], "Spread by aphids.", None,
        ["Remove infected plants", "Control weeds"], [], ["No cure; control aphids"],
        ["Balanced fertilizer"], ["Use insect net on seedlings"]),
    "radish___flea_beetle": D(
        "Radish Flea Beetle", "Pest", "Flea beetles", "Moderate",
        "Small jumping beetles that riddle young leaves with tiny holes.",
        ["Many small round shot holes in leaves"], "Warm, dry weather.", None,
        ["Keep seedlings well watered"], ["Neem oil", "Insect net on young plants"],
        ["A recommended insecticide only if seedlings are badly damaged"],
        ["Balanced fertilizer"], ["Rotate crops"]),
}


def healthy_entry(crop_key, crops):
    c = crops[crop_key]
    problems = ", ".join(p["name"].lower() for p in c.get("problems", [])[:3])
    watch = f"Keep watching for {problems}." if problems else "Keep inspecting the plants regularly."
    return {
        "name": f"Healthy {c['name']}", "type": "Healthy", "pathogen": "", "impact": "None",
        "summary": f"No disease is visible on this {c['name'].lower()} leaf. {watch}",
        "symptoms": [], "conditions": "", "weather_profile": None,
        "treatment": {"cultural": [], "organic": [], "chemical": []},
        "fertilizer": [f"General reference: {c['npk']}.", c["tip"]],
        "prevention": [f"Inspect plants every week, especially in humid weather.",
                       "Keep the field or pot clean of dead leaves and weeds."],
    }


def main():
    classes_path = os.path.join(ROOT, "models", "extra-crops", "classes.json")
    with open(os.path.join(ROOT, "agri", "data", "crops.json"), encoding="utf-8") as fh:
        crops = json.load(fh)["crops"]
    if os.path.exists(classes_path):
        with open(classes_path, encoding="utf-8") as fh:
            classes = json.load(fh)
    else:
        classes = sorted(set(ENTRIES) | {f"{k.split('___')[0]}___healthy" for k in ENTRIES})
    out = []
    for i, key in enumerate(classes):
        crop, cls = key.split("___")
        entry = healthy_entry(crop, crops) if cls == "healthy" else ENTRIES[key]
        out.append({"id": 1000 + i, "key": key, "model_label": key, "pv_folder": key, "crop": crop,
                    "healthy": cls == "healthy", "model": "extra", **entry})
    missing = [k for k in classes if k not in ENTRIES and not k.endswith("___healthy")]
    if missing:
        raise SystemExit(f"No advice written for: {missing}")
    path = os.path.join(ROOT, "agri", "data", "diseases_extra.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"wrote {len(out)} entries to {path}")


if __name__ == "__main__":
    main()
