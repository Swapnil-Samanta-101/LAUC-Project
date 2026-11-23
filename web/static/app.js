// 2D Navier-Stokes CFD Simulator - High-Performance Frontend Controller

// Colormap color stop definitions
const COLORMAPS = {
  viridis: [
    [68,1,84],[70,8,92],[71,16,99],[72,23,105],[72,29,111],[71,36,117],[70,42,122],[68,49,126],
    [66,55,130],[63,61,133],[60,67,135],[57,73,137],[54,78,138],[51,84,139],[47,90,140],[44,95,141],
    [41,100,141],[38,106,142],[35,111,142],[33,116,142],[30,121,142],[28,126,142],[26,131,141],[24,136,141],
    [23,141,140],[22,146,140],[21,151,139],[21,156,138],[22,161,136],[25,166,135],[29,171,133],[34,176,131],
    [40,180,128],[47,185,126],[56,190,122],[65,194,119],[75,198,115],[86,202,111],[98,206,106],[110,209,101],
    [123,212,96],[136,215,90],[149,218,84],[163,220,78],[177,222,72],[191,224,66],[205,225,60],[220,226,54],
    [234,227,49],[248,228,45],[253,231,37]
  ],
  inferno: [
    [0,0,4],[10,7,29],[25,12,53],[42,10,74],[60,9,90],[79,14,99],[97,21,103],[116,29,104],
    [135,37,101],[154,46,95],[172,55,86],[189,66,74],[205,79,60],[219,94,44],[230,111,27],[239,130,9],
    [246,150,0],[249,171,4],[250,193,24],[248,214,51],[243,235,84],[245,248,125],[252,255,178]
  ],
  coolwarm: [
    [59,76,192],[68,90,204],[77,104,215],[87,117,225],[98,131,234],[109,144,241],[120,157,247],[132,170,251],
    [144,182,254],[157,194,255],[170,205,254],[183,215,251],[196,225,246],[209,234,239],[221,241,230],[232,246,220],
    [241,248,209],[248,247,196],[252,242,183],[254,234,168],[254,224,153],[252,211,137],[248,196,122],[242,180,107],
    [235,162,93],[226,143,80],[216,123,68],[204,103,57],[190,82,47],[175,62,38],[158,41,30],[140,20,23],[122,4,3]
  ]
};

// Helper: interpolate RGB from palette stops
function sampleColormap(name, t) {
  const palette = COLORMAPS[name] || COLORMAPS.viridis;
  const clamped = Math.max(0, Math.min(1, t));
  const idx = clamped * (palette.length - 1);
  const i0 = Math.floor(idx);
  const i1 = Math.min(i0 + 1, palette.length - 1);
  const frac = idx - i0;

  const c0 = palette[i0];
  const c1 = palette[i1];
  return [
    Math.round(c0[0] + frac * (c1[0] - c0[0])),
    Math.round(c0[1] + frac * (c1[1] - c0[1])),
    Math.round(c0[2] + frac * (c1[2] - c0[2]))
  ];
}

// Precompute 256-entry 32-bit RGBA lookup tables for ultra-fast canvas blitting (< 0.25 ms)
const COLORMAP_LUTS = {};
for (const [name, palette] of Object.entries(COLORMAPS)) {
  const lut = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    const t = i / 255.0;
    const rgb = sampleColormap(name, t);
    // Little-endian ABGR representation: Alpha=255, Blue, Green, Red
    lut[i] = ((255 << 24) >>> 0) | (rgb[2] << 16) | (rgb[1] << 8) | rgb[0];
  }
  COLORMAP_LUTS[name] = lut;
}

// Particle System for Streamline / Streakline Visualization
class ParticleSystem {
  constructor(count = 250) {
    this.count = count;
    this.particles = [];
    this.init();
  }

  init() {
    this.particles = [];
    for (let i = 0; i < this.count; i++) {
      this.particles.push({
        x: Math.random(),
        y: Math.random(),
        age: Math.floor(Math.random() * 80),
        maxAge: 60 + Math.floor(Math.random() * 60)
      });
    }
  }

  update(velSub) {
    if (!velSub || !velSub.u || velSub.u.length === 0) return;
    const nx = velSub.nx;
    const ny = velSub.ny;

    for (let p of this.particles) {
      p.age++;
      if (p.age > p.maxAge || p.x < 0 || p.x > 1.0 || p.y < 0 || p.y > 1.0) {
        p.x = Math.random() * 0.05;
        p.y = Math.random();
        p.age = 0;
        continue;
      }

      const ix = Math.min(nx - 1, Math.max(0, Math.floor(p.x * nx)));
      const iy = Math.min(ny - 1, Math.max(0, Math.floor(p.y * ny)));
      const idx = iy * nx + ix;

      const u = velSub.u[idx] || 0;
      const v = velSub.v[idx] || 0;

      p.x += u * 0.015;
      p.y += v * 0.015;
    }
  }

  draw(ctx, width, height) {
    for (let p of this.particles) {
      const alpha = Math.sin((p.age / p.maxAge) * Math.PI) * 0.7;
      ctx.fillStyle = `rgba(255, 255, 255, ${alpha.toFixed(2)})`;
      const px = p.x * width;
      const py = (1.0 - p.y) * height;
      ctx.fillRect(px, py, 1.8, 1.8);
    }
  }
}

// Main App Controller
class CFDApp {
  constructor() {
    this.canvas = document.getElementById("cfd-canvas");
    this.ctx = this.canvas.getContext("2d");
    this.offscreenCanvas = document.createElement("canvas");
    this.offscreenCtx = this.offscreenCanvas.getContext("2d");

    // Track active simulation mode to conditionally render geometry and charts
    this.currentMode = "airfoil";

    // Pre-allocated typed buffer for image blitting
    this.imgData = null;
    this.pixels32 = null;

    this.particles = new ParticleSystem(250);
    this.showParticles = true;
    this.colormap = "viridis";
    this.activeLUT = COLORMAP_LUTS[this.colormap];

    this.ws = null;
    this.lastFrameTime = performance.now();
    this.fps = 60;

    // Decoupled render loop state
    this.latestFrame = null;
    this.lastRenderedFrame = null;
    this.cachedPolygons = [];
    this.lastChartUpdate = 0;

    // FoilSim and Analysis state
    this.shapeType = "naca";
    this.showProbe = false;
    this.showVectors = false;
    this.probeThrottleTimer = null;
    this.sweepLiftChart = null;
    this.sweepPolarChart = null;

    // Slider throttling / debouncing
    this.pendingConfig = {};
    this.configTimer = null;

    // Charts
    this.cpChart = null;
    this.historyChart = null;
    this.clHistory = [];
    this.cdHistory = [];
    this.timeHistory = [];

    this.initUI();
    this.initCharts();
    this.startRenderLoop();
    this.connectWebSocket();
  }

  initUI() {
    // Mode tabs
    document.querySelectorAll(".mode-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const mode = btn.dataset.mode;
        this.switchMode(mode);
      });
    });

    // Control buttons
    const btnPlay = document.getElementById("btn-play");
    btnPlay.addEventListener("click", () => {
      const icon = document.getElementById("play-icon");
      const text = document.getElementById("play-text");
      if (text.textContent === "Pause") {
        this.sendAction("pause");
        text.textContent = "Play";
        icon.textContent = "▶";
        btnPlay.classList.replace("btn-primary", "btn-secondary");
      } else {
        this.sendAction("play");
        text.textContent = "Pause";
        icon.textContent = "⏸";
        btnPlay.classList.replace("btn-secondary", "btn-primary");
      }
    });

    document.getElementById("btn-step").addEventListener("click", () => this.sendAction("step"));
    
    // Reset button: flushes charts, HUD metrics, and requests server reset
    document.getElementById("btn-reset").addEventListener("click", () => {
      this.resetChartsAndTelemetry();
      this.sendAction("reset");
    });

    // Range Sliders with immediate DOM label updates & 40ms network throttling
    const sliderRe = document.getElementById("slider-re");
    sliderRe.addEventListener("input", (e) => {
      document.getElementById("val-re").textContent = e.target.value;
      this.throttleConfig("reynolds", parseFloat(e.target.value));
    });

    const sliderAoA = document.getElementById("slider-aoa");
    sliderAoA.addEventListener("input", (e) => {
      const val = parseFloat(e.target.value);
      document.getElementById("val-aoa").textContent = (val >= 0 ? "+" : "") + val.toFixed(1) + "°";
      this.throttleConfig("alpha_deg", val);
    });

    // FoilSim Shape Presets
    document.querySelectorAll(".shape-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        document.querySelectorAll(".shape-chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        this.shapeType = chip.dataset.shape;
        this.updateShapeUI();
        this.sendConfig({ shape_type: this.shapeType });
      });
    });

    // Camber slider
    const sliderCamber = document.getElementById("slider-camber");
    if (sliderCamber) {
      sliderCamber.addEventListener("input", (e) => {
        const val = parseFloat(e.target.value);
        document.getElementById("val-camber").textContent = val.toFixed(1) + "% c";
        this.throttleConfig("camber", val / 100.0);
      });
    }

    // Thickness slider
    const sliderThick = document.getElementById("slider-thickness");
    if (sliderThick) {
      sliderThick.addEventListener("input", (e) => {
        const val = parseFloat(e.target.value);
        document.getElementById("val-thickness").textContent = val.toFixed(1) + "% c";
        this.throttleConfig("thickness", val / 100.0);
      });
    }

    // Spin Rate slider (Rotating Cylinder)
    const sliderSpin = document.getElementById("slider-spin");
    if (sliderSpin) {
      sliderSpin.addEventListener("input", (e) => {
        const val = parseFloat(e.target.value);
        document.getElementById("val-spin").textContent = (val >= 0 ? "+" : "") + val.toFixed(1) + " rad/s";
        this.throttleConfig("spin_rate", val);
      });
    }

    // NACA presets & input
    document.getElementById("btn-apply-naca").addEventListener("click", () => {
      const code = document.getElementById("input-naca").value.trim();
      if (code.length === 4) this.sendConfig({ naca_code: code });
    });

    document.querySelectorAll(".chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const code = chip.dataset.naca;
        document.getElementById("input-naca").value = code;
        this.sendConfig({ naca_code: code });
      });
    });

    // Flight & Atmospheric Conditions
    const sliderAirspeed = document.getElementById("slider-airspeed");
    if (sliderAirspeed) {
      sliderAirspeed.addEventListener("input", (e) => {
        const val = parseFloat(e.target.value);
        document.getElementById("val-airspeed").textContent = val.toFixed(1) + " m/s";
        this.throttleConfig("airspeed", val);
      });
    }

    const sliderAltitude = document.getElementById("slider-altitude");
    if (sliderAltitude) {
      sliderAltitude.addEventListener("input", (e) => {
        const val = parseFloat(e.target.value);
        document.getElementById("val-altitude").textContent = `${Math.round(val)} m`;
        this.throttleConfig("altitude", val);
      });
    }

    const inputArea = document.getElementById("input-wing-area");
    if (inputArea) {
      inputArea.addEventListener("change", (e) => {
        const val = Math.max(0.01, parseFloat(e.target.value) || 1.0);
        this.sendConfig({ wing_area: val });
      });
    }

    const inputChord = document.getElementById("input-chord");
    if (inputChord) {
      inputChord.addEventListener("change", (e) => {
        const val = Math.max(0.01, parseFloat(e.target.value) || 1.0);
        this.sendConfig({ chord_length: val });
      });
    }

    // Interactive Flow Probe & Canvas Crosshair
    const toggleProbe = document.getElementById("toggle-probe");
    if (toggleProbe) {
      toggleProbe.addEventListener("change", (e) => {
        this.showProbe = e.target.checked;
        if (!this.showProbe) {
          const hud = document.getElementById("flow-probe-hud");
          if (hud) hud.classList.add("hidden");
          this.sendWS({ action: "clear_probe" });
        }
      });
    }

    this.canvas.addEventListener("mousemove", (e) => {
      if (!this.showProbe) return;
      const rect = this.canvas.getBoundingClientRect();
      const normX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const normY = Math.max(0, Math.min(1, 1.0 - ((e.clientY - rect.top) / rect.height)));

      if (!this.probeThrottleTimer) {
        this.probeThrottleTimer = setTimeout(() => {
          this.sendWS({ action: "probe", x: normX, y: normY });
          this.probeThrottleTimer = null;
        }, 30);
      }
    });

    this.canvas.addEventListener("mouseleave", () => {
      if (this.showProbe) {
        const hud = document.getElementById("flow-probe-hud");
        if (hud) hud.classList.add("hidden");
        this.sendWS({ action: "clear_probe" });
      }
    });

    // Surface Pressure Vectors
    const toggleVectors = document.getElementById("toggle-vectors");
    if (toggleVectors) {
      toggleVectors.addEventListener("change", (e) => {
        this.showVectors = e.target.checked;
      });
    }

    // Alpha Sweep Modal triggers
    const btnSweep = document.getElementById("btn-alpha-sweep");
    if (btnSweep) {
      btnSweep.addEventListener("click", () => this.runAlphaSweep());
    }

    const btnCloseSweep = document.getElementById("btn-close-sweep");
    if (btnCloseSweep) {
      btnCloseSweep.addEventListener("click", () => {
        document.getElementById("sweep-modal").classList.add("hidden");
      });
    }

    // Cascade sliders
    document.getElementById("slider-stagger").addEventListener("input", (e) => {
      document.getElementById("val-stagger").textContent = e.target.value + "°";
      this.throttleConfig("cascade_stagger", parseFloat(e.target.value));
    });

    document.getElementById("slider-pitch").addEventListener("input", (e) => {
      document.getElementById("val-pitch").textContent = parseFloat(e.target.value).toFixed(2);
      this.throttleConfig("cascade_pitch", parseFloat(e.target.value));
    });

    document.getElementById("slider-inlet-angle").addEventListener("input", (e) => {
      document.getElementById("val-inlet-angle").textContent = e.target.value + "°";
      this.throttleConfig("cascade_inlet_angle", parseFloat(e.target.value));
    });

    // Visualization options
    document.getElementById("select-field").addEventListener("change", (e) => {
      this.sendWS({ action: "set_field", field: e.target.value });
      document.getElementById("cb-title").textContent =
        e.target.value === "vorticity" ? "ω" :
        e.target.value === "speed" ? "|u|" :
        e.target.value === "pressure" ? "p" : "div";
    });

    document.getElementById("select-colormap").addEventListener("change", (e) => {
      this.colormap = e.target.value;
      this.activeLUT = COLORMAP_LUTS[this.colormap] || COLORMAP_LUTS.viridis;
      this.updateColorbarGradient();
    });

    document.getElementById("toggle-particles").addEventListener("change", (e) => {
      this.showParticles = e.target.checked;
    });

    document.getElementById("select-resolution").addEventListener("change", (e) => {
      this.sendConfig({ resolution: e.target.value });
    });

    // Simulation Speed selector
    const selectSpeed = document.getElementById("select-speed");
    if (selectSpeed) {
      selectSpeed.addEventListener("change", (e) => {
        this.sendConfig({ speed_multiplier: parseInt(e.target.value, 10) });
      });
    }

    this.updateColorbarGradient();
  }

  throttleConfig(key, value, delay = 40) {
    this.pendingConfig[key] = value;
    if (!this.configTimer) {
      this.configTimer = setTimeout(() => {
        this.sendConfig(this.pendingConfig);
        this.pendingConfig = {};
        this.configTimer = null;
      }, delay);
    }
  }

  updateColorbarGradient() {
    const bar = document.getElementById("colorbar-gradient");
    const p = COLORMAPS[this.colormap] || COLORMAPS.viridis;
    const stops = p.map((c, i) => {
      const pct = (i / (p.length - 1)) * 100;
      return `rgb(${c[0]},${c[1]},${c[2]}) ${pct}%`;
    }).join(", ");
    bar.style.background = `linear-gradient(to top, ${stops})`;
  }

  resetChartsAndTelemetry() {
    // Clear history arrays
    this.clHistory = [];
    this.cdHistory = [];
    this.timeHistory = [];

    // Clear Aerodynamic History Chart
    if (this.historyChart) {
      this.historyChart.data.labels = [];
      this.historyChart.data.datasets[0].data = [];
      this.historyChart.data.datasets[1].data = [];
      this.historyChart.update("none");
    }

    // Clear Surface Cp Chart
    if (this.cpChart) {
      this.cpChart.data.labels = [];
      this.cpChart.data.datasets[0].data = [];
      this.cpChart.data.datasets[1].data = [];
      this.cpChart.update("none");
    }

    // Reset HUD telemetry display
    const elTime = document.getElementById("stat-time");
    if (elTime) elTime.textContent = "0.00s";
    const elDt = document.getElementById("stat-dt");
    if (elDt) elDt.textContent = "0.0000s";
    const elStep = document.getElementById("stat-step");
    if (elStep) elStep.textContent = "0";
    const elCl = document.getElementById("hud-cl");
    if (elCl) elCl.textContent = "0.0000";
    const elCd = document.getElementById("hud-cd");
    if (elCd) elCd.textContent = "0.0000";
    const elLd = document.getElementById("hud-ld");
    if (elLd) elLd.textContent = "0.00";
  }

  switchMode(mode) {
    this.currentMode = mode;

    // Immediately flush old polygons and frame buffers so zero ghost geometry leaks
    this.cachedPolygons = [];
    this.latestFrame = null;
    this.lastRenderedFrame = null;

    // Clear both charts on mode switch
    this.resetChartsAndTelemetry();

    const isCascade = (mode === "cascade");
    const isAirfoil = (mode === "airfoil");

    document.getElementById("airfoil-controls").classList.toggle("hidden", !isAirfoil);
    document.getElementById("cascade-controls").classList.toggle("hidden", !isCascade);
    document.getElementById("card-turning").classList.toggle("hidden", !isCascade);
    document.getElementById("card-loss").classList.toggle("hidden", !isCascade);

    // Update Cp chart badge state
    const cpBadge = document.getElementById("cp-badge");
    if (cpBadge) {
      cpBadge.textContent = isAirfoil ? "Inviscid / Viscous" : "Airfoil mode only";
    }

    const tag = document.getElementById("view-mode-tag");
    tag.textContent = `MODE: ${mode.toUpperCase()} Flow Simulation`;

    this.updateShapeUI();
    this.sendConfig({ mode: mode });
  }

  updateShapeUI() {
    const isAirfoil = (this.currentMode === "airfoil");
    if (!isAirfoil) return;

    const isNACA = (this.shapeType === "naca");
    const isCyl = (this.shapeType === "rotating_cylinder");
    const hasThick = (this.shapeType === "naca" || this.shapeType === "flat_plate" || this.shapeType === "ellipse");

    const grpCamber = document.getElementById("grp-camber");
    if (grpCamber) grpCamber.classList.toggle("hidden", !isNACA);

    const grpNaca = document.getElementById("grp-naca-code");
    if (grpNaca) grpNaca.classList.toggle("hidden", !isNACA);

    const grpThick = document.getElementById("grp-thickness");
    if (grpThick) grpThick.classList.toggle("hidden", !hasThick);

    const grpSpin = document.getElementById("grp-spin");
    if (grpSpin) grpSpin.classList.toggle("hidden", !isCyl);
  }

  initCharts() {
    // 1. Surface Cp Chart (Nothing OS Monochrome / Signature Red)
    const ctxCp = document.getElementById("chart-cp").getContext("2d");
    this.cpChart = new Chart(ctxCp, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Upper (Suction)",
            data: [],
            borderColor: "#FFFFFF",
            backgroundColor: "rgba(255, 255, 255, 0.05)",
            borderWidth: 2,
            tension: 0.3,
            fill: false,
            pointRadius: 0
          },
          {
            label: "Lower (Pressure)",
            data: [],
            borderColor: "#D71921",
            backgroundColor: "rgba(215, 25, 33, 0.05)",
            borderWidth: 2,
            tension: 0.3,
            fill: false,
            pointRadius: 0
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: {
          x: {
            title: { display: true, text: "x / c", color: "#888888", font: { family: "'Space Mono', monospace", size: 9 } },
            ticks: { color: "#888888", font: { family: "'Space Mono', monospace", size: 9 } },
            grid: { color: "#1F1F1F", borderDash: [2, 4] }
          },
          y: {
            reverse: true,
            title: { display: true, text: "-Cp", color: "#888888", font: { family: "'Space Mono', monospace", size: 9 } },
            ticks: { color: "#888888", font: { family: "'Space Mono', monospace", size: 9 } },
            grid: { color: "#1F1F1F", borderDash: [2, 4] }
          }
        },
        plugins: {
          legend: { labels: { color: "#FFFFFF", font: { family: "'Space Mono', monospace", size: 10 } } }
        }
      }
    });

    // 2. Aerodynamic History Chart (Cl & Cd)
    const ctxHist = document.getElementById("chart-history").getContext("2d");
    this.historyChart = new Chart(ctxHist, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Cl (Lift)",
            data: [],
            borderColor: "#FFFFFF",
            borderWidth: 2,
            tension: 0.2,
            pointRadius: 0
          },
          {
            label: "Cd (Drag)",
            data: [],
            borderColor: "#D71921",
            borderWidth: 2,
            tension: 0.2,
            pointRadius: 0
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: {
          x: { display: false },
          y: {
            ticks: { color: "#888888", font: { family: "'Space Mono', monospace", size: 9 } },
            grid: { color: "#1F1F1F", borderDash: [2, 4] }
          }
        },
        plugins: {
          legend: { labels: { color: "#FFFFFF", font: { family: "'Space Mono', monospace", size: 10 } } }
        }
      }
    });
  }

  connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => console.log("Connected to CFD solver server.");
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "frame") {
          // Store frame for the decoupled render loop
          this.latestFrame = data;
        }
      } catch (err) {
        console.error("Frame parse error:", err);
      }
    };
    this.ws.onclose = () => {
      console.log("WebSocket disconnected. Reconnecting in 2s...");
      setTimeout(() => this.connectWebSocket(), 2000);
    };
  }

  sendAction(action) {
    this.sendWS({ action: action });
  }

  sendConfig(config) {
    this.sendWS({ action: "set_config", config: config });
  }

  sendWS(msg) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  drawSolidGeometry(ctx, w, h, data) {
    ctx.fillStyle = "#000000";
    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth = 1.5;

    // 1. Cylinder Vortex mode: draw analytical circular cylinder
    if (this.currentMode === "cylinder") {
      // Physical domain: [0, 8.0] x [0, 4.0]. Cylinder: center (2.0, 2.0), diameter 0.6 (radius 0.3)
      const cx = (2.0 / 8.0) * w;
      const cy = (1.0 - (2.0 / 4.0)) * h;
      const rx = (0.3 / 8.0) * w;
      const ry = (0.3 / 4.0) * h;

      ctx.beginPath();
      ctx.ellipse(cx, cy, rx, ry, 0, 0, 2 * Math.PI);
      ctx.fill();
      ctx.stroke();
      return;
    }

    // 2. Lid Cavity mode: clean square cavity without internal obstacles
    if (this.currentMode === "cavity") {
      return;
    }

    // 3. Single Airfoil & Turbofan Cascade modes: render polygons
    if (data && data.polygons) {
      this.cachedPolygons = data.polygons;
    }
    const polys = this.cachedPolygons;
    if (!polys || polys.length === 0) return;

    for (let poly of polys) {
      if (poly.length < 3) continue;
      ctx.beginPath();
      for (let k = 0; k < poly.length; k++) {
        const px = poly[k][0] * w;
        const py = (1.0 - poly[k][1]) * h;
        if (k === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }
  }

  startRenderLoop() {
    const loop = () => {
      if (this.latestFrame && this.latestFrame !== this.lastRenderedFrame) {
        this.renderFrame(this.latestFrame);
        this.lastRenderedFrame = this.latestFrame;
      } else if (this.latestFrame && this.showParticles && this.latestFrame.vel_sub) {
        // Redraw particle positions smoothly between physics frame updates
        const w = this.canvas.width;
        const h = this.canvas.height;
        this.ctx.drawImage(this.offscreenCanvas, 0, 0, w, h);

        // Render mode-appropriate solid geometry
        this.drawSolidGeometry(this.ctx, w, h, null);

        this.particles.update(this.latestFrame.vel_sub);
        this.particles.draw(this.ctx, w, h);

        // Render overlay layers
        if (this.showVectors && this.latestFrame.cp_data && this.latestFrame.cp_data.vectors) {
          this.drawPressureVectors(this.ctx, w, h, this.latestFrame.cp_data.vectors);
        }
        if (this.showProbe && this.latestFrame.probe_data) {
          this.drawFlowProbe(this.ctx, w, h, this.latestFrame.probe_data);
        }
      }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  renderFrame(data) {
    // 1. Calculate rendering FPS
    const now = performance.now();
    const delta = (now - this.lastFrameTime) / 1000;
    this.lastFrameTime = now;
    if (delta > 0) {
      this.fps = Math.round(0.9 * this.fps + 0.1 * (1.0 / delta));
      document.getElementById("fps-counter").textContent = `${this.fps} FPS`;
    }

    const nx = data.nx;
    const ny = data.ny;

    // 2. Pre-allocate ImageData once; reallocate only if grid dimensions change
    if (!this.imgData || this.imgData.width !== nx || this.imgData.height !== ny) {
      this.offscreenCanvas.width = nx;
      this.offscreenCanvas.height = ny;
      this.imgData = this.offscreenCtx.createImageData(nx, ny);
      this.pixels32 = new Uint32Array(this.imgData.data.buffer);
    }

    // 3. Ultra-fast direct 32-bit LUT pixel copy (< 0.25 ms)
    const raw = atob(data.field_b64);
    const lut = this.activeLUT;
    const pixels32 = this.pixels32;

    for (let j = 0; j < ny; j++) {
      const srcRow = j * nx;
      const dstRow = (ny - 1 - j) * nx;
      for (let i = 0; i < nx; i++) {
        pixels32[dstRow + i] = lut[raw.charCodeAt(srcRow + i)];
      }
    }
    this.offscreenCtx.putImageData(this.imgData, 0, 0);

    // 4. Render scalar field to main display canvas (completely overwrites canvas pixels)
    const w = this.canvas.width;
    const h = this.canvas.height;
    this.ctx.imageSmoothingEnabled = true;
    this.ctx.drawImage(this.offscreenCanvas, 0, 0, w, h);

    // 5. Render mode-appropriate solid obstacle boundary
    this.drawSolidGeometry(this.ctx, w, h, data);

    // 6. Particle streaklines overlay
    if (this.showParticles && data.vel_sub) {
      this.particles.update(data.vel_sub);
      this.particles.draw(this.ctx, w, h);
    }

    // 7. Surface Pressure Vectors overlay
    if (this.showVectors && data.cp_data && data.cp_data.vectors) {
      this.drawPressureVectors(this.ctx, w, h, data.cp_data.vectors);
    }

    // 8. Flow Field Probe overlay
    if (this.showProbe && data.probe_data) {
      this.drawFlowProbe(this.ctx, w, h, data.probe_data);
    }

    // 9. Update Colorbar labels
    document.getElementById("cb-max").textContent = (data.f_max >= 0 ? "+" : "") + data.f_max.toFixed(2);
    document.getElementById("cb-min").textContent = (data.f_min >= 0 ? "+" : "") + data.f_min.toFixed(2);
    document.getElementById("cb-mid").textContent = ((data.f_max + data.f_min) * 0.5).toFixed(2);

    // 10. Update Telemetry HUD
    document.getElementById("stat-time").textContent = `${data.time.toFixed(2)}s`;
    document.getElementById("stat-dt").textContent = `${data.dt.toFixed(4)}s`;
    document.getElementById("stat-step").textContent = data.step;

    document.getElementById("hud-cl").textContent = (data.cl >= 0 ? "+" : "") + data.cl.toFixed(4);
    document.getElementById("hud-cd").textContent = data.cd.toFixed(4);
    const eff = data.cl / Math.max(data.cd, 1e-4);
    document.getElementById("hud-ld").textContent = eff.toFixed(2);
    document.getElementById("hud-div").textContent = data.rms_div;

    // Dimensional Forces (Newtons)
    if (data.lift_n !== undefined) {
      const elLift = document.getElementById("hud-lift-n");
      if (elLift) elLift.textContent = `${data.lift_n.toFixed(1)} N`;
    }
    if (data.drag_n !== undefined) {
      const elDrag = document.getElementById("hud-drag-n");
      if (elDrag) elDrag.textContent = `${data.drag_n.toFixed(1)} N`;
    }

    // ISA Flight Conditions Telemetry
    if (data.flight_conditions) {
      const fc = data.flight_conditions;
      const elRho = document.getElementById("isa-rho");
      if (elRho) elRho.textContent = `ρ: ${fc.density_kg_m3.toFixed(3)} kg/m³`;
      const elQ = document.getElementById("isa-q");
      if (elQ) elQ.textContent = `q∞: ${Math.round(fc.q_inf_pa)} Pa`;
      const elRe = document.getElementById("isa-re");
      if (elRe) elRe.textContent = `Re: ${fc.reynolds.toExponential(1)}`;
      const elBadge = document.getElementById("isa-badge");
      if (elBadge) elBadge.textContent = fc.altitude_m > 0 ? `${fc.altitude_m}m Alt` : "Sea Level";
    }

    if (data.cascade_metrics && data.cascade_metrics.turning_angle_deg !== undefined) {
      document.getElementById("hud-turning").textContent = `${data.cascade_metrics.turning_angle_deg.toFixed(1)}°`;
      document.getElementById("hud-yp").textContent = data.cascade_metrics.total_pressure_loss_yp.toFixed(3);
    }

    // 11. Throttled Chart.js updates (at most ~6 Hz to eliminate UI thread lag)
    if (now - this.lastChartUpdate > 150) {
      this.lastChartUpdate = now;

      // Update Surface Cp Chart conditionally for active airfoil mode only
      if (this.currentMode === "airfoil") {
        if (data.cp_data && data.cp_data.x_c && data.cp_data.x_c.length > 0) {
          this.cpChart.data.labels = data.cp_data.x_c.map(v => v.toFixed(2));
          this.cpChart.data.datasets[0].data = data.cp_data.cp_upper;
          this.cpChart.data.datasets[1].data = data.cp_data.cp_lower;
          this.cpChart.update("none");
        }
      } else {
        // In non-airfoil modes, clear Cp chart datasets
        if (this.cpChart.data.labels.length > 0) {
          this.cpChart.data.labels = [];
          this.cpChart.data.datasets[0].data = [];
          this.cpChart.data.datasets[1].data = [];
          this.cpChart.update("none");
        }
      }

      // Update Aerodynamic History Chart
      this.clHistory.push(data.cl);
      this.cdHistory.push(data.cd);
      this.timeHistory.push(data.time.toFixed(1));
      if (this.clHistory.length > 50) {
        this.clHistory.shift();
        this.cdHistory.shift();
        this.timeHistory.shift();
      }
      this.historyChart.data.labels = this.timeHistory;
      this.historyChart.data.datasets[0].data = this.clHistory;
      this.historyChart.data.datasets[1].data = this.cdHistory;
      this.historyChart.update("none");
    }
  }

  drawPressureVectors(ctx, w, h, vectors) {
    if (!vectors || vectors.length === 0) return;
    ctx.save();
    for (const [x1, y1, x2, y2, isSuction] of vectors) {
      const sx = x1 * w;
      const sy = (1.0 - y1) * h;
      const tx = x2 * w;
      const ty = (1.0 - y2) * h;

      ctx.strokeStyle = isSuction ? "#FFFFFF" : "#D71921";
      ctx.fillStyle = isSuction ? "#FFFFFF" : "#D71921";
      ctx.lineWidth = 1.5;

      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(tx, ty);
      ctx.stroke();

      // Arrow head at (tx, ty)
      const angle = Math.atan2(ty - sy, tx - sx);
      const headLen = 4;
      ctx.beginPath();
      ctx.moveTo(tx, ty);
      ctx.lineTo(tx - headLen * Math.cos(angle - Math.PI / 6), ty - headLen * Math.sin(angle - Math.PI / 6));
      ctx.lineTo(tx - headLen * Math.cos(angle + Math.PI / 6), ty - headLen * Math.sin(angle + Math.PI / 6));
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  }

  drawFlowProbe(ctx, w, h, probeData) {
    if (!this.showProbe || !probeData) return;
    const px = probeData.norm_x * w;
    const py = (1.0 - probeData.norm_y) * h;

    ctx.save();
    // Dotted crosshair hairline
    ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
    ctx.setLineDash([2, 3]);
    ctx.lineWidth = 1;

    ctx.beginPath();
    ctx.moveTo(0, py);
    ctx.lineTo(w, py);
    ctx.moveTo(px, 0);
    ctx.lineTo(px, h);
    ctx.stroke();

    // Target ring
    ctx.setLineDash([]);
    ctx.strokeStyle = probeData.in_solid ? "#D71921" : "#FFFFFF";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(px, py, 7, 0, 2 * Math.PI);
    ctx.stroke();

    // Center dot
    ctx.fillStyle = probeData.in_solid ? "#D71921" : "#FFFFFF";
    ctx.beginPath();
    ctx.arc(px, py, 2, 0, 2 * Math.PI);
    ctx.fill();
    ctx.restore();

    // Update Probe HUD elements
    const hud = document.getElementById("flow-probe-hud");
    if (hud) {
      hud.classList.remove("hidden");
      const xcEl = document.getElementById("probe-xc");
      if (xcEl) xcEl.textContent = (probeData.x_c >= 0 ? "+" : "") + probeData.x_c.toFixed(2);
      const velEl = document.getElementById("probe-vel");
      if (velEl) velEl.textContent = `${probeData.vel_mps.toFixed(1)} m/s (${probeData.vel_mag.toFixed(2)} U∞)`;
      const pEl = document.getElementById("probe-p");
      if (pEl) pEl.textContent = `${(probeData.p_dim_pa / 1000).toFixed(1)} kPa`;
      const cpEl = document.getElementById("probe-cp");
      if (cpEl) cpEl.textContent = (probeData.p_coeff >= 0 ? "+" : "") + probeData.p_coeff.toFixed(2);
      const vortEl = document.getElementById("probe-vort");
      if (vortEl) vortEl.textContent = (probeData.vorticity >= 0 ? "+" : "") + probeData.vorticity.toFixed(1) + " s⁻¹";
      const zoneEl = document.getElementById("probe-zone");
      if (zoneEl) {
        zoneEl.textContent = probeData.in_solid ? "SOLID OBSTACLE" : "FLUID FIELD";
        zoneEl.style.color = probeData.in_solid ? "#D71921" : "#FFFFFF";
      }
    }
  }

  async runAlphaSweep() {
    const modal = document.getElementById("sweep-modal");
    const status = document.getElementById("sweep-status");
    if (!modal || !status) return;

    modal.classList.remove("hidden");
    status.textContent = "RUNNING NAVIER-STOKES α SWEEP [-4° TO +16°]...";
    status.style.color = "#FFFFFF";

    const camberInput = document.getElementById("slider-camber");
    const thickInput = document.getElementById("slider-thickness");
    const nacaInput = document.getElementById("input-naca");
    const reInput = document.getElementById("slider-re");

    const camberVal = camberInput ? parseFloat(camberInput.value) / 100.0 : 0.0;
    const thickVal = thickInput ? parseFloat(thickInput.value) / 100.0 : 0.12;
    const nacaCode = nacaInput ? nacaInput.value.trim() : "0012";
    const reynoldsVal = reInput ? parseFloat(reInput.value) : 500.0;

    try {
      const response = await fetch("/api/sweep/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shape_type: this.shapeType || "naca",
          naca_code: nacaCode,
          camber: camberVal,
          thickness: thickVal,
          reynolds: reynoldsVal,
          alpha_start: -4.0,
          alpha_end: 16.0,
          alpha_step: 2.0
        })
      });

      if (!response.ok) throw new Error("Sweep failed on server");
      const data = await response.json();

      status.textContent = "ALPHA SWEEP COMPLETE // READY";
      status.style.color = "#D71921";

      document.getElementById("stat-stall-alpha").textContent = `${data.stall_alpha.toFixed(1)}°`;
      document.getElementById("stat-cl-max").textContent = `${data.cl_max.toFixed(3)}`;
      document.getElementById("stat-zero-alpha").textContent = (data.zero_lift_alpha !== null) ? `${data.zero_lift_alpha.toFixed(1)}°` : "N/A";

      this.renderSweepCharts(data.sweep_data);
    } catch (err) {
      status.textContent = "ERROR RUNNING SWEEP: " + err.message;
      status.style.color = "#D71921";
    }
  }

  renderSweepCharts(sweepData) {
    if (!sweepData || sweepData.length === 0) return;

    const alphas = sweepData.map(d => `${d.alpha}°`);
    const cls = sweepData.map(d => d.cl);
    const cds = sweepData.map(d => d.cd);

    // 1. Lift Curve Chart (Cl vs alpha)
    const ctxLift = document.getElementById("chart-sweep-lift").getContext("2d");
    if (this.sweepLiftChart) this.sweepLiftChart.destroy();
    this.sweepLiftChart = new Chart(ctxLift, {
      type: "line",
      data: {
        labels: alphas,
        datasets: [{
          label: "Lift Coefficient (Cl)",
          data: cls,
          borderColor: "#FFFFFF",
          backgroundColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 2,
          pointBackgroundColor: "#D71921",
          pointRadius: 4,
          tension: 0.2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            title: { display: true, text: "Angle of Attack (α)", color: "#888888", font: { family: "'Space Mono', monospace", size: 10 } },
            ticks: { color: "#888888", font: { family: "'Space Mono', monospace", size: 9 } },
            grid: { color: "#1F1F1F", borderDash: [2, 4] }
          },
          y: {
            title: { display: true, text: "Lift Coeff (Cl)", color: "#888888", font: { family: "'Space Mono', monospace", size: 10 } },
            ticks: { color: "#888888", font: { family: "'Space Mono', monospace", size: 9 } },
            grid: { color: "#1F1F1F", borderDash: [2, 4] }
          }
        },
        plugins: {
          legend: { labels: { color: "#FFFFFF", font: { family: "'Space Mono', monospace", size: 10 } } }
        }
      }
    });

    // 2. Drag Polar Chart (Cl vs Cd)
    const ctxPolar = document.getElementById("chart-sweep-polar").getContext("2d");
    if (this.sweepPolarChart) this.sweepPolarChart.destroy();
    const polarPoints = sweepData.map(d => ({ x: d.cd, y: d.cl }));
    this.sweepPolarChart = new Chart(ctxPolar, {
      type: "scatter",
      data: {
        datasets: [{
          label: "Drag Polar (Cl vs Cd)",
          data: polarPoints,
          borderColor: "#D71921",
          backgroundColor: "rgba(215, 25, 33, 0.4)",
          showLine: true,
          borderWidth: 2,
          pointRadius: 4,
          tension: 0.2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            title: { display: true, text: "Drag Coeff (Cd)", color: "#888888", font: { family: "'Space Mono', monospace", size: 10 } },
            ticks: { color: "#888888", font: { family: "'Space Mono', monospace", size: 9 } },
            grid: { color: "#1F1F1F", borderDash: [2, 4] }
          },
          y: {
            title: { display: true, text: "Lift Coeff (Cl)", color: "#888888", font: { family: "'Space Mono', monospace", size: 10 } },
            ticks: { color: "#888888", font: { family: "'Space Mono', monospace", size: 9 } },
            grid: { color: "#1F1F1F", borderDash: [2, 4] }
          }
        },
        plugins: {
          legend: { labels: { color: "#FFFFFF", font: { family: "'Space Mono', monospace", size: 10 } } }
        }
      }
    });
  }
}

// Instantiate on page load
window.addEventListener("DOMContentLoaded", () => {
  window.app = new CFDApp();
});
