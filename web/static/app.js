// 2D Navier-Stokes CFD Simulator Frontend Controller

// Colormap lookup tables (256 RGB values)
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

// Interpolate RGB from palette
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
        // Respawn near inlet
        p.x = Math.random() * 0.05;
        p.y = Math.random();
        p.age = 0;
        continue;
      }

      // Sample velocity at (p.x, p.y)
      const ix = Math.min(nx - 1, Math.max(0, Math.floor(p.x * nx)));
      const iy = Math.min(ny - 1, Math.max(0, Math.floor(p.y * ny)));
      const idx = iy * nx + ix;

      const u = velSub.u[idx] || 0;
      const v = velSub.v[idx] || 0;

      // Advect position
      p.x += u * 0.015;
      p.y += v * 0.015;
    }
  }

  draw(ctx, width, height) {
    ctx.fillStyle = "rgba(255, 255, 255, 0.65)";
    for (let p of this.particles) {
      const alpha = Math.sin((p.age / p.maxAge) * Math.PI) * 0.7;
      ctx.fillStyle = `rgba(255, 255, 255, ${alpha.toFixed(2)})`;
      const px = p.x * width;
      const py = (1.0 - p.y) * height; // Invert y for canvas coordinates
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

    this.particles = new ParticleSystem(300);
    this.showParticles = true;
    this.colormap = "viridis";
    this.ws = null;
    this.lastFrameTime = performance.now();
    this.fps = 30;

    // Charts
    this.cpChart = null;
    this.historyChart = null;
    this.clHistory = [];
    this.cdHistory = [];
    this.timeHistory = [];

    this.initUI();
    this.initCharts();
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
    document.getElementById("btn-reset").addEventListener("click", () => this.sendAction("reset"));

    // Sliders
    const sliderRe = document.getElementById("slider-re");
    sliderRe.addEventListener("input", (e) => {
      document.getElementById("val-re").textContent = e.target.value;
      this.sendConfig({ reynolds: parseFloat(e.target.value) });
    });

    const sliderAoA = document.getElementById("slider-aoa");
    sliderAoA.addEventListener("input", (e) => {
      const val = parseFloat(e.target.value);
      document.getElementById("val-aoa").textContent = (val >= 0 ? "+" : "") + val.toFixed(1) + "°";
      this.sendConfig({ alpha_deg: val });
    });

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

    // Cascade sliders
    document.getElementById("slider-stagger").addEventListener("input", (e) => {
      document.getElementById("val-stagger").textContent = e.target.value + "°";
      this.sendConfig({ cascade_stagger: parseFloat(e.target.value) });
    });

    document.getElementById("slider-pitch").addEventListener("input", (e) => {
      document.getElementById("val-pitch").textContent = parseFloat(e.target.value).toFixed(2);
      this.sendConfig({ cascade_pitch: parseFloat(e.target.value) });
    });

    document.getElementById("slider-inlet-angle").addEventListener("input", (e) => {
      document.getElementById("val-inlet-angle").textContent = e.target.value + "°";
      this.sendConfig({ cascade_inlet_angle: parseFloat(e.target.value) });
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
      this.updateColorbarGradient();
    });

    document.getElementById("toggle-particles").addEventListener("change", (e) => {
      this.showParticles = e.target.checked;
    });

    document.getElementById("select-resolution").addEventListener("change", (e) => {
      this.sendConfig({ resolution: e.target.value });
    });

    this.updateColorbarGradient();
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

  switchMode(mode) {
    const isCascade = (mode === "cascade");
    const isAirfoil = (mode === "airfoil");

    document.getElementById("airfoil-controls").classList.toggle("hidden", !isAirfoil);
    document.getElementById("cascade-controls").classList.toggle("hidden", !isCascade);
    document.getElementById("card-turning").classList.toggle("hidden", !isCascade);
    document.getElementById("card-loss").classList.toggle("hidden", !isCascade);

    const tag = document.getElementById("view-mode-tag");
    tag.textContent = `MODE: ${mode.toUpperCase()} Flow Simulation`;

    this.sendConfig({ mode: mode });
  }

  initCharts() {
    // 1. Cp vs x/c distribution chart
    const ctxCp = document.getElementById("chart-cp").getContext("2d");
    this.cpChart = new Chart(ctxCp, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Upper (Suction)",
            data: [],
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.1)",
            borderWidth: 2,
            tension: 0.3,
            fill: false,
            pointRadius: 0
          },
          {
            label: "Lower (Pressure)",
            data: [],
            borderColor: "#f59e0b",
            backgroundColor: "rgba(245, 158, 11, 0.1)",
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
            title: { display: true, text: "x / c", color: "#9ca3af", font: { size: 10 } },
            ticks: { color: "#6b7280", font: { size: 9 } },
            grid: { color: "#1f2937" }
          },
          y: {
            // Standard aerodynamic convention: invert y so -Cp (suction) is pointing up
            reverse: true,
            title: { display: true, text: "-Cp", color: "#9ca3af", font: { size: 10 } },
            ticks: { color: "#6b7280", font: { size: 9 } },
            grid: { color: "#1f2937" }
          }
        },
        plugins: {
          legend: { labels: { color: "#e5e7eb", font: { size: 10 } } }
        }
      }
    });

    // 2. Aerodynamic History Chart (Cl and Cd)
    const ctxHist = document.getElementById("chart-history").getContext("2d");
    this.historyChart = new Chart(ctxHist, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Cl (Lift)",
            data: [],
            borderColor: "#10b981",
            borderWidth: 2,
            tension: 0.2,
            pointRadius: 0
          },
          {
            label: "Cd (Drag)",
            data: [],
            borderColor: "#ef4444",
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
            ticks: { color: "#6b7280", font: { size: 9 } },
            grid: { color: "#1f2937" }
          }
        },
        plugins: {
          legend: { labels: { color: "#e5e7eb", font: { size: 10 } } }
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
      const data = JSON.parse(event.data);
      if (data.type === "frame") {
        this.renderFrame(data);
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

  renderFrame(data) {
    // Calculate rendering FPS
    const now = performance.now();
    const delta = (now - this.lastFrameTime) / 1000;
    this.lastFrameTime = now;
    if (delta > 0) {
      this.fps = Math.round(0.9 * this.fps + 0.1 * (1.0 / delta));
      document.getElementById("fps-counter").textContent = `${this.fps} FPS`;
    }

    // 1. Decode base64 uint8 scalar field
    const raw = atob(data.field_b64);
    const len = raw.length;
    const nx = data.nx;
    const ny = data.ny;

    if (this.offscreenCanvas.width !== nx || this.offscreenCanvas.height !== ny) {
      this.offscreenCanvas.width = nx;
      this.offscreenCanvas.height = ny;
    }

    const imgData = this.offscreenCtx.createImageData(nx, ny);
    const pixels = imgData.data;

    // Fast colormap mapping: invert row index so y=0 is bottom
    for (let j = 0; j < ny; j++) {
      const canvasRow = ny - 1 - j;
      for (let i = 0; i < nx; i++) {
        const srcIdx = j * nx + i;
        const normVal = raw.charCodeAt(srcIdx) / 255.0;
        const rgb = sampleColormap(this.colormap, normVal);

        const dstIdx = (canvasRow * nx + i) * 4;
        pixels[dstIdx] = rgb[0];
        pixels[dstIdx + 1] = rgb[1];
        pixels[dstIdx + 2] = rgb[2];
        pixels[dstIdx + 3] = 255;
      }
    }

    this.offscreenCtx.putImageData(imgData, 0, 0);

    // 2. Render to main canvas
    const w = this.canvas.width;
    const h = this.canvas.height;
    this.ctx.imageSmoothingEnabled = true;
    this.ctx.drawImage(this.offscreenCanvas, 0, 0, w, h);

    // 3. Render solid body contours (polygons)
    if (data.polygons && data.polygons.length > 0) {
      this.ctx.fillStyle = "#0f172a";
      this.ctx.strokeStyle = "#38bdf8";
      this.ctx.lineWidth = 2.0;

      for (let poly of data.polygons) {
        if (poly.length < 3) continue;
        this.ctx.beginPath();
        for (let k = 0; k < poly.length; k++) {
          const px = poly[k][0] * w;
          const py = (1.0 - poly[k][1]) * h;
          if (k === 0) this.ctx.moveTo(px, py);
          else this.ctx.lineTo(px, py);
        }
        this.ctx.closePath();
        this.ctx.fill();
        this.ctx.stroke();
      }
    }

    // 4. Update and render particle streaklines overlay
    if (this.showParticles && data.vel_sub) {
      this.particles.update(data.vel_sub);
      this.particles.draw(this.ctx, w, h);
    }

    // 5. Update Colorbar labels
    document.getElementById("cb-max").textContent = (data.f_max >= 0 ? "+" : "") + data.f_max.toFixed(2);
    document.getElementById("cb-min").textContent = (data.f_min >= 0 ? "+" : "") + data.f_min.toFixed(2);
    document.getElementById("cb-mid").textContent = ((data.f_max + data.f_min) * 0.5).toFixed(2);

    // 6. Update Telemetry HUD
    document.getElementById("stat-time").textContent = `${data.time.toFixed(2)}s`;
    document.getElementById("stat-dt").textContent = `${data.dt.toFixed(4)}s`;
    document.getElementById("stat-step").textContent = data.step;

    document.getElementById("hud-cl").textContent = (data.cl >= 0 ? "+" : "") + data.cl.toFixed(4);
    document.getElementById("hud-cd").textContent = data.cd.toFixed(4);
    const eff = data.cl / Math.max(data.cd, 1e-4);
    document.getElementById("hud-ld").textContent = eff.toFixed(2);
    document.getElementById("hud-div").textContent = data.rms_div;

    if (data.cascade_metrics && data.cascade_metrics.turning_angle_deg !== undefined) {
      document.getElementById("hud-turning").textContent = `${data.cascade_metrics.turning_angle_deg.toFixed(1)}°`;
      document.getElementById("hud-yp").textContent = data.cascade_metrics.total_pressure_loss_yp.toFixed(3);
    }

    // 7. Update Cp chart
    if (data.cp_data && data.cp_data.x_c && data.cp_data.x_c.length > 0) {
      this.cpChart.data.labels = data.cp_data.x_c.map(v => v.toFixed(2));
      this.cpChart.data.datasets[0].data = data.cp_data.cp_upper;
      this.cpChart.data.datasets[1].data = data.cp_data.cp_lower;
      this.cpChart.update("none");
    }

    // 8. Update Aerodynamic history chart
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

// Instantiate on page load
window.addEventListener("DOMContentLoaded", () => {
  window.app = new CFDApp();
});
