/* eslint-disable no-undef */
(function () {
  if (typeof window.THREE === "undefined") {
    return;
  }

  class TouchTexture {
    constructor() {
      this.size = 64;
      this.width = this.height = this.size;
      this.maxAge = 64;
      this.radius = 0.25 * this.size;
      this.speed = 1 / this.maxAge;
      this.trail = [];
      this.last = null;
      this.initTexture();
    }

    initTexture() {
      this.canvas = document.createElement("canvas");
      this.canvas.width = this.width;
      this.canvas.height = this.height;
      this.ctx = this.canvas.getContext("2d");
      this.ctx.fillStyle = "black";
      this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
      this.texture = new THREE.Texture(this.canvas);
    }

    clear() {
      this.ctx.fillStyle = "black";
      this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    addTouch(point) {
      let force = 0;
      let vx = 0;
      let vy = 0;
      if (this.last) {
        const dx = point.x - this.last.x;
        const dy = point.y - this.last.y;
        if (dx === 0 && dy === 0) return;
        const dd = dx * dx + dy * dy;
        const d = Math.sqrt(dd);
        vx = dx / d;
        vy = dy / d;
        force = Math.min(dd * 20000, 2.0);
      }

      this.last = { x: point.x, y: point.y };
      this.trail.push({ x: point.x, y: point.y, age: 0, force, vx, vy });
    }

    drawPoint(point) {
      const pos = {
        x: point.x * this.width,
        y: (1 - point.y) * this.height,
      };

      let intensity = 1;
      if (point.age < this.maxAge * 0.3) {
        intensity = Math.sin((point.age / (this.maxAge * 0.3)) * (Math.PI / 2));
      } else {
        const t = 1 - (point.age - this.maxAge * 0.3) / (this.maxAge * 0.7);
        intensity = -t * (t - 2);
      }
      intensity *= point.force;

      const offset = this.size * 5;
      const color = `${((point.vx + 1) / 2) * 255}, ${((point.vy + 1) / 2) * 255}, ${intensity * 255}`;
      this.ctx.shadowOffsetX = offset;
      this.ctx.shadowOffsetY = offset;
      this.ctx.shadowBlur = this.radius;
      this.ctx.shadowColor = `rgba(${color},${0.2 * intensity})`;

      this.ctx.beginPath();
      this.ctx.fillStyle = "rgba(255,0,0,1)";
      this.ctx.arc(pos.x - offset, pos.y - offset, this.radius, 0, Math.PI * 2);
      this.ctx.fill();
    }

    update() {
      this.clear();
      for (let i = this.trail.length - 1; i >= 0; i--) {
        const point = this.trail[i];
        const f = point.force * this.speed * (1 - point.age / this.maxAge);
        point.x += point.vx * f;
        point.y += point.vy * f;
        point.age += 1;
        if (point.age > this.maxAge) {
          this.trail.splice(i, 1);
          continue;
        }
        this.drawPoint(point);
      }
      this.texture.needsUpdate = true;
    }
  }

  class GradientBackground {
    constructor(sceneManager) {
      this.sceneManager = sceneManager;
      this.mesh = null;
      this.uniforms = {
        uTime: { value: 0 },
        uResolution: {
          value: new THREE.Vector2(window.innerWidth, window.innerHeight),
        },
        uColor1: { value: new THREE.Vector3(0.945, 0.353, 0.133) },
        uColor2: { value: new THREE.Vector3(0.039, 0.055, 0.153) },
        uColor3: { value: new THREE.Vector3(0.945, 0.353, 0.133) },
        uColor4: { value: new THREE.Vector3(0.039, 0.055, 0.153) },
        uColor5: { value: new THREE.Vector3(0.945, 0.353, 0.133) },
        uColor6: { value: new THREE.Vector3(0.039, 0.055, 0.153) },
        uSpeed: { value: 0.95 },
        uIntensity: { value: 1.22 },
        uTouchTexture: { value: null },
        uGrainIntensity: { value: 0.035 },
        uDarkNavy: { value: new THREE.Vector3(0.039, 0.055, 0.153) },
      };
    }

    init() {
      const viewSize = this.sceneManager.getViewSize();
      const geometry = new THREE.PlaneGeometry(
        viewSize.width,
        viewSize.height,
        1,
        1,
      );
      const material = new THREE.ShaderMaterial({
        uniforms: this.uniforms,
        vertexShader: `
          varying vec2 vUv;
          void main() {
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position.xyz, 1.0);
            vUv = uv;
          }
        `,
        fragmentShader: `
          uniform float uTime;
          uniform vec2 uResolution;
          uniform vec3 uColor1;
          uniform vec3 uColor2;
          uniform vec3 uColor3;
          uniform vec3 uColor4;
          uniform vec3 uColor5;
          uniform vec3 uColor6;
          uniform float uSpeed;
          uniform float uIntensity;
          uniform sampler2D uTouchTexture;
          uniform float uGrainIntensity;
          uniform vec3 uDarkNavy;
          varying vec2 vUv;

          float grain(vec2 uv, float time) {
            vec2 grainUv = uv * uResolution * 0.5;
            float g = fract(sin(dot(grainUv + time, vec2(12.9898, 78.233))) * 43758.5453);
            return g * 2.0 - 1.0;
          }

          vec3 gradientColor(vec2 uv, float time) {
            vec2 c1 = vec2(0.5 + sin(time * uSpeed * 0.4) * 0.42, 0.5 + cos(time * uSpeed * 0.5) * 0.42);
            vec2 c2 = vec2(0.5 + cos(time * uSpeed * 0.6) * 0.48, 0.5 + sin(time * uSpeed * 0.45) * 0.48);
            vec2 c3 = vec2(0.5 + sin(time * uSpeed * 0.35) * 0.46, 0.5 + cos(time * uSpeed * 0.55) * 0.46);
            vec2 c4 = vec2(0.5 + cos(time * uSpeed * 0.5) * 0.4, 0.5 + sin(time * uSpeed * 0.4) * 0.4);
            vec2 c5 = vec2(0.5 + sin(time * uSpeed * 0.7) * 0.35, 0.5 + cos(time * uSpeed * 0.6) * 0.35);
            vec2 c6 = vec2(0.5 + cos(time * uSpeed * 0.45) * 0.5, 0.5 + sin(time * uSpeed * 0.65) * 0.5);

            float d1 = 1.0 - smoothstep(0.0, 0.45, length(uv - c1));
            float d2 = 1.0 - smoothstep(0.0, 0.45, length(uv - c2));
            float d3 = 1.0 - smoothstep(0.0, 0.45, length(uv - c3));
            float d4 = 1.0 - smoothstep(0.0, 0.45, length(uv - c4));
            float d5 = 1.0 - smoothstep(0.0, 0.45, length(uv - c5));
            float d6 = 1.0 - smoothstep(0.0, 0.45, length(uv - c6));

            vec3 color = vec3(0.0);
            color += uColor1 * d1 * (0.55 + 0.45 * sin(time * uSpeed));
            color += uColor2 * d2 * (0.55 + 0.45 * cos(time * uSpeed * 1.2));
            color += uColor3 * d3 * (0.55 + 0.45 * sin(time * uSpeed * 0.8));
            color += uColor4 * d4 * (0.55 + 0.45 * cos(time * uSpeed * 1.3));
            color += uColor5 * d5 * (0.55 + 0.45 * sin(time * uSpeed * 1.1));
            color += uColor6 * d6 * (0.55 + 0.45 * cos(time * uSpeed * 0.9));

            color = clamp(color, vec3(0.0), vec3(1.0)) * uIntensity;
            float luminance = dot(color, vec3(0.299, 0.587, 0.114));
            color = mix(vec3(luminance), color, 1.35);
            color = pow(color, vec3(0.92));
            float brightness = length(color);
            color = mix(uDarkNavy, color, max(brightness * 1.2, 0.15));
            return clamp(color, vec3(0.0), vec3(1.0));
          }

          void main() {
            vec2 uv = vUv;
            vec4 touchTex = texture2D(uTouchTexture, uv);
            float vx = -(touchTex.r * 2.0 - 1.0);
            float vy = -(touchTex.g * 2.0 - 1.0);
            float intensity = touchTex.b;
            uv.x += vx * 0.34 * intensity;
            uv.y += vy * 0.34 * intensity;

            float dist = length(uv - vec2(0.5));
            float ripple = sin(dist * 14.0 - uTime * 2.0) * 0.018 * intensity;
            float wave = sin(dist * 10.0 - uTime * 1.4) * 0.014 * intensity;
            uv += vec2(ripple + wave);

            vec3 color = gradientColor(uv, uTime);
            color += grain(uv, uTime) * uGrainIntensity;
            color.r += sin(uTime * 0.5) * 0.02;
            color.g += cos(uTime * 0.7) * 0.02;
            color.b += sin(uTime * 0.6) * 0.02;
            gl_FragColor = vec4(clamp(color, vec3(0.0), vec3(1.0)), 1.0);
          }
        `,
      });

      this.mesh = new THREE.Mesh(geometry, material);
      this.mesh.position.z = 0;
      this.sceneManager.scene.add(this.mesh);
    }

    update(delta) {
      this.uniforms.uTime.value += delta;
    }

    onResize(width, height) {
      const viewSize = this.sceneManager.getViewSize();
      if (this.mesh) {
        this.mesh.geometry.dispose();
        this.mesh.geometry = new THREE.PlaneGeometry(
          viewSize.width,
          viewSize.height,
          1,
          1,
        );
      }
      this.uniforms.uResolution.value.set(width, height);
    }
  }

  class LiquidThemeApp {
    constructor() {
      this.renderer = new THREE.WebGLRenderer({
        antialias: true,
        powerPreference: "high-performance",
        alpha: false,
        stencil: false,
        depth: false,
      });
      this.renderer.setSize(window.innerWidth, window.innerHeight);
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      this.renderer.domElement.id = "webGLApp";
      document.body.prepend(this.renderer.domElement);

      this.camera = new THREE.PerspectiveCamera(
        45,
        window.innerWidth / window.innerHeight,
        0.1,
        10000,
      );
      this.camera.position.z = 50;
      this.scene = new THREE.Scene();
      this.scene.background = new THREE.Color(0x0a0e27);
      this.clock = new THREE.Clock();

      this.touchTexture = new TouchTexture();
      this.gradientBackground = new GradientBackground(this);
      this.gradientBackground.uniforms.uTouchTexture.value =
        this.touchTexture.texture;
      this.themeModeKey = "healthbuddy.themeMode";
      this.themeSchemeKey = "healthbuddy.themeScheme";

      this.colorSchemes = {
        1: {
          color1: new THREE.Vector3(0.945, 0.353, 0.133),
          color2: new THREE.Vector3(0.039, 0.055, 0.153),
          color3: new THREE.Vector3(0.945, 0.353, 0.133),
          color4: new THREE.Vector3(0.039, 0.055, 0.153),
          color5: new THREE.Vector3(0.945, 0.353, 0.133),
          color6: new THREE.Vector3(0.039, 0.055, 0.153),
        },
        2: {
          color1: new THREE.Vector3(1.0, 0.424, 0.314),
          color2: new THREE.Vector3(0.251, 0.878, 0.816),
          color3: new THREE.Vector3(1.0, 0.424, 0.314),
          color4: new THREE.Vector3(0.251, 0.878, 0.816),
          color5: new THREE.Vector3(1.0, 0.424, 0.314),
          color6: new THREE.Vector3(0.251, 0.878, 0.816),
        },
        3: {
          color1: new THREE.Vector3(0.945, 0.353, 0.133),
          color2: new THREE.Vector3(0.039, 0.055, 0.153),
          color3: new THREE.Vector3(0.251, 0.878, 0.816),
          color4: new THREE.Vector3(0.945, 0.353, 0.133),
          color5: new THREE.Vector3(0.039, 0.055, 0.153),
          color6: new THREE.Vector3(0.251, 0.878, 0.816),
        },
        4: {
          color1: new THREE.Vector3(0.949, 0.4, 0.2),
          color2: new THREE.Vector3(0.176, 0.42, 0.427),
          color3: new THREE.Vector3(0.82, 0.686, 0.612),
          color4: new THREE.Vector3(0.949, 0.4, 0.2),
          color5: new THREE.Vector3(0.176, 0.42, 0.427),
          color6: new THREE.Vector3(0.82, 0.686, 0.612),
        },
        5: {
          color1: new THREE.Vector3(0.945, 0.353, 0.133),
          color2: new THREE.Vector3(0.0, 0.259, 0.22),
          color3: new THREE.Vector3(0.945, 0.353, 0.133),
          color4: new THREE.Vector3(0.0, 0.0, 0.0),
          color5: new THREE.Vector3(0.945, 0.353, 0.133),
          color6: new THREE.Vector3(0.0, 0.0, 0.0),
        },
      };

      this.init();
      this.wireThemeControls();
      this.wireCursor();
    }

    getViewSize() {
      const fovInRadians = (this.camera.fov * Math.PI) / 180;
      const height = Math.abs(
        this.camera.position.z * Math.tan(fovInRadians / 2) * 2,
      );
      return { width: height * this.camera.aspect, height };
    }

    setColorScheme(scheme) {
      const colors = this.colorSchemes[scheme];
      if (!colors) return;
      const u = this.gradientBackground.uniforms;
      u.uColor1.value.copy(colors.color1);
      u.uColor2.value.copy(colors.color2);
      u.uColor3.value.copy(colors.color3);
      u.uColor4.value.copy(colors.color4);
      u.uColor5.value.copy(colors.color5);
      u.uColor6.value.copy(colors.color6);
      localStorage.setItem(this.themeSchemeKey, String(scheme));
      this.updateColorPickers();
    }

    setThemeMode(mode, persist = true) {
      const isClassic = mode === "classic";
      document.body.classList.toggle("classic-mode", isClassic);

      if (this.renderer && this.renderer.domElement) {
        this.renderer.domElement.style.display = isClassic ? "none" : "block";
      }

      const classicBtn = document.getElementById("classicModeBtn");
      if (classicBtn) {
        classicBtn.classList.toggle("active", isClassic);
      }

      if (persist) {
        localStorage.setItem(
          this.themeModeKey,
          isClassic ? "classic" : "liquid",
        );
      }
    }

    update(delta) {
      this.touchTexture.update();
      this.gradientBackground.update(delta);
    }

    render() {
      const delta = Math.min(this.clock.getDelta(), 0.1);
      this.renderer.render(this.scene, this.camera);
      this.update(delta);
    }

    tick() {
      this.render();
      requestAnimationFrame(() => this.tick());
    }

    onResize() {
      this.camera.aspect = window.innerWidth / window.innerHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(window.innerWidth, window.innerHeight);
      this.gradientBackground.onResize(window.innerWidth, window.innerHeight);
    }

    onMouseMove(ev) {
      this.touchTexture.addTouch({
        x: ev.clientX / window.innerWidth,
        y: 1 - ev.clientY / window.innerHeight,
      });
    }

    init() {
      this.gradientBackground.init();
      const savedSchemeRaw = parseInt(
        localStorage.getItem(this.themeSchemeKey) || "1",
        10,
      );
      const savedScheme = this.colorSchemes[savedSchemeRaw]
        ? savedSchemeRaw
        : 1;
      this.setColorScheme(savedScheme);
      const savedMode = localStorage.getItem(this.themeModeKey) || "liquid";
      this.setThemeMode(savedMode, false);
      this.tick();
      window.addEventListener("resize", () => this.onResize());
      window.addEventListener("mousemove", (ev) => this.onMouseMove(ev));
      window.addEventListener(
        "touchmove",
        (ev) => {
          const t = ev.touches && ev.touches[0];
          if (t) this.onMouseMove({ clientX: t.clientX, clientY: t.clientY });
        },
        { passive: true },
      );
    }

    static rgbToHex(v3) {
      const toHex = (n) => {
        const hex = Math.round(Math.max(0, Math.min(1, n)) * 255).toString(16);
        return hex.length === 1 ? `0${hex}` : hex;
      };
      return `#${toHex(v3.x)}${toHex(v3.y)}${toHex(v3.z)}`.toUpperCase();
    }

    static hexToRgb(hex) {
      const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
      if (!m) return null;
      return {
        r: parseInt(m[1], 16) / 255,
        g: parseInt(m[2], 16) / 255,
        b: parseInt(m[3], 16) / 255,
      };
    }

    updateColorPickers() {
      const u = this.gradientBackground.uniforms;
      const arr = [
        u.uColor1.value,
        u.uColor2.value,
        u.uColor3.value,
        u.uColor4.value,
        u.uColor5.value,
        u.uColor6.value,
      ];
      arr.forEach((color, idx) => {
        const n = idx + 1;
        const picker = document.getElementById(`colorPicker${n}`);
        const value = document.getElementById(`colorValue${n}`);
        if (!picker || !value) return;
        const hex = LiquidThemeApp.rgbToHex(color);
        picker.value = hex;
        value.value = hex;
      });
    }

    wireThemeControls() {
      const toolbar = document.getElementById("themeToolbar");
      const menuToggle = document.getElementById("themeMenuToggle");
      if (toolbar && menuToggle) {
        menuToggle.addEventListener("click", () => {
          toolbar.classList.toggle("open");
        });

        document.addEventListener("click", (e) => {
          if (!toolbar.contains(e.target)) {
            toolbar.classList.remove("open");
          }
        });
      }

      const classicBtn = document.getElementById("classicModeBtn");
      if (classicBtn) {
        classicBtn.addEventListener("click", () => {
          this.setThemeMode("classic", true);
        });
      }

      const colorButtons = document.querySelectorAll(".color-btn");
      colorButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
          const scheme = parseInt(btn.dataset.scheme, 10);
          this.setThemeMode("liquid", true);
          this.setColorScheme(scheme);
          colorButtons.forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
        });
      });

      const panel = document.getElementById("colorAdjusterPanel");
      const toggle = document.getElementById("toggleAdjusterBtn");
      const close = document.getElementById("closeAdjusterBtn");
      const exportBtn = document.getElementById("exportAllBtn");

      if (toggle && panel) {
        toggle.addEventListener("click", () => {
          panel.classList.toggle("open");
          if (panel.classList.contains("open")) {
            this.updateColorPickers();
            toggle.style.display = "none";
          } else {
            toggle.style.display = "block";
          }
        });
      }

      if (close && panel && toggle) {
        close.addEventListener("click", () => {
          panel.classList.remove("open");
          toggle.style.display = "block";
        });
      }

      for (let i = 1; i <= 6; i++) {
        const picker = document.getElementById(`colorPicker${i}`);
        const value = document.getElementById(`colorValue${i}`);
        if (!picker || !value) continue;

        picker.addEventListener("input", (e) => {
          const rgb = LiquidThemeApp.hexToRgb(e.target.value);
          if (!rgb) return;
          const uniform = this.gradientBackground.uniforms[`uColor${i}`];
          if (!uniform) return;
          uniform.value.set(rgb.r, rgb.g, rgb.b);
          value.value = e.target.value.toUpperCase();
        });
      }

      document.querySelectorAll(".copy-btn").forEach((btn) => {
        btn.addEventListener("click", async (e) => {
          const idx = e.currentTarget.dataset.copy;
          const value = document.getElementById(`colorValue${idx}`);
          if (!value) return;
          await navigator.clipboard.writeText(value.value);
          e.currentTarget.textContent = "Copied!";
          e.currentTarget.classList.add("copied");
          setTimeout(() => {
            e.currentTarget.textContent = "Copy";
            e.currentTarget.classList.remove("copied");
          }, 1200);
        });
      });

      if (exportBtn) {
        exportBtn.addEventListener("click", async () => {
          const colors = [];
          for (let i = 1; i <= 6; i++) {
            const value = document.getElementById(`colorValue${i}`);
            colors.push(value ? value.value : "");
          }
          const text = `HealthBuddy Theme Colors:\n${colors.map((c, i) => `Color ${i + 1}: ${c}`).join("\n")}\n\nHex Array: [${colors.map((c) => `\"${c}\"`).join(", ")}]`;
          await navigator.clipboard.writeText(text);
          exportBtn.textContent = "Copied!";
          setTimeout(() => {
            exportBtn.textContent = "Export All Colors";
          }, 1200);
        });
      }
    }

    wireCursor() {
      const cursor = document.getElementById("customCursor");
      if (
        !cursor ||
        !window.matchMedia("(hover: hover) and (pointer: fine)").matches
      ) {
        return;
      }

      let x = window.innerWidth / 2;
      let y = window.innerHeight / 2;
      cursor.style.left = `${x}px`;
      cursor.style.top = `${y}px`;

      document.addEventListener("mousemove", (e) => {
        x = e.clientX;
        y = e.clientY;
        cursor.style.left = `${x}px`;
        cursor.style.top = `${y}px`;
      });

      const interactive = "button, a, input, select, textarea, .chip, .tab-btn";
      document.addEventListener("mouseover", (e) => {
        if (e.target.closest(interactive)) {
          cursor.style.width = "52px";
          cursor.style.height = "52px";
          cursor.style.borderWidth = "3px";
        }
      });
      document.addEventListener("mouseout", (e) => {
        if (e.target.closest(interactive)) {
          cursor.style.width = "40px";
          cursor.style.height = "40px";
          cursor.style.borderWidth = "2px";
        }
      });
    }
  }

  window.addEventListener("DOMContentLoaded", () => {
    const liquidThemeApp = new LiquidThemeApp();
    window.liquidThemeApp = liquidThemeApp;
  });
})();
