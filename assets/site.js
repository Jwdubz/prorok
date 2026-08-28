(() => {
  const cfg = window.PROROK || {};

  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const isMobile = matchMedia("(max-width: 880px)").matches;
  const pageParams = new URLSearchParams(location.search);
  const beatWheelRequested = pageParams.get("wheel") !== "off"
    && Boolean(document.querySelector("#top.hero"));

  if (window.gsap && window.ScrollTrigger) {
    gsap.registerPlugin(ScrollTrigger);
  }

  let lenis = null;
  const hasGsapDriver = Boolean(window.gsap && gsap.ticker && typeof gsap.ticker.add === "function");
  const hasRafDriver = typeof requestAnimationFrame === "function";
  if (window.Lenis && (hasGsapDriver || hasRafDriver)) {
    const lenisOptions = { lerp: 0.09 };
    if (beatWheelRequested) {
      lenisOptions.virtualScroll = ({ event }) => {
        if (!matchMedia("(min-width: 881px)").matches) return true;
        const beat = window.PROROK_WHEEL_BEAT;
        const type = String(event?.type || "");
        if (type.includes("wheel")) {
          const canCapture = typeof beat?.canCaptureWheel === "function"
            ? beat.canCaptureWheel(event)
            : false;
          return !(beat?.enabled && canCapture);
        }
        return true;
      };
    }
    lenis = new Lenis(lenisOptions);
    if (window.ScrollTrigger) lenis.on("scroll", ScrollTrigger.update);
    if (hasGsapDriver) {
      gsap.ticker.add((t) => lenis.raf(t * 1000));
      gsap.ticker.lagSmoothing(0);
    } else {
      const tick = (time) => {
        lenis.raf(time);
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }
  }
  window.PROROK_LENIS = lenis;

  document.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener("click", (e) => {
      const target = a.getAttribute("href");
      const el = target && target !== "#" ? document.querySelector(target) : null;
      if (!el) return;
      e.preventDefault();
      closeNav();
      if (lenis) {
        lenis.scrollTo(el, {
          offset: -92,
          duration: 1.6,
          easing: (t) => 1 - Math.pow(1 - t, 4)
        });
      } else {
        el.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
      }
    });
  });

  document.querySelectorAll("[data-split]").forEach((el) => {
    const text = el.textContent.trim();
    el.setAttribute("aria-label", text);
    el.innerHTML = text.split(/\s+/).map((w) =>
      `<span class="word" aria-hidden="true">${[...w].map((c) => `<span class="char">${c}</span>`).join("")}</span>`
    ).join(" ");
  });

  const nav = document.querySelector(".nav");
  const toggle = document.querySelector(".nav__toggle");
  const more = document.querySelector(".nav__more");
  const moreBtn = document.querySelector(".nav__more-btn");

  function closeNav() {
    if (!nav) return;
    nav.classList.remove("is-open");
    if (toggle) {
      toggle.setAttribute("aria-expanded", "false");
      toggle.textContent = "Menu";
    }
  }

  function closeMore() {
    if (!more || !moreBtn) return;
    more.classList.remove("is-open");
    moreBtn.setAttribute("aria-expanded", "false");
  }

  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const open = !nav.classList.contains("is-open");
      nav.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", String(open));
      toggle.textContent = open ? "Close" : "Menu";
      if (open) {
        const first = nav.querySelector(".nav__links a");
        first?.focus();
      }
    });
  }

  if (moreBtn && more) {
    moreBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = !more.classList.contains("is-open");
      more.classList.toggle("is-open", open);
      moreBtn.setAttribute("aria-expanded", String(open));
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeNav();
      closeMore();
    }
  });
  document.addEventListener("click", (e) => {
    if (more && !more.contains(e.target)) closeMore();
  });
  nav?.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", closeNav);
  });

  if (!isMobile && !reduceMotion) {
    const cv = document.getElementById("petals");
    if (cv && cv.getContext) {
      const ctx = cv.getContext("2d");
      const COLORS = ["rgba(178,58,44,A)", "rgba(140,47,34,A)", "rgba(239,231,216,A)", "rgba(162,145,127,A)"];
      let W, H;
      const dpr = Math.min(devicePixelRatio || 1, 2);
      const size = () => {
        W = innerWidth; H = innerHeight;
        cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      };
      size();
      addEventListener("resize", size);
      const r = (a, b) => a + Math.random() * (b - a);
      const make = (seed) => ({
        x: r(-40, W + 40), y: seed ? r(-H * .2, H) : r(-120, -20), size: r(4, 10),
        vy: r(.3, .95), vx: r(-.3, .45), rot: r(0, Math.PI * 2), vr: r(-.02, .02),
        swayAmp: r(10, 40), swaySpeed: r(.4, 1.1), phase: r(0, Math.PI * 2),
        color: COLORS[Math.random() * COLORS.length | 0].replace("A", r(.18, .5).toFixed(2)),
        squish: r(.55, .8)
      });
      const P = Array.from({ length: 22 }, () => make(true));
      const draw = (p) => {
        ctx.save();
        ctx.translate(p.x + Math.sin(p.phase) * p.swayAmp, p.y);
        ctx.rotate(p.rot); ctx.scale(1, p.squish); ctx.beginPath();
        const d = p.size;
        ctx.moveTo(0, -d);
        ctx.bezierCurveTo(d, -d * .6, d * .9, d * .7, 0, d);
        ctx.bezierCurveTo(-d * .9, d * .7, -d, -d * .6, 0, -d);
        ctx.fillStyle = p.color; ctx.fill(); ctx.restore();
      };
      let lastY = scrollY, vel = 0, t = 0;
      (function loop() {
        const y = scrollY; vel += (y - lastY - vel) * .08; lastY = y; t += .016;
        ctx.clearRect(0, 0, W, H);
        for (const p of P) {
          p.phase += p.swaySpeed * .016;
          p.y += p.vy + Math.min(Math.abs(vel) * .03, 2.4);
          p.x += p.vx + Math.sin(t * .5 + p.phase) * .2;
          p.rot += p.vr + vel * 4e-4;
          if (p.y > H + 40 || p.x < -80 || p.x > W + 80) Object.assign(p, make(false));
          draw(p);
        }
        requestAnimationFrame(loop);
      })();
    }
  }

  if (window.gsap) {
    const head = document.querySelector(".page .sec__head, .folio-page .sec__head");
    if (head) {
      const chars = head.querySelectorAll(".char");
      if (chars.length) {
        gsap.from(chars, { yPercent: 120, opacity: 0, stagger: .035, duration: 1, ease: "power4.out" });
      }
      const jp = head.querySelector(".sec__jp");
      if (jp) gsap.from(jp, { opacity: 0, letterSpacing: "1.6em", duration: 1.3, ease: "power3.out" });
      const p = head.querySelector("p");
      if (p) gsap.from(p, { y: 26, opacity: 0, duration: 1, ease: "power3.out" });
    }
    if (window.ScrollTrigger && !reduceMotion) {
      const figs = gsap.utils.toArray(".folio figure, .folio-flow figure, .flash-grid figure, .art-grid figure");
      if (figs.length) {
        ScrollTrigger.batch(figs, {
          start: "top 92%",
          once: true,
          onEnter: (batch) => {
            gsap.fromTo(batch, { opacity: 0, y: 22 }, {
              opacity: 1, y: 0, duration: .85, stagger: .05, ease: "power3.out"
            });
          }
        });
      }
      const artistImg = document.querySelector(".artist__img");
      const artistText = document.querySelector(".artist__text");
      if (artistImg) {
        gsap.from(artistImg, {
          opacity: 0,
          y: 28,
          duration: 1.1,
          ease: "power3.out",
          scrollTrigger: { trigger: artistImg, start: "top 82%" }
        });
      }
      if (artistText) {
        gsap.from(artistText, {
          opacity: 0,
          y: 24,
          duration: 1.1,
          ease: "power3.out",
          scrollTrigger: { trigger: artistText, start: "top 80%" }
        });
      }
    }
  }

  const consultHref = cfg.consultationUrl || "https://dylanprorok.as.me/";

  function safeParam(value, pattern) {
    const text = String(value || "");
    return pattern.test(text) ? text : "";
  }

  function prefillInquiryFromQuery() {
    const params = new URLSearchParams(location.search);
    const source = safeParam(params.get("source"), /^[a-z]{1,24}$/);
    const design = safeParam(params.get("design"), /^[A-Z]{3}(?:-[A-Z]{3})?-[A-Z0-9]{3}$/);
    if (!source && !design) return;
    document.querySelectorAll("[data-prorok-form='inquiry']").forEach((form) => {
      const field = form.querySelector("[data-field-name='description']");
      if (!field || field.value.trim()) return;
      const parts = [];
      if (source === "flash") parts.push("Flash archive");
      else if (source === "art") parts.push("Art archive");
      else if (source === "merch") parts.push("Merchandise listing");
      else if (source) parts.push("Inquiry");
      if (design) parts.push("reference " + design);
      field.value = parts.join(" — ") + ".";
    });
  }
  prefillInquiryFromQuery();

  function setError(field, message) {
    if (!field) return;
    field.classList.toggle("is-invalid", Boolean(message));
    const err = field.querySelector(".field__error");
    if (err) err.textContent = message || "";
    const isLocation = field.getAttribute("data-field") === "location" || field.matches("fieldset");
    const controls = isLocation
      ? Array.from(field.querySelectorAll("input[type='radio']"))
      : Array.from(field.querySelectorAll("input, textarea, select"));
    if (isLocation) {
      if (message) field.setAttribute("aria-invalid", "true");
      else field.removeAttribute("aria-invalid");
    }
    controls.forEach((control) => {
      if (message) control.setAttribute("aria-invalid", "true");
      else control.removeAttribute("aria-invalid");
    });
  }

  function validEmail(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  }

  const ACCEPTED_IMAGE_TYPES = cfg.acceptedImageTypes || [
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"
  ];
  const ACCEPTED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"];

  function collectFiles(input) {
    return Array.from(input?.files || []);
  }

  function isAcceptedImageFile(file) {
    const type = String(file.type || "").toLowerCase();
    if (type) return ACCEPTED_IMAGE_TYPES.includes(type);
    const name = String(file.name || "").toLowerCase();
    return ACCEPTED_IMAGE_EXTENSIONS.some((ext) => name.endsWith(ext));
  }

  function fieldControl(form, name) {
    return form.querySelector(`[data-field-name="${name}"]`);
  }

  function enableVisitorControls(form) {
    form.querySelectorAll("[data-js-enable]").forEach((el) => {
      el.disabled = false;
    });
  }

  function setInquiryButtonLabel(form, endpoint) {
    const label = form.querySelector(".form-actions .btn span");
    if (!label) return;
    label.textContent = endpoint ? "Send the inquiry" : "Book a virtual consultation";
  }

  function validateInquiry(form) {
    let ok = true;
    const name = fieldControl(form, "name");
    const description = fieldControl(form, "description");
    const placement = fieldControl(form, "placement");
    const email = fieldControl(form, "email");
    const location = form.querySelector("[data-field-name='location']:checked");
    const photos = fieldControl(form, "photos");

    const nameField = name?.closest(".field");
    if (nameField) {
      const bad = !name.value.trim();
      setError(nameField, bad ? "Name is required." : "");
      if (bad) ok = false;
    }
    const descField = description?.closest(".field");
    if (descField) {
      const bad = !description.value.trim();
      setError(descField, bad ? "Describe the tattoo you have in mind." : "");
      if (bad) ok = false;
    }
    const placeField = placement?.closest(".field");
    if (placeField) {
      const bad = !placement.value.trim();
      setError(placeField, bad ? "Add a placement and approximate size." : "");
      if (bad) ok = false;
    }
    const emailField = email?.closest(".field");
    if (emailField) {
      const value = email.value.trim();
      const bad = !value || !validEmail(value);
      setError(emailField, bad ? "Enter a working email so I can reply." : "");
      if (bad) ok = false;
    }
    const locField = form.querySelector("[data-field='location']");
    if (locField) {
      const bad = !location;
      setError(locField, bad ? "Choose where you are looking to get tattooed." : "");
      if (bad) ok = false;
    }
    const photoField = photos?.closest(".field");
    if (photoField && photos) {
      const files = collectFiles(photos);
      const wrong = files.find((f) => !isAcceptedImageFile(f));
      const huge = files.find((f) => f.size > (cfg.maxImageBytes || 10 * 1024 * 1024));
      if (wrong) {
        setError(photoField, "Use image files only — JPEG, PNG, WebP, or HEIC.");
        ok = false;
      } else if (huge) {
        setError(photoField, "Each image needs to stay under 10 MB.");
        ok = false;
      } else {
        setError(photoField, "");
      }
    }
    return ok;
  }

  function fallbackMessage() {
    return `Nothing was sent. Book a virtual consultation and we can talk through the piece there.`;
  }

  function showStatus(box, html, state) {
    if (!box) return;
    box.hidden = false;
    box.dataset.state = state || "info";
    box.innerHTML = html;
  }

  function buildFormData(form) {
    const body = new FormData();
    const seenRadio = new Set();
    form.querySelectorAll("[data-field-name]").forEach((el) => {
      const key = el.getAttribute("data-field-name");
      if (!key) return;
      if (el.type === "radio") {
        if (seenRadio.has(key)) return;
        const checked = form.querySelector(`[data-field-name="${key}"]:checked`);
        if (checked) body.append(key, checked.value);
        seenRadio.add(key);
        return;
      }
      if (el.type === "checkbox") {
        if (el.checked) body.append(key, el.value || "yes");
        return;
      }
      if (el.type === "file") {
        collectFiles(el).forEach((file) => body.append(key, file, file.name));
        return;
      }
      body.append(key, el.value ?? "");
    });
    return body;
  }

  async function postForm(endpoint, form) {
    const body = buildFormData(form);
    const res = await fetch(endpoint, { method: "POST", body });
    if (!res.ok) throw new Error("endpoint-failed");
  }

  document.querySelectorAll("[data-prorok-form]").forEach((form) => {
    const kind = form.getAttribute("data-prorok-form") || "inquiry";
    const status = form.querySelector(".form-status") || form.parentElement.querySelector(".form-status");
    const endpoint = kind === "newsletter"
      ? (cfg.newsletterEndpoint || cfg.formEndpoint)
      : cfg.formEndpoint;
    if (kind === "inquiry") setInquiryButtonLabel(form, endpoint);
    form.addEventListener("submit", async (e) => {
      if (!endpoint) {
        e.preventDefault();
        window.location.assign(consultHref);
        return;
      }
      e.preventDefault();
      if (kind === "inquiry" && !validateInquiry(form)) {
        showStatus(status, "<p>Please complete the highlighted fields.</p>", "error");
        form.querySelector(".is-invalid input, .is-invalid textarea, .is-invalid .radio input")?.focus();
        return;
      }
      if (kind === "newsletter") {
        const email = form.querySelector("[data-field-name='email']");
        const emailField = email?.closest(".field");
        const consent = form.querySelector("[data-field-name='newsletter']");
        if (!email?.value.trim() || !validEmail(email.value.trim())) {
          if (emailField) setError(emailField, "Enter an email address.");
          showStatus(status, "<p>Enter an email address to be notified.</p>", "error");
          email?.focus();
          return;
        }
        if (emailField) setError(emailField, "");
        if (consent && !consent.checked) {
          showStatus(status, "<p>Check the box if you want to be emailed when a release is actually available. Nothing was stored.</p>", "error");
          consent.focus();
          return;
        }
      }

      try {
        await postForm(endpoint, form);
        showStatus(status, kind === "newsletter"
          ? "<p>You are on the list. I will write when a release is ready.</p>"
          : "<p>The inquiry was sent. I will reply as soon as I can.</p>", "ok");
        form.reset();
      } catch (err) {
        showStatus(status, `<p>${fallbackMessage()}</p><p><a href="${consultHref}" target="_blank" rel="noopener">Book a virtual consultation</a></p>`, "error");
      }
    });
    enableVisitorControls(form);
  });
})();
