/**
 * HealthBuddy — GSAP Animation Layer
 * Exact port of SmartCare reference animations, selectors mapped to HealthBuddy DOM.
 *
 * Reference mapping:
 *   .header > *            →  .chat-header > *
 *   .eyebrow               →  .eyebrow               (NEW element added)
 *   .title .word           →  .welcome-heading .word  (words wrapped)
 *   .title-desc            →  .welcome-sub
 *   .paren-group .paren    →  skipped (no equivalent)
 *   .avatar-group          →  .avatar-group           (NEW element added)
 *   .dna-icon              →  .welcome-icon           (pulse icon)
 *   .future-tag            →  .disclaimer
 *   .badge                 →  .badge                  (NEW element added)
 *   .res-item              →  .tab-btn
 *   .wave-wrap             →  .wave-wrap              (NEW element added)
 *   .wave-glow             →  .wave-glow              (NEW element added)
 *   .bg-text               →  .bg-text                (NEW element added)
 *   .clay-card (tilt)      →  .product-onboarding, .onboarding-card
 *   .header-cta (magnet)   →  #newChatBtn
 *   .nav-pill click        →  .tab-btn click
 */
(function () {
  if (!window.gsap) return;
  gsap.registerPlugin(ScrollTrigger);

  // ─── INITIAL STATES ─── (identical to reference)
  gsap.set(".chat-header > *",        { y: -20, opacity: 0 });
  gsap.set(".eyebrow",                { y: 12,  opacity: 0 });
  gsap.set(".welcome-heading .word",  { yPercent: 110, opacity: 0 });
  gsap.set(".welcome-sub",            { opacity: 0, x: -10 });
  gsap.set(".avatar-group",           { scale: 0, opacity: 0 });
  gsap.set(".welcome-icon",           { scale: 0, rotation: -45, opacity: 0 });
  gsap.set(".disclaimer",             { opacity: 0, x: -10 });
  gsap.set(".badge",                  { scale: 0, rotation: -90, opacity: 0 });
  gsap.set(".tab-btn",                { y: 16,  opacity: 0 });
  gsap.set(".wave-wrap",              { x: 120, opacity: 0 });
  gsap.set(".wave-glow",              { opacity: 0 });
  gsap.set(".bg-text",                { opacity: 0, scale: 1.1 });

  // ─── PAGE LOAD TIMELINE ─── (exact timing from reference)
  const tl = gsap.timeline({
    defaults: { ease: "power3.out" },
    delay: 0.15
  });

  tl
    .to(".chat-header > *", {
      y: 0, opacity: 1, duration: 0.7, stagger: 0.07
    })
    .to(".wave-glow", {
      opacity: 1, duration: 1.2
    }, "-=.5")
    .to(".wave-wrap", {
      x: 0, opacity: 1, duration: 1.4, ease: "power3.out"
    }, "-=1.2")
    .to(".bg-text", {
      opacity: 1, scale: 1, duration: 1.4, ease: "power3.out"
    }, "-=1.2")
    .to(".eyebrow", {
      y: 0, opacity: 1, duration: 0.5
    }, "-=1")
    .to(".welcome-heading .word", {
      yPercent: 0, opacity: 1, duration: 0.9, stagger: 0.05, ease: "power4.out"
    }, "-=.8")
    .to(".welcome-sub", {
      x: 0, opacity: 1, duration: 0.6
    }, "-=.5")
    .to(".avatar-group", {
      scale: 1, opacity: 1, duration: 0.6, ease: "back.out(1.7)"
    }, "-=.4")
    .to(".welcome-icon", {
      scale: 1, rotation: 0, opacity: 1, duration: 0.6, ease: "back.out(1.7)"
    }, "-=.4")
    .to(".disclaimer", {
      x: 0, opacity: 1, duration: 0.5
    }, "-=.3")
    .to(".badge", {
      scale: 1, rotation: 0, opacity: 1, duration: 0.8, ease: "back.out(1.7)"
    }, "-=.5")
    .to(".tab-btn", {
      y: 0, opacity: 1, duration: 0.5, stagger: 0.08
    }, "-=.4")
    .to(".chip", {
      y: 0, opacity: 1, duration: 0.45, stagger: 0.06, ease: "power3.out"
    }, "-=.3");

  // Pre-set chips for the stagger above
  gsap.set(".chip", { y: 14, opacity: 0 });

  // ─── WAVE FLOAT — gentle continuous (exact from reference) ───
  gsap.to(".wave-wrap", {
    y: -18, rotation: -1.2, duration: 5.5,
    repeat: -1, yoyo: true, ease: "sine.inOut"
  });
  gsap.to(".wave-glow", {
    y: 12, scale: 1.05, duration: 6,
    repeat: -1, yoyo: true, ease: "sine.inOut"
  });
  gsap.to(".wave-glow.b", {
    y: -16, x: -10, duration: 7,
    repeat: -1, yoyo: true, ease: "sine.inOut"
  });

  // Badge slow drift
  gsap.to(".badge", {
    y: "+=8", duration: 3.5, repeat: -1, yoyo: true, ease: "sine.inOut"
  });

  // Welcome icon gentle rotate cycle (maps to .dna-icon svg rotation)
  gsap.to(".welcome-icon svg", {
    rotation: 12, duration: 4, repeat: -1, yoyo: true,
    ease: "sine.inOut", transformOrigin: "50% 50%"
  });

  // Avatar group gentle sway (maps to .avatar-group rotation)
  gsap.to(".avatar-group", {
    rotation: 3, duration: 3, repeat: -1, yoyo: true, ease: "sine.inOut"
  });

  // ─── SCROLL PARALLAX (exact from reference) ───
  gsap.to(".wave-wrap", {
    scrollTrigger: {
      trigger: ".chat-area",
      start: "top top",
      end: "+=1200",
      scrub: 1.2
    },
    y: -240, rotation: 6, scale: 1.08
  });

  gsap.to(".bg-text", {
    scrollTrigger: {
      trigger: ".chat-area",
      start: "top top",
      end: "+=1000",
      scrub: 1.2
    },
    xPercent: -8, opacity: 0.5
  });

  gsap.to(".badge", {
    scrollTrigger: {
      trigger: ".chat-area",
      start: "top top",
      end: "+=800",
      scrub: 1.5
    },
    y: 80, rotation: 30
  });

  // ─── SCROLL REVEALS ───
  gsap.utils.toArray(".reveal").forEach((el) => {
    gsap.fromTo(el,
      { y: 50, opacity: 0 },
      {
        scrollTrigger: { trigger: el, start: "top 88%", once: true },
        y: 0, opacity: 1, duration: 0.9, ease: "power3.out"
      }
    );
  });

  // ─── INTERACTIVE: WAVE MOUSE PARALLAX (exact from reference) ───
  if (!window.matchMedia("(pointer: coarse)").matches) {
    document.addEventListener("mousemove", (e) => {
      const x = e.clientX / window.innerWidth - 0.5;
      const y = e.clientY / window.innerHeight - 0.5;
      gsap.to(".wave-wrap", {
        x: x * 30, duration: 1.2, ease: "power3.out", overwrite: "auto"
      });
      gsap.to(".wave-glow", {
        x: x * 60, y: y * 40, duration: 1.4, ease: "power3.out", overwrite: "auto"
      });
      gsap.to(".badge", {
        x: x * -16, y: y * -10, duration: 1.2, ease: "power3.out", overwrite: "auto"
      });
      gsap.to(".bg-text", {
        x: x * -20, duration: 1.4, ease: "power3.out", overwrite: "auto"
      });
    });
  }

  // ─── CARD HOVER MICRO-TILT (exact from reference, maps to .clay-card) ───
  const tiltCards = document.querySelectorAll(
    ".product-onboarding, .onboarding-card, .shortcuts-card, .queue-stat-card, .info-card"
  );
  tiltCards.forEach((card) => {
    card.addEventListener("mousemove", (e) => {
      const r = card.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width  - 0.5;
      const y = (e.clientY - r.top)  / r.height - 0.5;
      gsap.to(card, {
        rotateY: x * 4, rotateX: -y * 4,
        duration: 0.5, ease: "power2.out", transformPerspective: 900
      });
    });
    card.addEventListener("mouseleave", () => {
      gsap.to(card, {
        rotateY: 0, rotateX: 0,
        duration: 0.7, ease: "elastic.out(1,.6)"
      });
    });
  });

  // ─── TAB BUTTONS — elastic bounce on click (maps to .nav-pill click) ───
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      gsap.fromTo(btn,
        { scale: 0.9 },
        { scale: 1, duration: 0.45, ease: "elastic.out(1, 0.5)" }
      );
    });
  });

  // ─── MAGNETIC EFFECT — New Chat button (maps to .header-cta) ───
  const newChatBtn = document.querySelector("#newChatBtn");
  if (newChatBtn && !window.matchMedia("(pointer: coarse)").matches) {
    newChatBtn.addEventListener("mousemove", (e) => {
      const r = newChatBtn.getBoundingClientRect();
      const x = (e.clientX - r.left  - r.width  / 2) / r.width;
      const y = (e.clientY - r.top   - r.height / 2) / r.height;
      gsap.to(newChatBtn, {
        x: x * 6, y: y * 6, duration: 0.4, ease: "power2.out"
      });
    });
    newChatBtn.addEventListener("mouseleave", () => {
      gsap.to(newChatBtn, {
        x: 0, y: 0, duration: 0.6, ease: "elastic.out(1,.5)"
      });
    });
  }

  // Send button magnetic
  const sendBtn = document.querySelector("#sendButton");
  if (sendBtn && !window.matchMedia("(pointer: coarse)").matches) {
    sendBtn.addEventListener("mousemove", (e) => {
      const r = sendBtn.getBoundingClientRect();
      const x = (e.clientX - r.left  - r.width  / 2) / r.width;
      const y = (e.clientY - r.top   - r.height / 2) / r.height;
      gsap.to(sendBtn, { x: x * 5, y: y * 5, duration: 0.35, ease: "power2.out" });
    });
    sendBtn.addEventListener("mouseleave", () => {
      gsap.to(sendBtn, { x: 0, y: 0, duration: 0.5, ease: "elastic.out(1,.5)" });
    });
  }

  // ─── CHIP HOVER LIFT (maps to suggestion chip hover) ───
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("mouseenter", () => {
      gsap.to(chip, { y: -5, scale: 1.05, duration: 0.25, ease: "power2.out" });
    });
    chip.addEventListener("mouseleave", () => {
      gsap.to(chip, { y: 0, scale: 1, duration: 0.4, ease: "elastic.out(1, 0.5)" });
    });
  });

  // ─── DYNAMIC MESSAGE ANIMATION ─── (new messages animate in)
  const msgList = document.querySelector("#messagesList");
  if (msgList) {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((m) => {
        m.addedNodes.forEach((node) => {
          if (node.nodeType === 1 && node.classList) {
            gsap.fromTo(node,
              { y: 24, opacity: 0 },
              { y: 0,  opacity: 1, duration: 0.5, ease: "power3.out" }
            );
          }
        });
      });
    });
    observer.observe(msgList, { childList: true });
  }

  // ─── SIDEBAR NUDGE FLOAT ───
  const nudge = document.querySelector(".sign-in-nudge, .upgrade-nudge");
  if (nudge) {
    gsap.to(nudge, {
      y: "+=6", duration: 2.8, repeat: -1, yoyo: true, ease: "sine.inOut"
    });
  }

  // ─── LOGO ICON SPIN ON HOVER ───
  const logoIcon = document.querySelector(".logo-icon, .sidebar-logo svg");
  if (logoIcon) {
    logoIcon.addEventListener("mouseenter", () => {
      gsap.to(logoIcon, { rotation: 360, duration: 0.6, ease: "power2.inOut" });
    });
    logoIcon.addEventListener("mouseleave", () => {
      gsap.set(logoIcon, { rotation: 0 });
    });
  }

})();
