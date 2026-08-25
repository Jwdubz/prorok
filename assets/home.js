(() => {
  const loader = document.getElementById("loader");
  const hashTarget = location.hash && location.hash !== "#"
    ? document.querySelector(location.hash)
    : null;

  function hideLoader() {
    if (!loader) return;
    loader.style.display = "none";
    loader.hidden = true;
    loader.setAttribute("aria-hidden", "true");
  }

  if (!window.gsap || !window.ScrollTrigger) {
    hideLoader();
    return;
  }

  const lenis = window.PROROK_LENIS;

  function hero() {
    gsap.timeline({ defaults: { ease: "power4.out" } })
      .from(".hero__title .char", { yPercent: 120, opacity: 0, rotate: 5, duration: 1.3, stagger: .05 })
      .from(".hero__kicker span", { yPercent: 110, duration: 1 }, "-=0.9")
      .from(".hero__sub .line > span", { yPercent: 110, opacity: 0, duration: 1, stagger: .12 }, "-=0.8")
      .from(".hero__vertical", { opacity: 0, y: 30, duration: 1.2 }, "-=0.8")
      .from(".hero__scroll", { opacity: 0, duration: .8 }, "-=0.6");
  }

  if (loader) {
    if (hashTarget) {
      loader.style.display = "none";
    } else {
      gsap.timeline({ onComplete: hero })
        .from(".loader__seal", { scale: 0, rotate: -30, duration: .7, ease: "back.out(2)" })
        .to(".loader__bar span", { scaleX: 1, duration: 1, ease: "power2.inOut" }, "-=0.2")
        .to(loader, { yPercent: -100, duration: .9, ease: "power4.inOut", delay: .1 })
        .set(loader, { display: "none" });
    }
  }

  gsap.to(".hero__img", { scale: 1.16, yPercent: 9, ease: "none",
    scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true } });
  gsap.to(".hero__content", { y: -90, opacity: 0, ease: "none",
    scrollTrigger: { trigger: ".hero", start: "top top", end: "70% top", scrub: true } });

  gsap.from(".thesis__jp", { opacity: 0, letterSpacing: "1.5em", duration: 1.4, ease: "power3.out",
    scrollTrigger: { trigger: ".thesis", start: "top 72%" } });
  gsap.from(".thesis__text .line > span", { yPercent: 115, duration: 1.2, stagger: .18,
    ease: "power4.out", scrollTrigger: { trigger: ".thesis", start: "top 64%" } });
  gsap.from(".thesis__seal", { scale: 0, rotate: 25, duration: .8, ease: "back.out(2.5)",
    scrollTrigger: { trigger: ".thesis__seal", start: "top 90%" } });

  gsap.utils.toArray(".panel").forEach((p) => {
    const img = p.querySelector(".panel__img img");
    const right = p.classList.contains("panel--right");
    gsap.fromTo(p.querySelector(".panel__img"),
      { clipPath: right ? "inset(0 0 0 100%)" : "inset(0 100% 0 0)" },
      { clipPath: "inset(0 0% 0 0%)", duration: 1.5, delay: .25, ease: "power4.inOut",
        scrollTrigger: { trigger: p, start: "top 72%" } });
    gsap.fromTo(img, { scale: 1.32 }, { scale: 1.08, duration: 1.5, delay: .25, ease: "power3.out",
      scrollTrigger: { trigger: p, start: "top 72%" } });
    gsap.fromTo(img, { yPercent: -6 }, { yPercent: 6, ease: "none",
      scrollTrigger: { trigger: p, start: "top bottom", end: "bottom top", scrub: true } });
    gsap.from(p.querySelectorAll(".panel__num, .panel__text h3, .panel__text p"),
      { y: 44, opacity: 0, duration: 1, stagger: .12, ease: "power3.out",
        scrollTrigger: { trigger: p, start: "top 58%" } });
  });

  gsap.utils.toArray(".sec__head").forEach((h) => {
    gsap.from(h.querySelectorAll(".char"), { yPercent: 120, opacity: 0, stagger: .035,
      duration: 1, ease: "power4.out", scrollTrigger: { trigger: h, start: "top 78%" } });
    gsap.from(h.querySelector(".sec__jp"), { opacity: 0, letterSpacing: "1.6em", duration: 1.3,
      ease: "power3.out", scrollTrigger: { trigger: h, start: "top 80%" } });
    const p = h.querySelector("p");
    if (p) gsap.from(p, { y: 26, opacity: 0, duration: 1, ease: "power3.out",
      scrollTrigger: { trigger: h, start: "top 74%" } });
  });
  gsap.from(".healed-montage", { clipPath: "inset(0 0 100% 0)", duration: 1.2,
    ease: "power3.out", scrollTrigger: { trigger: ".healed-montage", start: "top 82%" } });
  gsap.from(".step", { y: 50, opacity: 0, duration: .9, stagger: .09, ease: "power3.out",
    scrollTrigger: { trigger: ".steps", start: "top 80%" } });
  gsap.from(".door", { y: 60, opacity: 0, duration: 1, stagger: .12, ease: "power3.out",
    scrollTrigger: { trigger: ".doors__grid", start: "top 80%" } });
  gsap.matchMedia().add("(prefers-reduced-motion: no-preference)", () => {
    gsap.utils.toArray(".voices__card").forEach((card) => {
      gsap.from(card, { y: 36, duration: 1.1, ease: "power3.out",
        scrollTrigger: { trigger: card, start: "top 82%" } });
    });
  });
  gsap.from(".inquiry-chapter .sec__head, .inquiry-chapter .inquiry", {
    y: 28, opacity: 0, duration: 1, stagger: .1, ease: "power3.out",
    scrollTrigger: { trigger: ".inquiry-chapter", start: "top 78%" } });
  gsap.from(".visit__block", { y: 40, opacity: 0, duration: 1, stagger: .1, ease: "power3.out",
    scrollTrigger: { trigger: ".visit", start: "top 82%" } });

  if (hashTarget && lenis) {
    const goHash = () => {
      ScrollTrigger.refresh();
      lenis.resize();
      lenis.scrollTo(hashTarget, { offset: -92, immediate: true });
    };
    const arm = () => { goHash(); setTimeout(goHash, 160); };
    if (document.readyState === "complete") arm();
    else addEventListener("load", arm, { once: true });
  }
})();
