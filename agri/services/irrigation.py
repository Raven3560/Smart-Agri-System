"""Smart irrigation guidance module.

Implements a daily root-zone soil water balance based on FAO Irrigation and
Drainage Paper 56 (Allen et al., 1998), using no physical sensors:

    ETc  = Kc x ET0                       crop water use (mm/day)
    TAW  = AWC x Zr                       total available water in the root zone (mm)
    RAW  = p x TAW                        readily available water (mm)
    Dr_i = Dr_(i-1) + Ks x ETc_i - Peff_i  root-zone depletion (mm), 0 <= Dr <= TAW

* ET0 (reference evapotranspiration) and rainfall come from the weather API.
* Kc depends on crop and growth stage, Zr on crop and stage, AWC on soil type.
* The field is assumed to be at field capacity (Dr = 0) right after the last
  irrigation; the balance is run forward through the past days and the forecast.
* Irrigation is due when depletion reaches RAW. If useful rain is likely in the
  next two days, irrigation is postponed to save water and pumping energy.

The output also converts the water requirement into pump run-time, electricity,
cost and CO2 so the energy impact (SDG 7) is visible to the farmer.
"""
import datetime as dt

from . import knowledge as kb

ACRE_M2 = 4046.86
FLOOD_EFFICIENCY = 0.50          # conventional flood/basin irrigation baseline
PUMP_WIRE_TO_WATER = 0.40        # typical overall efficiency of Indian farm pump-sets
GRID_CO2_KG_PER_KWH = 0.71       # Indian grid emission factor (CEA CO2 baseline database)
RAIN_PROB_LIKELY = 50            # % probability for forecast rain to be counted
RAIN_LOOKAHEAD_DAYS = 2
MAX_HISTORY_DAYS = 45


def effective_rain(rain_mm):
    """Simplified effective rainfall.

    Rain below 2 mm/day is lost to interception and evaporation; 80% of the
    remainder is assumed to reach the root zone (the rest runs off or
    percolates below it).
    """
    return round(0.8 * max(0.0, (rain_mm or 0.0) - 2.0), 2)


def crop_coefficient(crop, stage):
    ini, mid, end = crop["kc"]
    return {"initial": ini, "development": round((ini + mid) / 2, 3), "mid": mid, "late": end}[stage]


def root_depth(crop, stage):
    if crop.get("perennial"):
        return crop["root_m"]
    factor = kb.stages()[stage]["root_factor"]
    return round(max(min(0.2, crop["root_m"]), crop["root_m"] * factor), 3)


def depletion_fraction(p_table, etc):
    """FAO-56 adjustment of p for the evaporative demand of the day."""
    return min(0.8, max(0.1, p_table + 0.04 * (5.0 - etc)))


def stress_coefficient(dr, taw, raw):
    if dr <= raw or taw <= raw:
        return 1.0
    return max(0.0, (taw - dr) / (taw - raw))


def pump_flow_lps(hp, head_m):
    """Approximate pump discharge (litres/second) from pump power and total head."""
    hp = max(0.5, float(hp or 5))
    head_m = max(3.0, float(head_m or 20))
    return hp * 746 * PUMP_WIRE_TO_WATER / (9.81 * head_m)


def energy_for(volume_l, hp, head_m, tariff):
    lps = pump_flow_lps(hp, head_m)
    hours = volume_l / (lps * 3600) if lps else 0
    kwh = float(hp or 5) * 0.746 * hours
    return {
        "flow_lps": round(lps, 2),
        "flow_m3h": round(lps * 3.6, 1),
        "hours": round(hours, 2),
        "kwh": round(kwh, 1),
        "cost": round(kwh * float(tariff or 0), 0),
        "co2_kg": round(kwh * GRID_CO2_KG_PER_KWH, 1),
    }


def _date(value):
    if isinstance(value, dt.date):
        return value
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def plan_irrigation(*, crop_key, stage, soil_key, method_key, area_acres, last_irrigation, weather,
                    pump_hp=5.0, pump_head_m=20.0, tariff=6.0, today=None):
    crops, soils, methods = kb.crops(), kb.soils(), kb.methods()
    if crop_key not in crops:
        raise ValueError(f"Unknown crop: {crop_key}")
    if stage not in kb.stages():
        raise ValueError(f"Unknown growth stage: {stage}")
    if soil_key not in soils:
        raise ValueError(f"Unknown soil type: {soil_key}")
    if method_key not in methods:
        raise ValueError(f"Unknown irrigation method: {method_key}")

    crop, soil, method = crops[crop_key], soils[soil_key], methods[method_key]
    if crop.get("kind") == "houseplant":
        return plan_houseplant(crop_key=crop_key, crop=crop, stage=stage, last_irrigation=last_irrigation,
                               weather=weather, today=today)
    area_acres = max(0.01, float(area_acres or 1))
    area_m2 = area_acres * ACRE_M2
    efficiency = method["efficiency"]
    today = _date(today) or _date(weather.get("today")) or dt.date.today()

    kc = crop_coefficient(crop, stage)
    zr = root_depth(crop, stage)
    taw = round(soil["awc"] * zr, 1)
    assumptions = []

    forecast = weather["forecast"][:7]
    if not forecast:
        raise ValueError("Weather forecast is empty")
    etc_today = kc * forecast[0]["et0"]
    p = depletion_fraction(crop["p"], etc_today)
    raw = round(p * taw, 1)

    # ---- 1. Water balance from the last irrigation up to this morning --------
    last = _date(last_irrigation)
    history_rows = []
    if last is None:
        depletion = round(0.5 * raw, 1)
        days_since = None
        assumptions.append("Last irrigation date not given: the root zone is assumed to be half-way to the "
                           "irrigation threshold.")
    else:
        if last > today:
            last = today
        days_since = (today - last).days
        depletion = 0.0
        start = max(last, today - dt.timedelta(days=MAX_HISTORY_DAYS))
        if start > last:
            assumptions.append(f"Only the last {MAX_HISTORY_DAYS} days of weather are used for the water balance.")
        past_by_date = {d["date"]: d for d in weather.get("past", [])}
        known = [d["et0"] for d in weather.get("past", [])] or [f["et0"] for f in forecast]
        mean_et0 = sum(known) / len(known)
        missing = 0
        day = start + dt.timedelta(days=1)
        while day < today:
            rec = past_by_date.get(day.isoformat())
            if rec is None:
                missing += 1
                et0, rain = mean_et0, 0.0
            else:
                et0, rain = rec["et0"], rec["rain"]
            etc = kc * et0
            ks = stress_coefficient(depletion, taw, raw)
            peff = effective_rain(rain)
            depletion = min(taw, max(0.0, depletion + ks * etc - peff))
            history_rows.append({"date": day.isoformat(), "et0": round(et0, 2), "etc": round(ks * etc, 2),
                                 "rain": rain, "peff": peff, "depletion": round(depletion, 1)})
            day += dt.timedelta(days=1)
        if missing:
            assumptions.append(f"Weather history was missing for {missing} day(s); average ET0 and no rain were assumed.")
        depletion = round(depletion, 1)

    if crop_key == "rice":
        assumptions.append("For puddled paddy, percolation and seepage losses (typically 2-6 mm/day) are not "
                           "included. Follow Alternate Wetting and Drying (AWD) to save water.")

    current_depletion = depletion
    rain_saving_events = []

    # ---- 2. Project the balance through the 7-day forecast ------------------
    schedule = []
    dr = depletion
    for i, d in enumerate(forecast):
        etc = kc * d["et0"]
        p_day = depletion_fraction(crop["p"], etc)
        raw_day = p_day * taw
        likely = d["rain_prob"] >= RAIN_PROB_LIKELY or weather.get("source") != "live"
        peff = effective_rain(d["rain"]) if likely else 0.0
        morning = dr
        projected_end = min(taw, max(0.0, morning + etc - peff))
        action, net = None, 0.0

        if projected_end >= raw_day:
            # Would useful rain in the next days cover most of the need?
            ahead = forecast[i + 1:i + 1 + RAIN_LOOKAHEAD_DAYS]
            rain_ahead = sum(effective_rain(a["rain"]) for a in ahead if a["rain_prob"] >= 60)
            severe = morning >= 0.85 * taw
            if rain_ahead >= 0.5 * projected_end and not severe:
                action = "skip_rain"
                rain_saving_events.append({"date": d["date"], "need_mm": round(projected_end, 1),
                                           "rain_mm": round(rain_ahead, 1)})
            else:
                action = "irrigate"
                net = round(projected_end, 1)

        if action == "irrigate":
            dr = 0.0
        else:
            ks = stress_coefficient(morning, taw, raw_day)
            dr = min(taw, max(0.0, morning + ks * etc - peff))

        schedule.append({
            "date": d["date"], "label": d["label"], "icon": d["icon"],
            "et0": d["et0"], "kc": round(kc, 2), "etc": round(etc, 2),
            "rain": d["rain"], "rain_prob": d["rain_prob"], "peff": round(peff, 1),
            "depletion_morning": round(morning, 1), "depletion_end": round(dr, 1),
            "depletion_pct": round(100 * morning / taw, 0) if taw else 0,
            "raw_pct": round(100 * raw_day / taw, 0) if taw else 0,
            "action": action, "net_mm": net, "gross_mm": round(net / efficiency, 1) if net else 0.0,
        })

    # ---- 3. Decision for the farmer ----------------------------------------
    first_event = next((s for s in schedule if s["action"] == "irrigate"), None)
    today_row = schedule[0]
    if today_row["action"] == "irrigate":
        status = "irrigate_now"
    elif today_row["action"] == "skip_rain":
        status = "delay_rain"
    elif first_event:
        status = "upcoming"
    else:
        status = "not_needed"

    target = today_row if status in ("irrigate_now", "delay_rain") else first_event
    if status == "delay_rain":
        net_mm = rain_saving_events[0]["need_mm"]
    else:
        net_mm = target["net_mm"] if target else 0.0
    gross_mm = round(net_mm / efficiency, 1) if net_mm else 0.0
    volume_l = round(gross_mm * area_m2)
    flood_volume_l = round(net_mm / FLOOD_EFFICIENCY * area_m2) if net_mm else 0
    energy = energy_for(volume_l, pump_hp, pump_head_m, tariff)
    flood_energy = energy_for(flood_volume_l, pump_hp, pump_head_m, tariff)

    days_until = None
    next_date = None
    if target:
        next_date = target["date"]
        days_until = (_date(target["date"]) - today).days

    week_gross_mm = round(sum(s["gross_mm"] for s in schedule), 1)
    week_volume_l = round(week_gross_mm * area_m2)
    week_etc = round(sum(s["etc"] for s in schedule), 1)
    week_rain = round(sum(s["peff"] for s in schedule), 1)

    saved_by_rain_l = 0
    if rain_saving_events:
        saved_by_rain_l = round(rain_saving_events[0]["need_mm"] / efficiency * area_m2)
    savings = {
        "vs_flood_l": max(0, flood_volume_l - volume_l),
        "vs_flood_kwh": round(max(0.0, flood_energy["kwh"] - energy["kwh"]), 1),
        "vs_flood_cost": max(0, flood_energy["cost"] - energy["cost"]),
        "rain_skip_l": saved_by_rain_l,
        "rain_skip_kwh": energy_for(saved_by_rain_l, pump_hp, pump_head_m, tariff)["kwh"] if saved_by_rain_l else 0,
    }
    savings["total_l"] = savings["vs_flood_l"] + savings["rain_skip_l"]
    savings["total_kwh"] = round(savings["vs_flood_kwh"] + savings["rain_skip_kwh"], 1)
    savings["total_co2_kg"] = round(savings["total_kwh"] * GRID_CO2_KG_PER_KWH, 1)

    radiation = [d["radiation"] for d in forecast if d.get("radiation")]
    solar_kwh_m2 = round(sum(radiation) / len(radiation) / 3.6, 1) if radiation else None

    result = {
        "status": status,
        "headline": _headline(status, days_until, next_date, net_mm, rain_saving_events),
        "inputs": {
            "crop": crop_key, "crop_name": crop["name"], "stage": stage,
            "stage_name": kb.stages()[stage]["label"], "soil": soil_key, "soil_name": soil["name"],
            "method": method_key, "method_name": method["label"], "efficiency": efficiency,
            "area_acres": round(area_acres, 2), "last_irrigation": last.isoformat() if last else None,
            "days_since": days_since, "pump_hp": float(pump_hp or 5), "pump_head_m": float(pump_head_m or 20),
            "tariff": float(tariff or 0),
        },
        "soil_water": {
            "kc": round(kc, 2), "root_depth_m": zr, "awc_mm_per_m": soil["awc"], "taw_mm": taw,
            "p": round(p, 2), "raw_mm": raw, "depletion_mm": current_depletion,
            "depletion_pct": round(100 * current_depletion / taw) if taw else 0,
            "moisture_pct": max(0, round(100 - 100 * current_depletion / taw)) if taw else 0,
            "raw_pct": round(100 * raw / taw) if taw else 0,
            "etc_today": round(etc_today, 2),
        },
        "next": {"date": next_date, "days_until": days_until, "net_mm": net_mm, "gross_mm": gross_mm,
                 "volume_l": volume_l, "flood_volume_l": flood_volume_l, **energy},
        "week": {"etc_mm": week_etc, "effective_rain_mm": week_rain, "gross_mm": week_gross_mm,
                 "volume_l": week_volume_l, "events": sum(1 for s in schedule if s["action"] == "irrigate")},
        "savings": savings,
        "solar": _solar_note(solar_kwh_m2, energy["kwh"]),
        "schedule": schedule,
        "history": history_rows[-14:],
        "tips": _tips(crop, soil, method_key, forecast),
        "assumptions": assumptions + [
            f"Crop coefficient Kc = {kc:.2f} and root depth {zr} m for the {kb.stages()[stage]['label'].lower()} stage (FAO-56).",
            f"Application efficiency of {method['label'].lower()} irrigation taken as {int(efficiency * 100)}%.",
            "Forecast rain is counted only when its probability is 50% or more.",
            f"Pump discharge estimated from {float(pump_hp or 5):g} HP at {float(pump_head_m or 20):g} m head "
            f"with {int(PUMP_WIRE_TO_WATER * 100)}% overall pump-set efficiency.",
        ],
        "weather_source": weather.get("source", "live"),
    }
    return result


def _headline(status, days_until, next_date, net_mm, rain_events):
    if status == "irrigate_now":
        return {"title": "Irrigate today", "level": "critical",
                "text": f"The root zone has used up its readily available water. Apply about {net_mm} mm (net) today, "
                        "preferably in the early morning or evening."}
    if status == "delay_rain":
        ev = rain_events[0]
        return {"title": "Hold irrigation: rain expected", "level": "info",
                "text": f"The crop needs about {ev['need_mm']} mm, but about {ev['rain_mm']} mm of useful rain is "
                        "likely in the next 2 days. Wait and re-check after the rain to save water and electricity."}
    if status == "upcoming":
        when = "tomorrow" if days_until == 1 else f"in {days_until} days"
        pretty = dt.date.fromisoformat(next_date).strftime("%a %d %b")
        return {"title": f"Next irrigation {when}", "level": "warning" if days_until <= 2 else "good",
                "text": f"Soil moisture is adequate today. Plan to apply about {net_mm} mm (net) on {pretty}."}
    return {"title": "No irrigation needed this week", "level": "good",
            "text": "Soil moisture and expected rain are enough for the crop over the next 7 days."}


def _solar_note(kwh_m2, kwh_next):
    if kwh_m2 is None:
        return None
    if kwh_m2 >= 4.5:
        rating, text = "Good", ("Sunlight here is strong enough for a solar water pump. Solar pumps cut diesel and grid "
                                "electricity use; check the PM-KUSUM scheme for subsidies.")
    elif kwh_m2 >= 3.5:
        rating, text = "Moderate", ("Solar pumping is workable here, but output will be lower on cloudy days. "
                                    "Size the panels with some margin.")
    else:
        rating, text = "Low (this week)", ("Cloudy conditions this week lower solar output. Annual averages in most of "
                                           "India are still suitable for solar pumps.")
    return {"kwh_m2_day": kwh_m2, "rating": rating, "text": text, "next_irrigation_kwh": kwh_next}


def _tips(crop, soil, method_key, forecast):
    tips = [crop["tip"], soil["tip"]]
    if method_key in ("flood", "furrow"):
        tips.append("Switching to drip irrigation can cut water use by 30-50% and lower pumping energy; "
                    "PMKSY 'Per Drop More Crop' offers subsidies for drip and sprinkler systems.")
    if method_key == "sprinkler" and any(d["wind"] >= 15 for d in forecast[:2]):
        tips.append("Wind is strong in the next 2 days. Run sprinklers in the calm early morning to reduce drift losses.")
    tips.append("Irrigate in the early morning or evening to reduce evaporation losses.")
    return tips


def plan_houseplant(*, crop_key, crop, stage, last_irrigation, weather, today=None):
    """Watering plan for a pot plant (money plant, tulsi).

    A pot holds very little water and sits in shade or indoors, so a field
    water balance in mm per acre makes no sense. Instead the watering interval
    comes from the plant's care profile and the next few days' weather:
    hotter weather shortens it, humid weather lengthens it a little.
    """
    care = crop["care"]
    forecast = weather["forecast"][:7]
    today = _date(today) or _date(weather.get("today")) or dt.date.today()
    window = forecast[:3] or forecast
    tmax = sum(d["tmax"] for d in window) / len(window)
    rh = sum(d["rh"] for d in window) / len(window)
    if tmax >= 32:
        season, interval = "hot", care["water_days"]["hot"]
    elif tmax >= 22:
        season, interval = "warm", care["water_days"]["warm"]
    else:
        season, interval = "cool", care["water_days"]["cool"]
    if rh >= 75 and interval >= 2:
        interval += 1

    last = _date(last_irrigation)
    if last and last > today:
        last = today
    days_since = (today - last).days if last else None

    if last is None:
        status, next_date = "irrigate_now", today
        headline = {"title": "Check the soil today", "level": "warning",
                    "text": "We don't know when it was last watered. Push a finger 2-3 cm into the soil: water if it "
                            f"feels dry, then water about every {interval} days."}
    else:
        next_date = last + dt.timedelta(days=interval)
        if next_date <= today:
            status = "irrigate_now"
            headline = {"title": "Water today", "level": "critical",
                        "text": f"It has been {days_since} days. Check the top 2-3 cm of soil and water if it feels "
                                "dry, until water drains from the bottom."}
        else:
            status = "upcoming"
            gap = (next_date - today).days
            when = "tomorrow" if gap == 1 else f"in {gap} days"
            plural = "s" if days_since != 1 else ""
            headline = {"title": f"Next watering {when}", "level": "warning" if gap <= 1 else "good",
                        "text": f"Watered {days_since} day{plural} ago. In this {season} weather, water about every "
                                f"{interval} days, and only when the topsoil is dry."}

    schedule = []
    due = next_date
    for d in forecast:
        day = dt.date.fromisoformat(d["date"])
        action = None
        if due is not None and day >= due:
            action = "water"
            due = day + dt.timedelta(days=interval)
        schedule.append({"date": d["date"], "label": d["label"], "icon": d["icon"], "tmax": d["tmax"],
                         "rh": d["rh"], "action": action})

    dryness = 0 if days_since is None else min(100, round(100 * days_since / interval))
    tips = [crop["tip"], care["watering"], care["light"]]
    if care.get("water_grown"):
        tips.append(care["water_grown"])
    return {
        "kind": "houseplant",
        "status": status,
        "headline": headline,
        "inputs": {"crop": crop_key, "crop_name": crop["name"], "stage": stage, "stage_name": "Pot plant",
                   "last_irrigation": last.isoformat() if last else None, "days_since": days_since},
        "care": {"interval_days": interval, "season": season, "tmax_avg": round(tmax, 1), "rh_avg": round(rh),
                 "light": care["light"], "watering": care["watering"], "water_grown": care.get("water_grown", ""),
                 "fertilizer": care["fertilizer"], "dryness_pct": dryness},
        "next": {"date": next_date.isoformat() if next_date else None,
                 "days_until": (next_date - today).days if next_date else None},
        "schedule": schedule,
        "tips": tips,
        "savings": {"total_l": 0, "total_kwh": 0, "total_co2_kg": 0},
        "assumptions": [
            f"Watering interval of {interval} days for {season} weather (average maximum {tmax:.0f} °C, "
            f"humidity {rh:.0f}%).",
            "Indoor and shaded pots dry more slowly than the outdoor forecast suggests, so always check the soil first.",
        ],
        "weather_source": weather.get("source", "live"),
    }
