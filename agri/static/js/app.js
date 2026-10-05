/* SmartAgri front-end behaviour (no build step, no framework). */
(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  /* ---------------- theme ---------------- */
  function effectiveTheme() {
    const set = document.documentElement.getAttribute("data-theme");
    if (set) return set;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  $$("[data-theme-toggle]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const next = effectiveTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) { /* storage unavailable */ }
      renderCharts();
    })
  );

  /* ---------------- mobile nav ---------------- */
  const navToggle = $("[data-nav-toggle]");
  const navLinks = $("#nav-links");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => {
      const open = navLinks.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", String(open));
    });
  }

  /* ---------------- show / hide password ---------------- */
  $$("[data-pw-toggle]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.dataset.pwToggle);
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.textContent = show ? "Hide" : "Show";
    })
  );

  /* ---------------- confirm + busy overlay ---------------- */
  $$("form[data-confirm]").forEach((f) =>
    f.addEventListener("submit", (e) => { if (!confirm(f.dataset.confirm)) e.preventDefault(); })
  );

  const busy = $("#busy");
  function showBusy(title, steps) {
    if (!busy) return;
    $("#busy-title").textContent = title || "Working...";
    busy.classList.add("open");
    const stepEl = $("#busy-step");
    let i = 0;
    stepEl.textContent = steps[0] || "";
    if (steps.length > 1) {
      setInterval(() => { i = Math.min(i + 1, steps.length - 1); stepEl.textContent = steps[i]; }, 1100);
    }
  }
  $$("form[data-busy]").forEach((f) =>
    f.addEventListener("submit", (e) => {
      if (f.id === "analyze-form") {
        const input = $("[data-file-input]", f);
        if (input && !input.files.length) {
          e.preventDefault();
          alert("Add a photo of the leaf first.");
          return;
        }
      }
      const steps = f.id === "analyze-form"
        ? ["Checking the photo is sharp enough...", "Looking at the leaf...", "Getting the weather forecast...", "Working out the soil water...", "Putting your plan together..."]
        : ["Getting the weather forecast...", "Working out the soil water...", "Adding up water and electricity..."];
      showBusy(f.dataset.busy, steps);
      $$("button[type=submit]", f).forEach((b) => (b.disabled = true));
    })
  );
  window.addEventListener("pageshow", () => {
    if (busy) busy.classList.remove("open");
    $$("button[type=submit]").forEach((b) => (b.disabled = false));
  });

  /* ---------------- image upload, camera and samples ---------------- */
  const dz = $("[data-dropzone]");
  const fileInput = $("[data-file-input]");

  function setFile(file) {
    if (!fileInput || !file) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    showPreview(file);
  }

  function showPreview(file) {
    if (!dz || !file) return;
    const img = $("[data-preview]", dz);
    const reader = new FileReader();
    reader.onload = () => { img.src = reader.result; dz.classList.add("has-image"); };
    reader.readAsDataURL(file);
    $("[data-file-name]", dz).textContent = file.name + " · " + Math.round(file.size / 1024) + " KB · tap to change";
  }

  if (dz && fileInput) {
    fileInput.addEventListener("change", () => { if (fileInput.files[0]) showPreview(fileInput.files[0]); });
    ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
    ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, () => dz.classList.remove("drag")));
    dz.addEventListener("drop", (e) => {
      e.preventDefault();
      const f = e.dataTransfer.files && e.dataTransfer.files[0];
      if (f && f.type.startsWith("image/")) setFile(f);
    });
    const pick = $("[data-pick]");
    if (pick) pick.addEventListener("click", () => fileInput.click());
  }

  $$("[data-sample]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      try {
        const res = await fetch(btn.dataset.sample);
        const blob = await res.blob();
        const name = btn.dataset.sample.split("/").pop();
        setFile(new File([blob], name, { type: blob.type || "image/jpeg" }));
        const crop = $("#crop");
        if (crop && btn.dataset.sampleCrop) { crop.value = btn.dataset.sampleCrop; crop.dispatchEvent(new Event("change")); }
        dz.scrollIntoView({ behavior: "smooth", block: "center" });
      } catch (err) {
        alert("Could not load the sample image.");
      }
    })
  );

  const captureInput = $("[data-capture-input]");
  if (captureInput) captureInput.addEventListener("change", () => { if (captureInput.files[0]) setFile(captureInput.files[0]); });

  const modal = $("#camera-modal");
  let stream = null;
  function closeCamera() {
    if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
    if (modal) modal.classList.remove("open");
  }
  const camBtn = $("[data-camera]");
  if (camBtn) {
    camBtn.addEventListener("click", async () => {
      const canUseCamera = navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.isSecureContext;
      if (!canUseCamera) { captureInput.click(); return; }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width: { ideal: 1280 } }, audio: false });
        $("[data-camera-video]").srcObject = stream;
        modal.classList.add("open");
      } catch (err) {
        captureInput.click();
      }
    });
    $$("[data-camera-close]").forEach((b) => b.addEventListener("click", closeCamera));
    $("[data-camera-snap]").addEventListener("click", () => {
      const video = $("[data-camera-video]");
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      canvas.getContext("2d").drawImage(video, 0, 0);
      canvas.toBlob((blob) => {
        setFile(new File([blob], "camera-" + Date.now() + ".jpg", { type: "image/jpeg" }));
        closeCamera();
      }, "image/jpeg", 0.92);
    });
  }

  /* crop support note */
  const form = $("#analyze-form");
  if (form) {
    const supported = JSON.parse(form.dataset.modelCrops || "[]");
    const crop = $("#crop", form);
    const note = $("[data-support-note]", form);
    const update = () => {
      const ok = supported.includes(crop.value);
      note.hidden = ok;
      if (!ok) $("span", note).textContent = "We can't check this crop for disease yet, but you'll still get irrigation, weather and fertilizer advice.";
    };
    crop.addEventListener("change", update);
    update();
  }

  /* ---------------- irrigation form: hide field-only inputs for pot plants ---------------- */
  const potForm = document.querySelector("[data-houseplant-form]");
  if (potForm) {
    const pots = JSON.parse(potForm.dataset.houseplants || "[]");
    const cropSel = potForm.querySelector("#crop");
    const label = potForm.querySelector("[data-label-field]");
    const sync = () => {
      const pot = pots.includes(cropSel.value);
      potForm.querySelectorAll("[data-field-only]").forEach((el) => (el.hidden = pot));
      potForm.querySelectorAll("[data-pot-only]").forEach((el) => (el.hidden = !pot));
      if (label) label.textContent = pot ? "Last watered on" : "Last irrigated on";
    };
    cropSel.addEventListener("change", sync);
    sync();
  }

  /* ---------------- crop guide: search and group filter ---------------- */
  const guide = document.querySelector("[data-guide]");
  if (guide) {
    const cards = Array.from(document.querySelectorAll("[data-guide-card]"));
    const search = guide.querySelector("[data-guide-search]");
    const count = guide.querySelector("[data-guide-count]");
    let group = "";
    const apply = () => {
      const q = search.value.trim().toLowerCase();
      let shown = 0;
      cards.forEach((c) => {
        const okGroup = !group || (group === "photo" ? c.dataset.photo === "1" : c.dataset.group === group);
        const ok = okGroup && (!q || c.dataset.text.includes(q));
        c.hidden = !ok;
        if (ok) shown += 1;
      });
      count.textContent = shown === 1 ? "Showing 1 crop" : `Showing ${shown} crops`;
    };
    guide.querySelectorAll("[data-guide-group]").forEach((b) => b.addEventListener("click", () => {
      guide.querySelectorAll("[data-guide-group]").forEach((x) => x.classList.toggle("active", x === b));
      group = b.dataset.guideGroup;
      apply();
    }));
    search.addEventListener("input", apply);
  }

  /* ---------------- location search ---------------- */
  $$("[data-loc-picker]").forEach((picker) => {
    const input = $("[data-loc-input]", picker);
    const list = $("[data-loc-results]", picker);
    const lat = $("[data-loc-lat]", picker);
    const lon = $("[data-loc-lon]", picker);
    const status = $("[data-loc-status] span", picker);
    const navigate = picker.hasAttribute("data-loc-navigate");
    let timer = null;

    function choose(name, la, lo) {
      input.value = name; lat.value = la; lon.value = lo;
      if (status) status.textContent = Number(la).toFixed(3) + ", " + Number(lo).toFixed(3);
      list.classList.remove("open");
      if (navigate) {
        const url = new URL(picker.getAttribute("action"), window.location.origin);
        url.searchParams.set("lat", la); url.searchParams.set("lon", lo); url.searchParams.set("name", name);
        window.location.href = url.toString();
      }
    }

    input.addEventListener("input", () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) { list.classList.remove("open"); return; }
      timer = setTimeout(async () => {
        try {
          const res = await fetch("/api/geocode?q=" + encodeURIComponent(q));
          const data = await res.json();
          list.innerHTML = "";
          if (!data.results || !data.results.length) {
            list.innerHTML = '<button type="button" disabled>' + (data.error || "No places found") + "</button>";
          } else {
            data.results.forEach((r) => {
              const b = document.createElement("button");
              b.type = "button";
              b.textContent = r.label;
              b.addEventListener("click", () => choose(r.label, r.lat, r.lon));
              list.appendChild(b);
            });
          }
          list.classList.add("open");
        } catch (e) { list.classList.remove("open"); }
      }, 300);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); const first = $("button:not([disabled])", list); if (first) first.click(); }
      if (e.key === "Escape") list.classList.remove("open");
    });
    document.addEventListener("click", (e) => { if (!picker.contains(e.target)) list.classList.remove("open"); });

    const gps = $("[data-loc-gps]", picker);
    if (gps) gps.addEventListener("click", () => {
      if (!navigator.geolocation) { alert("Location is not available in this browser."); return; }
      if (status) status.textContent = "Finding your location...";
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const la = pos.coords.latitude.toFixed(4), lo = pos.coords.longitude.toFixed(4);
          choose("My location (" + Number(la).toFixed(3) + ", " + Number(lo).toFixed(3) + ")", la, lo);
        },
        () => { if (status) status.textContent = "Could not get your location. Search by name instead."; },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  });

  /* ---------------- charts ---------------- */
  const charts = [];
  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function dayLabel(iso) {
    const d = new Date(iso + "T00:00:00");
    if (isNaN(d)) return iso;
    return d.toLocaleDateString(undefined, { weekday: "short", day: "numeric" });
  }

  function baseOptions(yTitle, extra) {
    const ink = css("--text-2"), grid = css("--chart-grid"), axis = css("--chart-axis");
    return Object.assign({
      responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: css("--surface"), titleColor: css("--text"), bodyColor: ink, borderColor: css("--border-strong"), borderWidth: 1, padding: 10, boxPadding: 4, usePointStyle: true },
      },
      scales: {
        x: { grid: { display: false }, border: { color: axis }, ticks: { color: ink, font: { size: 11 } } },
        y: { beginAtZero: true, grid: { color: grid }, border: { display: false }, ticks: { color: ink, font: { size: 11 } },
             title: { display: !!yTitle, text: yTitle, color: ink, font: { size: 11 } } },
      },
    }, extra || {});
  }

  function renderCharts() {
    if (!window.Chart) return;
    const dataEl = $("#chart-data");
    if (!dataEl) return;
    const data = JSON.parse(dataEl.textContent);
    charts.splice(0).forEach((c) => c.destroy());
    Chart.defaults.font.family = css("--font") || "system-ui";
    const s1 = css("--series-1"), s2 = css("--series-2"), crit = css("--critical"), surface = css("--surface");

    $$("canvas[data-chart]").forEach((cv) => {
      const type = cv.dataset.chart;
      let cfg = null;
      if (type === "water") {
        const bar = { borderRadius: { topLeft: 4, topRight: 4 }, borderSkipped: "bottom", barPercentage: 0.82, categoryPercentage: 0.7, maxBarThickness: 26 };
        cfg = { type: "bar", data: { labels: data.labels, datasets: [
          Object.assign({ label: "ET₀ (mm)", data: data.et0, backgroundColor: s2 }, bar),
          Object.assign({ label: "Rainfall (mm)", data: data.rain, backgroundColor: s1 }, bar),
        ] }, options: baseOptions("mm per day") };
      } else if (type === "temperature") {
        const line = { borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, pointBorderColor: surface, pointBorderWidth: 2, tension: 0.3 };
        const opts = baseOptions("°C");
        opts.scales.y.beginAtZero = false;
        cfg = { type: "line", data: { labels: data.labels, datasets: [
          Object.assign({ label: "Max °C", data: data.tmax, borderColor: s2, backgroundColor: s2 }, line),
          Object.assign({ label: "Min °C", data: data.tmin, borderColor: s1, backgroundColor: s1 }, line),
        ] }, options: opts };
      } else if (type === "depletion") {
        const irr = data.irrigate || [];
        const opts = baseOptions("% of available water used");
        opts.scales.y.max = 100;
        opts.plugins.tooltip.callbacks = {
          afterBody: (items) => { const i = items[0].dataIndex; return irr[i] ? "Irrigate " + irr[i] + " mm (gross)" : ""; },
        };
        cfg = { type: "line", data: { labels: data.labels.map(dayLabel), datasets: [
          { label: "Depletion (%)", data: data.depletion, borderColor: s1, backgroundColor: s1, borderWidth: 2, tension: 0.25,
            pointRadius: irr.map((v) => (v ? 7 : 4)), pointStyle: irr.map((v) => (v ? "rectRot" : "circle")),
            pointBackgroundColor: irr.map((v) => (v ? crit : s1)), pointBorderColor: surface, pointBorderWidth: 2 },
          { label: "Irrigation threshold (%)", data: data.threshold, borderColor: crit, borderWidth: 2, borderDash: [6, 4], pointRadius: 0, fill: false },
        ] }, options: opts };
      }
      if (cfg) charts.push(new Chart(cv, cfg));
    });
  }
  window.addEventListener("load", renderCharts);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderCharts);
})();
