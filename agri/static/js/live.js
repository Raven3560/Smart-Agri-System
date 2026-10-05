/* Live scan: classify camera frames continuously and show the plant's health over the video.
 *
 * Flow per frame:
 *   1. copy the square inside the on-screen guide box from the <video> to a 320 x 320 canvas,
 *   2. POST it as JPEG to /api/live/predict (one request in flight at a time),
 *   3. smooth the class probabilities of both models over recent frames (exponential moving average),
 *   4. if a crop is selected, keep only that crop's classes and renormalise (same rule as the
 *      full report), then call the result "steady" once the same answer repeats 3 frames in a row.
 */
(function () {
  "use strict";
  const root = document.querySelector("[data-live]");
  if (!root) return;

  const $ = (sel) => root.querySelector(sel);
  const $$ = (sel) => Array.from(root.querySelectorAll(sel));
  const meta = JSON.parse(root.dataset.meta);
  const defaults = JSON.parse(root.dataset.defaults);
  const csrf = document.body.dataset.csrf;

  const stage = $("[data-stage]");
  const video = $("[data-video]");
  const guide = $("[data-guide]");
  const badgeText = $("[data-badge-text]");
  const hint = $("[data-hint]");
  const startPanel = $("[data-start]");
  const startMsg = $("[data-start-msg]");
  const controls = $("[data-controls]");
  const cropSelect = $("[data-crop]");
  const pauseBtn = $("[data-pause]");
  const switchBtn = $("[data-switch]");
  const torchBtn = $("[data-torch]");
  const captureBtns = $$("[data-capture]");

  const SEND_SIZE = 320;           // pixels sent to the server per frame
  const REPORT_SIZE = 720;         // pixels sent for a full report
  const MIN_INTERVAL = 200;        // ms between frames (max ~5 per second)
  const EMA_NEW = 0.45;            // weight of the newest frame in the moving average
  const STEADY_FRAMES = 3;
  const CONF_OK = 0.5;
  const MIN_CROP_MASS = 0.15;
  const MIN_PLANT = 0.05;
  const GUIDE_SHARE = 0.66;        // guide square = 66% of the shorter side of the view

  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");

  let stream = null;
  let running = false;
  let paused = false;
  let inFlight = false;
  let facing = "environment";
  let torchOn = false;
  let ema = null;
  let lastBest = -1;
  let streak = 0;
  let current = null;              // latest decision
  let rtts = [];
  let gotFirst = false;

  /* ---------- geometry: map the guide box to video pixels ---------- */
  function layoutGuide() {
    const w = stage.clientWidth, h = stage.clientHeight;
    const side = Math.round(Math.min(w, h) * GUIDE_SHARE);
    guide.style.width = side + "px";
    guide.style.height = side + "px";
  }
  window.addEventListener("resize", layoutGuide);

  function guideRegion() {
    const vw = video.videoWidth, vh = video.videoHeight;
    const ew = video.clientWidth, eh = video.clientHeight;
    const scale = Math.max(ew / vw, eh / vh);            // object-fit: cover
    const offX = (vw * scale - ew) / 2, offY = (vh * scale - eh) / 2;
    const side = Math.min(ew, eh) * GUIDE_SHARE;
    const gx = (ew - side) / 2, gy = (eh - side) / 2;
    return { sx: (gx + offX) / scale, sy: (gy + offY) / scale, s: side / scale };
  }

  function grab(size, quality) {
    const r = guideRegion();
    canvas.width = canvas.height = size;
    ctx.drawImage(video, r.sx, r.sy, r.s, r.s, 0, 0, size, size);
    return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
  }

  /* ---------- camera ---------- */
  function cameraBlockedReason() {
    if (!window.isSecureContext) {
      return "The camera only works over a secure connection. Open this page as http://localhost:5000 on this computer, " +
             "or start the app with  python run.py --host 0.0.0.0 --https  to scan from a phone.";
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return "This browser can't open the camera. Try Chrome, Edge or Safari, or use a video file.";
    }
    return null;
  }

  async function startCamera() {
    const blocked = cameraBlockedReason();
    if (blocked) { startMsg.textContent = blocked; return; }
    stopStream();
    startMsg.textContent = "Waiting for camera permission...";
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: facing }, width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
    } catch (err) {
      startMsg.textContent = err && err.name === "NotAllowedError"
        ? "Camera permission was refused. Allow camera access in the browser's address bar, then try again."
        : "No camera was found. Connect a camera, or use a video file instead.";
      return;
    }
    video.removeAttribute("src");
    video.srcObject = stream;
    await video.play().catch(() => {});
    setupTrackButtons();
    begin();
  }

  async function setupTrackButtons() {
    const track = stream && stream.getVideoTracks()[0];
    const caps = track && track.getCapabilities ? track.getCapabilities() : {};
    torchBtn.hidden = !caps.torch;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      switchBtn.hidden = devices.filter((d) => d.kind === "videoinput").length < 2;
    } catch (e) { switchBtn.hidden = true; }
  }

  function stopStream() {
    if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
  }

  function useVideoFile(file) {
    stopStream();
    video.srcObject = null;
    video.src = URL.createObjectURL(file);
    video.loop = true;
    video.play().catch(() => {});
    switchBtn.hidden = true;
    torchBtn.hidden = true;
    begin();
  }

  function begin() {
    startPanel.hidden = true;
    controls.hidden = false;
    running = true;
    paused = false;
    resetSmoothing();
    setBadge("Loading the model...", "running");
    captureBtns.forEach((b) => (b.disabled = false));
    requestAnimationFrame(layoutGuide);
    loop();
  }

  /* ---------- frame loop ---------- */
  async function loop() {
    if (!running) return;
    if (paused || inFlight || video.readyState < 2 || document.hidden) { setTimeout(loop, 150); return; }
    const t0 = performance.now();
    inFlight = true;
    try {
      const blob = await grab(SEND_SIZE, 0.85);
      const fd = new FormData();
      fd.append("frame", blob, "frame.jpg");
      const res = await fetch("/api/live/predict", { method: "POST", body: fd, headers: { "X-CSRF-Token": csrf } });
      if (res.status === 401) { window.location.href = "/login?next=/live"; return; }
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "error");
      handle(data, performance.now() - t0);
    } catch (err) {
      setBadge("Connection problem, retrying...", "unsure");
    } finally {
      inFlight = false;
    }
    setTimeout(loop, Math.max(0, MIN_INTERVAL - (performance.now() - t0)));
  }

  function resetSmoothing() { ema = null; lastBest = -1; streak = 0; current = null; }

  /* ---------- decision ---------- */
  function decide(data) {
    const crop = cropSelect.value;
    const idx = crop === "auto" ? meta.map((_, i) => i) : meta.map((m, i) => (m.crop === crop ? i : -1)).filter((i) => i >= 0);
    let mass = 0, best = idx[0];
    idx.forEach((i) => { mass += ema[i]; if (ema[i] > ema[best]) best = i; });
    // With a single class for the crop, renormalising would always say 100%, so keep the raw value.
    let conf = crop === "auto" || idx.length === 1 ? ema[best] : (mass > 0 ? ema[best] / mass : 0);
    if (crop !== "auto" && idx.length > 1 && mass < MIN_CROP_MASS) conf = Math.min(conf, mass);
    const noHealthy = crop !== "auto" && !idx.some((i) => meta[i].healthy);

    streak = best === lastBest ? streak + 1 : 1;
    lastBest = best;

    let state;
    if (data.plant < MIN_PLANT && conf < 0.75) state = "noleaf";
    else if (conf < CONF_OK) state = "unsure";
    else if (streak < STEADY_FRAMES) state = "steadying";
    else state = meta[best].healthy ? "healthy" : "diseased";

    const ranked = idx.slice().sort((a, b) => ema[b] - ema[a]).slice(0, 3)
      .map((i) => ({ i, p: crop === "auto" || idx.length === 1 ? ema[i] : (mass > 0 ? ema[i] / mass : 0) }));
    return { best, conf, state, ranked, crop, noHealthy };
  }

  function handle(data, rtt) {
    const p = data.probs;
    ema = ema ? ema.map((v, i) => (1 - EMA_NEW) * v + EMA_NEW * p[i]) : p.slice();
    current = decide(data);
    rtts.push(rtt); if (rtts.length > 10) rtts.shift();
    gotFirst = true;
    render(current, data);
  }

  /* ---------- rendering ---------- */
  const STATE_TEXT = {
    noleaf: "Point the camera at a leaf",
    unsure: "Not sure yet. Move closer or improve the light",
    steadying: "Hold steady...",
  };
  const BADGES = {
    healthy: '<span class="badge badge-good"><svg class="icon"><use href="#i-check"/></svg> Looks healthy</span>',
    diseased: '<span class="badge badge-critical"><svg class="icon"><use href="#i-alert"/></svg> Disease detected</span>',
    unsure: '<span class="badge badge-warning"><svg class="icon"><use href="#i-help"/></svg> Not sure</span>',
    noleaf: '<span class="badge badge-warning"><svg class="icon"><use href="#i-help"/></svg> No leaf found</span>',
    steadying: '<span class="badge badge-neutral"><svg class="icon"><use href="#i-scan"/></svg> Steadying</span>',
  };

  function setBadge(text, state) {
    badgeText.textContent = text;
    stage.dataset.state = state;
  }

  function pct(x) { return Math.round(x * 100) + "%"; }

  function render(d, data) {
    const m = meta[d.best];
    const steady = d.state === "healthy" || d.state === "diseased";
    setBadge(steady ? `${m.name} · ${pct(d.conf)}` : (d.state === "steadying" ? `${m.name}?` : STATE_TEXT[d.state]), d.state);
    hint.textContent = d.state === "noleaf" ? "Fill the square with one leaf" :
      (!data.quality.ok && d.conf < 0.75 ? data.quality.issues[0] : "");

    $("[data-status-badge]").innerHTML = BADGES[d.state];
    $("[data-name]").textContent = d.state === "noleaf" ? "No leaf in view" : m.name;
    $("[data-crop-name]").textContent = d.state === "noleaf" ? "Hold one leaf inside the square." :
      `${m.crop_name}${d.crop === "auto" ? " (detected)" : ""}`;
    $("[data-conf]").textContent = pct(d.conf);
    const bar = $("[data-conf-bar]");
    bar.style.width = pct(d.conf);
    bar.parentElement.className = "meter " + ({ healthy: "m-good", diseased: "m-critical", unsure: "m-warning", noleaf: "m-warning" }[d.state] || "m-info");
    $("[data-advice]").textContent = {
      healthy: "No disease visible on this leaf. Save a report to log it, or move on to the next plant.",
      diseased: "Save a full report to get treatment steps, the best day to spray and an irrigation check.",
      unsure: "The model isn't confident. Get closer, fill the square with one leaf, and avoid shadows.",
      noleaf: "Hold a single leaf inside the square, about 20-30 cm from the camera.",
      steadying: "Keep the camera still for a moment.",
    }[d.state] + (d.noHealthy && d.state === "diseased"
      ? " Note: the model has no 'healthy' class for this crop, so it always names the closest problem." : "");

    $("[data-top3]").innerHTML = d.ranked.map((r) =>
      `<div class="top3-row"><span>${meta[r.i].name} <span class="muted small">· ${meta[r.i].crop_name}</span></span>` +
      `<strong class="tabular" style="text-align:right">${pct(r.p)}</strong>` +
      `<div class="meter m-info"><span style="width:${(r.p * 100).toFixed(1)}%"></span></div></div>`).join("");

    $("[data-q-plant]").textContent = data.plant >= 0.15 ? "Yes" : data.plant >= MIN_PLANT ? "A little" : "No";
    $("[data-q-sharp]").textContent = data.quality.sharpness >= 60 ? "Good" : data.quality.sharpness >= 20 ? "OK" : "Blurry";
    $("[data-q-light]").textContent = data.quality.brightness < 45 ? "Too dark" : data.quality.brightness > 225 ? "Too bright" : "Good";
    const avg = rtts.reduce((a, b) => a + b, 0) / rtts.length;
    $("[data-q-speed]").textContent = `${(1000 / Math.max(avg, MIN_INTERVAL)).toFixed(1)}/s`;
  }

  /* ---------- full report ---------- */
  async function saveReport() {
    if (!running || video.readyState < 2) return;
    const busy = document.getElementById("busy");
    if (busy) { document.getElementById("busy-title").textContent = "Preparing the full report..."; busy.classList.add("open"); }
    captureBtns.forEach((b) => (b.disabled = true));
    try {
      const blob = await grab(REPORT_SIZE, 0.92);
      const crop = cropSelect.value !== "auto" ? cropSelect.value : (current ? meta[current.best].crop : "tomato");
      const fd = new FormData();
      fd.append("csrf_token", csrf);
      fd.append("crop", crop);
      ["stage", "soil", "method", "area_acres", "location_name", "lat", "lon"].forEach((k) => {
        if (defaults[k] !== null && defaults[k] !== undefined) fd.append(k, defaults[k]);
      });
      fd.append("last_irrigation", "");
      fd.append("image", blob, "live-scan.jpg");
      const res = await fetch("/analyze", { method: "POST", body: fd });
      if (res.ok && /\/analysis\/\d+/.test(res.url)) { stopStream(); window.location.href = res.url; return; }
      throw new Error("save failed");
    } catch (err) {
      if (busy) busy.classList.remove("open");
      captureBtns.forEach((b) => (b.disabled = false));
      alert("Couldn't save the report. Check the connection and try again.");
    }
  }

  /* ---------- controls ---------- */
  $("[data-start-btn]").addEventListener("click", startCamera);
  $("[data-file]").addEventListener("change", (e) => { if (e.target.files[0]) useVideoFile(e.target.files[0]); });
  cropSelect.addEventListener("change", () => { if (ema) { current = null; streak = 0; lastBest = -1; } });
  captureBtns.forEach((b) => b.addEventListener("click", saveReport));
  pauseBtn.addEventListener("click", () => {
    paused = !paused;
    pauseBtn.querySelector("span").textContent = paused ? "Resume" : "Pause";
    pauseBtn.querySelector("use").setAttribute("href", paused ? "#i-play" : "#i-pause");
    if (paused) { video.pause(); setBadge("Paused", "idle"); } else { video.play().catch(() => {}); resetSmoothing(); }
  });
  switchBtn.addEventListener("click", () => { facing = facing === "environment" ? "user" : "environment"; startCamera(); });
  torchBtn.addEventListener("click", async () => {
    const track = stream && stream.getVideoTracks()[0];
    if (!track) return;
    torchOn = !torchOn;
    try { await track.applyConstraints({ advanced: [{ torch: torchOn }] }); } catch (e) { torchOn = false; }
    torchBtn.classList.toggle("on", torchOn);
  });
  window.addEventListener("pagehide", stopStream);

  layoutGuide();
  const blocked = cameraBlockedReason();
  if (blocked) startMsg.textContent = blocked;
})();
