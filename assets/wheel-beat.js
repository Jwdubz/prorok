(() => {
  const params = new URLSearchParams(location.search);
  const requested = params.get("wheel") !== "off";
  const homepage = Boolean(document.querySelector("#top.hero"));
  const dock = document.getElementById("consult-dock");
  const header = document.querySelector(".site-header");
  const root = document.documentElement;
  const MINIMUM_DESKTOP_STAGE = 520;
  const isDesktopViewport = () => matchMedia("(min-width: 881px)").matches;
  const visibleHeight = () => Math.round(window.visualViewport?.height || innerHeight);
  const layoutHeight = () => document.documentElement.clientHeight || innerHeight;
  const chromeGeometry = () => {
    const height = visibleHeight();
    const headerBottom = Math.ceil(header?.getBoundingClientRect().bottom || 92);
    const dockRect = dock?.getBoundingClientRect();
    const dockBottomGap = dockRect ? Math.max(0, height - dockRect.bottom) : 0;
    const bottomClearance = dockRect
      ? Math.ceil(dockRect.height + dockBottomGap + 16)
      : 24;
    return { height, headerBottom, bottomClearance };
  };
  const viewportCanFitBeat = () => {
    if (!isDesktopViewport()) return false;
    const { height, headerBottom, bottomClearance } = chromeGeometry();
    return height - headerBottom - bottomClearance >= MINIMUM_DESKTOP_STAGE;
  };
  const isReducedMotion = () => root.dataset.motion === "reduced";

  const disabled = (reason) => {
    root.dataset.wheelBeatMode = "off";
    window.PROROK_WHEEL_BEAT = { enabled: false, reason };
  };

  if (!requested) return disabled("query-off");
  if (!homepage) return disabled("homepage-only");

  const initiallyFits = viewportCanFitBeat();
  const initialPauseReason = isDesktopViewport() ? "viewport-too-short" : "desktop-only";

  const lenis = window.PROROK_LENIS;

  const state = {
    enabled: initiallyFits,
    reason: initiallyFits ? "enabled" : initialPauseReason,
    transport: lenis && typeof lenis.scrollTo === "function" ? "lenis" : "native",
    state: initiallyFits ? "booting" : "paused",
    gestureId: 0,
    inputCount: 0,
    suppressedCount: 0,
    stepCount: 0,
    boundaryAttempts: 0,
    index: 0,
    currentIndex: 0,
    fromIndex: 0,
    targetY: 0,
    currentY: Math.round(scrollY),
    settledY: Math.round(scrollY),
    direction: 0,
    stops: [],
    labels: []
  };
  window.PROROK_WHEEL_BEAT = state;
  root.dataset.wheelBeatLayout = isDesktopViewport() ? "desktop" : "mobile";
  root.dataset.wheelBeatMode = initiallyFits ? "on" : "paused";
  let topCurtain = null;
  let bottomCurtain = null;

  function ensureCurtains() {
    if (topCurtain && bottomCurtain) return;
    topCurtain = document.createElement("div");
    bottomCurtain = document.createElement("div");
    topCurtain.className = "wheel-beat-curtain wheel-beat-curtain--top";
    bottomCurtain.className = "wheel-beat-curtain wheel-beat-curtain--bottom";
    topCurtain.setAttribute("aria-hidden", "true");
    bottomCurtain.setAttribute("aria-hidden", "true");
    document.body.append(topCurtain, bottomCurtain);
  }

  function removeCurtains() {
    topCurtain?.remove();
    bottomCurtain?.remove();
    topCurtain = null;
    bottomCurtain = null;
  }

  if (initiallyFits) ensureCurtains();

  let quiet = true;
  let movementComplete = true;
  let gestureLocked = false;
  let activeStep = false;
  let armed = false;
  let paused = !initiallyFits;
  let quietTimer = 0;
  let resizeTimer = 0;
  let resizeReleaseFrame = 0;
  let armFrame = 0;
  let lastBootInputAt = -Infinity;
  let documentHeight = 0;
  let topInset = 92;
  let bottomInsetStart = visibleHeight();
  let beatGroups = [];
  let resizeSettling = false;
  let focusFallbackLocked = false;
  let focusFallbackTimer = 0;
  let nativeSettleTimer = 0;
  const SCROLL_TAU_SECONDS = .41;
  const SCROLL_DURATION_MS = Math.round(SCROLL_TAU_SECONDS * 4.6 * 1000);
  let smoothScrollFrame = 0;
  let smoothScrollWatchdog = 0;
  let smoothScrollGeneration = 0;
  let activeGestureType = null;
  let viewportRefreshPending = false;
  let nativeTouchActive = false;
  let nativeTouchSettling = false;
  let nativeTouchSettleTimer = 0;
  const GESTURE_QUIET_MS = Math.round(SCROLL_TAU_SECONDS * 1000);
  const TOUCH_INTENT_PX = 8;
  const TOUCH_AXIS_RATIO = 1.15;
  const NATIVE_TOUCH_SELECTOR = [
    "input",
    "textarea",
    "select",
    "option",
    '[contenteditable="true"]',
    '[role="slider"]',
    '[role="spinbutton"]',
    "video[controls]",
    "audio[controls]",
    "iframe",
    "[data-beat-native]",
    "[data-lenis-prevent-touch]"
  ].join(",");
  const touchGesture = {
    id: null,
    mode: "idle",
    target: null,
    startX: 0,
    startY: 0,
    stepped: false
  };
  root.dataset.wheelBeatTau = String(SCROLL_TAU_SECONDS);
  root.dataset.wheelBeatTransitionMs = String(isReducedMotion() ? 0 : SCROLL_DURATION_MS);
  root.dataset.wheelBeatQuietMs = String(GESTURE_QUIET_MS);
  root.dataset.wheelBeatMotion = isReducedMotion() ? "reduced" : "full";
  addEventListener("prorok:motion-change", () => {
    root.dataset.wheelBeatMotion = isReducedMotion() ? "reduced" : "full";
    root.dataset.wheelBeatTransitionMs = String(isReducedMotion() ? 0 : SCROLL_DURATION_MS);
  });
  state.canCaptureWheel = (event) => {
    if (event?.ctrlKey || !event?.deltaY || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return false;
    if (ownsVerticalScroll(event.target, Math.sign(event.deltaY))) return false;
    if (!armed || resizeSettling || gestureLocked) return true;
    if (focusFallbackLocked) return false;
    return atomicCaptureFocusIsSafe();
  };
  const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

  function syncState() {
    root.dataset.wheelBeatState = state.state;
    root.dataset.wheelBeatIndex = String(state.index);
    root.dataset.wheelBeatSteps = String(state.stepCount);
    root.dataset.wheelBeatBoundaries = String(state.boundaryAttempts);
    root.dataset.wheelBeatInputs = String(state.inputCount);
    root.dataset.wheelBeatSuppressed = String(state.suppressedCount);
    root.dataset.wheelBeatTarget = String(Math.round(state.targetY));
    root.dataset.wheelBeatStopCount = String(state.stops.length);
    root.dataset.wheelBeatLabel = state.labels[state.index] || "";
    root.dataset.wheelBeatCurrentIndex = String(state.currentIndex);
    root.dataset.wheelBeatCurrentY = String(state.currentY);
    root.dataset.wheelBeatTransport = state.transport;
    root.dataset.wheelBeatMaxStop = String(state.stops[state.stops.length - 1] || 0);
    root.dataset.wheelBeatMaxGap = String(state.stops.reduce((largest, stop, index) => {
      if (!index) return largest;
      return Math.max(largest, stop - state.stops[index - 1]);
    }, 0));
    root.dataset.wheelBeatMinGap = String(state.stops.reduce((smallest, stop, index) => {
      if (!index) return smallest;
      return Math.min(smallest, stop - state.stops[index - 1]);
    }, Infinity));
  }

  function nearestIndex(y) {
    if (!state.stops.length) return 0;
    let best = 0;
    let distance = Infinity;
    state.stops.forEach((stop, index) => {
      const next = Math.abs(stop - y);
      if (next < distance) {
        best = index;
        distance = next;
      }
    });
    return best;
  }

  function labelFor(element) {
    if (element.id) return element.id;
    const heading = element.querySelector("h1, h2, h3");
    if (heading) return heading.textContent.trim();
    return element.classList[0] || element.tagName.toLowerCase();
  }

  function beatDefinitions() {
    const desktop = isDesktopViewport();
    const top = document.getElementById("top");
    const thesis = document.getElementById("thesis");
    const scale = document.getElementById("scale");
    const workHead = document.querySelector("#work > .sec__head");
    const workPanels = Array.from(document.querySelectorAll("#work > .panel"));
    const portfolioLink = document.querySelector("#work > .work__to-folio");
    const healedHead = document.querySelector("#healed .sec__head");
    const healedMontage = document.querySelector("#healed .healed-montage");
    const voicesHead = document.querySelector("#voices > .sec__head");
    const voices = Array.from(document.querySelectorAll("#voices .voices__card"));
    const craftHead = document.querySelector("#craft .sec__head");
    const stepsContainer = document.querySelector("#craft .steps");
    const steps = Array.from(document.querySelectorAll("#craft .step"));
    const begin = document.getElementById("begin");
    const beginHead = document.querySelector("#begin > .sec__head");
    const doors = Array.from(document.querySelectorAll("#begin .door"));
    const visit = document.getElementById("visit");
    const foot = document.querySelector(".foot");
    const group = (...elements) => elements.filter(Boolean);
    const desktopDefinitions = [
      { anchor: top, group: group(top), label: "top" },
      { anchor: thesis, group: group(thesis), label: "thesis" },
      { anchor: scale, group: group(scale), label: "scale", atomic: true },
      { anchor: workHead, group: group(workHead, workPanels[0]), label: "The Work", atomic: true },
      { anchor: workPanels[1], group: group(workPanels[1]), label: labelFor(workPanels[1]) },
      { anchor: workPanels[2], group: group(workPanels[2], portfolioLink), label: labelFor(workPanels[2]) },
      { anchor: healedHead, group: group(healedHead, healedMontage), label: "Healed", atomic: true },
      { anchor: voicesHead, group: group(voicesHead, voices[0]), label: "In their words" },
      { anchor: voices[1], group: group(voices[1]), label: "Client story — Shannon" },
      { anchor: voices[2], group: group(voices[2]), label: "Client story — Mike" },
      { anchor: craftHead, group: group(craftHead, stepsContainer), label: "What a large project is" },
      { anchor: beginHead, group: group(begin), label: "Begin", atomic: true },
      { anchor: visit, group: group(visit, foot), label: "Visit" }
    ];
    const mobileDefinitions = [
      { anchor: top, group: group(top), label: "top" },
      { anchor: thesis, group: group(thesis), label: "thesis" },
      { anchor: scale, group: group(scale), label: "scale", atomic: true },
      { anchor: workHead, group: group(workHead), label: "The Work" },
      { anchor: workPanels[0], group: group(workPanels[0]), label: labelFor(workPanels[0]) },
      { anchor: workPanels[1], group: group(workPanels[1]), label: labelFor(workPanels[1]) },
      { anchor: workPanels[2], group: group(workPanels[2], portfolioLink), label: labelFor(workPanels[2]) },
      { anchor: healedHead, group: group(healedHead), label: "Healed" },
      { anchor: healedMontage, group: group(healedMontage), label: "Healed work" },
      { anchor: voicesHead, group: group(voicesHead), label: "In their words" },
      { anchor: voices[0], group: group(voices[0]), label: "Client story — Jordan" },
      { anchor: voices[1], group: group(voices[1]), label: "Client story — Shannon" },
      { anchor: voices[2], group: group(voices[2]), label: "Client story — Mike" },
      { anchor: craftHead, group: group(craftHead, steps[0]), label: "What a large project is" },
      { anchor: steps[1], group: group(steps[1], steps[2]), label: "Consultation and drawing" },
      { anchor: steps[3], group: group(steps[3], steps[4]), label: "Sessions and healing" },
      { anchor: beginHead, group: group(beginHead, doors[0]), label: "Begin" },
      { anchor: doors[1], group: group(doors[1]), label: labelFor(doors[1]) },
      { anchor: doors[2], group: group(doors[2]), label: labelFor(doors[2]) },
      { anchor: visit, group: group(visit), label: "Visit" },
      { anchor: foot, group: group(foot), label: "Footer" }
    ];
    const definitions = desktop
      ? desktopDefinitions.map((definition) => ({ ...definition, atomic: true }))
      : mobileDefinitions;
    return definitions.filter((definition) => definition.anchor && definition.group.length);
  }

  function groupBounds(group, absolute = false) {
    const rects = group
      .filter((element) => element && element.isConnected)
      .map((element) => element.getBoundingClientRect())
      .filter((rect) => rect.height || rect.width);
    if (!rects.length) return null;
    const offset = absolute ? scrollY : 0;
    return {
      top: Math.min(...rects.map((rect) => rect.top)) + offset,
      bottom: Math.max(...rects.map((rect) => rect.bottom)) + offset
    };
  }

  function fieldColor(group) {
    let element = group[0] || document.body;
    let owner = element.closest("section, header, footer") || element;
    while (owner && owner !== document.documentElement) {
      const color = getComputedStyle(owner).backgroundColor;
      if (color && color !== "transparent" && color !== "rgba(0, 0, 0, 0)") return color;
      owner = owner.parentElement;
    }
    return getComputedStyle(document.body).backgroundColor || "rgb(20, 16, 14)";
  }

  function hideRestingField() {
    root.dataset.wheelBeatMatte = "off";
  }

  function focusAllowsGroup(group) {
    const active = document.activeElement;
    const meaningfulFocus = active && active !== document.body && active !== document.documentElement;
    if (!meaningfulFocus || header?.contains(active) || dock?.contains(active)) return true;
    return group.some((element) => element === active || element.contains(active));
  }

  function atomicCaptureFocusIsSafe() {
    const active = document.activeElement;
    const meaningfulFocus = active && active !== document.body && active !== document.documentElement;
    return !meaningfulFocus || Boolean(header?.contains(active) || dock?.contains(active));
  }

  function paintField(group, { respectFocus = true, guardChrome = false } = {}) {
    const bounds = groupBounds(group || []);
    if (!bounds) {
      hideRestingField();
      return false;
    }
    if (respectFocus && !focusAllowsGroup(group)) {
      hideRestingField();
      return false;
    }
    const viewportHeight = visibleHeight();
    const matteTop = clamp(
      guardChrome ? Math.max(topInset, Math.ceil(bounds.top)) : Math.ceil(bounds.top),
      0,
      viewportHeight
    );
    const matteBottomStart = clamp(
      guardChrome ? Math.min(bottomInsetStart, Math.floor(bounds.bottom)) : Math.floor(bounds.bottom),
      0,
      viewportHeight
    );
    root.style.setProperty("--wheel-beat-matte-top", matteTop + "px");
    root.style.setProperty("--wheel-beat-matte-bottom-start", matteBottomStart + "px");
    root.style.setProperty("--wheel-beat-field-color", fieldColor(group));
    root.dataset.wheelBeatMatte = "on";
    return true;
  }

  function holdFocusFallback() {
    focusFallbackLocked = true;
    state.state = "focus-fallback";
    hideRestingField();
    clearTimeout(focusFallbackTimer);
    focusFallbackTimer = setTimeout(() => {
      focusFallbackLocked = false;
      if (gestureLocked || resizeSettling || paused || !armed) return;
      state.currentY = Math.round(scrollY);
      state.currentIndex = nearestIndex(scrollY);
      state.index = state.currentIndex;
      state.targetY = state.stops[state.index] || state.currentY;
      state.settledY = state.currentY;
      state.state = "idle";
      syncState();
      updateRestingField();
    }, 260);
    syncState();
  }

  function updateRestingField() {
    if (!armed || paused || state.state === "booting") {
      hideRestingField();
      return;
    }
    if (state.state === "moving") {
      hideRestingField();
      return;
    }
    const group = beatGroups[state.index] || [];
    paintField(group, { respectFocus: true });
  }

  function refreshStops() {
    root.dataset.wheelBeatLayout = isDesktopViewport() ? "desktop" : "mobile";
    const { height: viewportHeight, headerBottom, bottomClearance } = chromeGeometry();
    topInset = headerBottom;
    const usableBottom = Math.max(topInset + 200, viewportHeight - bottomClearance);
    bottomInsetStart = usableBottom;
    const minimumStage = isDesktopViewport() ? MINIMUM_DESKTOP_STAGE : 360;
    const usableHeight = Math.max(minimumStage, usableBottom - topInset);
    const mediaBottom = Math.max(topInset + 200, viewportHeight);
    const scaleMediaHeight = Math.max(420, mediaBottom - topInset);
    root.style.setProperty("--wheel-beat-stage-height", usableHeight + "px");
    root.style.setProperty("--wheel-beat-full-stage-height", scaleMediaHeight + "px");
    root.style.setProperty("--wheel-beat-scale-media-height", Math.max(420, viewportHeight) + "px");
    root.style.setProperty("--wheel-beat-work-media-height", Math.max(160, usableHeight - 218) + "px");
    root.style.setProperty("--wheel-beat-healed-media-height", Math.max(160, scaleMediaHeight - 218) + "px");
    document.documentElement.offsetHeight;
    const workHeadingHeight = document.querySelector("#work > .sec__head")?.getBoundingClientRect().height || 0;
    const healedHeadingHeight = document.querySelector("#healed .sec__head")?.getBoundingClientRect().height || 0;
    root.style.setProperty(
      "--wheel-beat-work-media-height",
      Math.max(160, usableHeight - Math.ceil(workHeadingHeight) - 16) + "px"
    );
    root.style.setProperty(
      "--wheel-beat-healed-media-height",
      Math.max(160, scaleMediaHeight - Math.ceil(healedHeadingHeight) - 16) + "px"
    );
    document.documentElement.offsetHeight;
    if (window.ScrollTrigger && typeof ScrollTrigger.refresh === "function") {
      ScrollTrigger.refresh();
    }
    if (lenis && typeof lenis.resize === "function") lenis.resize();

    const maxScroll = Math.max(0, document.documentElement.scrollHeight - layoutHeight());
    const definitions = beatDefinitions();
    const topGroup = definitions[0]?.group || [];
    const endGroup = definitions[definitions.length - 1]?.group || [];
    const raw = [
      { y: 0, label: "top", group: topGroup, terminal: true },
      { y: maxScroll, label: "end", group: endGroup, terminal: true }
    ];

    definitions.forEach((definition) => {
      const rect = definition.anchor.getBoundingClientRect();
      const bounds = groupBounds(definition.group, true);
      if (!rect.height || !bounds) return;
      const absoluteTop = rect.top + scrollY;
      const absoluteBottom = bounds.bottom;
      raw.push({
        y: clamp(Math.round(absoluteTop - topInset), 0, maxScroll),
        label: definition.label,
        group: definition.group,
        terminal: false
      });
      const bottomAligned = clamp(Math.round(absoluteBottom - usableBottom), 0, maxScroll);
      const minimumContinuation = Math.max(140, Math.round(viewportHeight * .2));
      if (!definition.atomic
        && definition.anchor.id !== "top"
        && bounds.bottom - bounds.top > usableHeight + 24
        && bottomAligned - clamp(Math.round(absoluteTop - topInset), 0, maxScroll) >= minimumContinuation) {
        raw.push({
          y: bottomAligned,
          label: definition.label + " — continuation",
          group: definition.group,
          terminal: false
        });
      }
    });

    raw.sort((a, b) => a.y - b.y || Number(b.terminal) - Number(a.terminal));
    const unique = [];
    raw.forEach((beat) => {
      const previous = unique[unique.length - 1];
      if (!previous || beat.terminal || beat.y - previous.y > 48) {
        unique.push(beat);
      }
    });
    if (!unique.length || unique[0].y !== 0) {
      unique.unshift({ y: 0, label: "top", group: topGroup, terminal: true });
    }
    if (unique[unique.length - 1].y !== maxScroll) {
      unique.push({ y: maxScroll, label: "end", group: endGroup, terminal: true });
    }
    const terminalDistance = Math.max(140, Math.round(viewportHeight * .2));
    const terminal = unique[unique.length - 1];
    const beforeTerminal = unique[unique.length - 2];
    const terminalSharesGroup = beforeTerminal?.group === terminal?.group;
    if (beforeTerminal
      && !beforeTerminal.terminal
      && terminal.terminal
      && (terminalSharesGroup || terminal.y - beforeTerminal.y < terminalDistance)) {
      unique.splice(unique.length - 2, 1);
    }

    const filled = unique.slice();

    state.stops = filled.map((beat) => beat.y);
    state.labels = filled.map((beat) => beat.label);
    beatGroups = filled.map((beat) => beat.group || []);
    state.currentY = Math.round(scrollY);
    state.currentIndex = nearestIndex(scrollY);
    state.index = state.currentIndex;
    state.targetY = state.stops[state.index] || 0;
    state.settledY = Math.round(scrollY);
    documentHeight = document.documentElement.scrollHeight;
    syncState();
    updateRestingField();
  }

  function dispatchBeat(phase) {
    dispatchEvent(new CustomEvent("prorok:wheel-beat", {
      detail: {
        phase,
        gestureId: state.gestureId,
        fromIndex: state.fromIndex,
        toIndex: state.index,
        direction: state.direction,
        targetY: state.targetY,
        settledY: state.settledY,
        inputCount: state.inputCount,
        suppressedCount: state.suppressedCount
      }
    }));
  }

  function scheduleQuietRelease() {
    quiet = false;
    clearTimeout(quietTimer);
    quietTimer = setTimeout(() => {
      quiet = true;
      releaseIfReady();
    }, GESTURE_QUIET_MS);
  }

  function releaseIfReady() {
    if (paused) {
      state.state = "paused";
      syncState();
      return;
    }
    if (!movementComplete) {
      state.state = "moving";
    } else if (!quiet) {
      state.state = "settling";
    } else {
      gestureLocked = false;
      state.state = "idle";
      state.currentY = Math.round(scrollY);
      state.currentIndex = nearestIndex(scrollY);
      state.settledY = Math.round(scrollY);
      state.index = state.currentIndex;
      if (activeStep) dispatchBeat("complete");
      activeStep = false;
      activeGestureType = null;
    }
    syncState();
    updateRestingField();
    if (!gestureLocked && state.state === "idle" && viewportRefreshPending) {
      viewportRefreshPending = false;
      requestAnimationFrame(onViewportResize);
    }
  }

  function cancelActiveMovement() {
    clearTimeout(quietTimer);
    clearTimeout(nativeSettleTimer);
    clearTimeout(smoothScrollWatchdog);
    smoothScrollGeneration += 1;
    cancelAnimationFrame(smoothScrollFrame);
    gestureLocked = false;
    activeStep = false;
    activeGestureType = null;
    if (lenis && typeof lenis.reset === "function") {
      lenis.reset();
    } else if (lenis && typeof lenis.stop === "function" && typeof lenis.start === "function") {
      lenis.stop();
      lenis.start();
    } else if (lenis && typeof lenis.scrollTo === "function") {
      lenis.scrollTo(scrollY, { immediate: true, force: true });
    }
    quiet = true;
    movementComplete = true;
    state.currentY = Math.round(scrollY);
    state.currentIndex = nearestIndex(scrollY);
    state.settledY = state.currentY;
    root.dataset.wheelBeatTransition = "idle";
  }

  function yieldToNativeNavigation() {
    if (!gestureLocked && state.state !== "moving" && state.state !== "settling") return;
    cancelActiveMovement();
    state.currentY = Math.round(scrollY);
    state.currentIndex = nearestIndex(scrollY);
    state.index = state.currentIndex;
    state.targetY = state.stops[state.index] || state.currentY;
    state.settledY = state.currentY;
    state.state = "idle";
    syncState();
    hideRestingField();
  }

  function settleAtCurrentGeometry() {
    resizeSettling = true;
    state.state = "settling";
    root.style.setProperty("--wheel-beat-matte-top", topInset + "px");
    root.style.setProperty("--wheel-beat-matte-bottom-start", topInset + "px");
    root.dataset.wheelBeatMatte = "on";
    syncState();
    cancelActiveMovement();
    refreshStops();
    const snappedY = state.stops[state.index] ?? scrollY;
    if (lenis && typeof lenis.scrollTo === "function") {
      lenis.scrollTo(snappedY, { immediate: true, force: true });
    } else {
      scrollTo(0, snappedY);
    }
    state.currentY = Math.round(scrollY);
    state.currentIndex = nearestIndex(scrollY);
    state.index = state.currentIndex;
    state.targetY = state.stops[state.index] || state.currentY;
    state.settledY = state.currentY;
    state.enabled = true;
    state.reason = "enabled";
    armed = true;
    state.state = "idle";
    syncState();
    updateRestingField();
    cancelAnimationFrame(resizeReleaseFrame);
    resizeReleaseFrame = requestAnimationFrame(() => {
      resizeSettling = false;
      resizeReleaseFrame = 0;
    });
  }

  function tauEase(progress) {
    const durationSeconds = SCROLL_DURATION_MS / 1000;
    const denominator = 1 - Math.exp(-durationSeconds / SCROLL_TAU_SECONDS);
    return (1 - Math.exp(-(durationSeconds * progress) / SCROLL_TAU_SECONDS)) / denominator;
  }

  function smoothToBeat(targetIndex) {
    const target = state.stops[targetIndex];
    const generation = ++smoothScrollGeneration;
    clearTimeout(smoothScrollWatchdog);
    cancelAnimationFrame(smoothScrollFrame);
    state.index = targetIndex;
    state.targetY = target;
    state.state = "moving";
    movementComplete = false;
    root.dataset.wheelBeatTransition = "moving";
    hideRestingField();
    syncState();

    let finished = false;
    const done = () => {
      if (finished || paused || generation !== smoothScrollGeneration) return;
      finished = true;
      clearTimeout(smoothScrollWatchdog);
      cancelAnimationFrame(smoothScrollFrame);
      if (Math.abs(scrollY - target) > 1) {
        if (lenis && typeof lenis.scrollTo === "function") {
          lenis.scrollTo(target, { immediate: true, force: true });
        } else {
          scrollTo(0, target);
        }
      }
      if (window.ScrollTrigger && typeof ScrollTrigger.update === "function") ScrollTrigger.update();
      state.currentY = Math.round(scrollY);
      state.currentIndex = nearestIndex(scrollY);
      state.index = targetIndex;
      state.targetY = target;
      state.settledY = state.currentY;
      movementComplete = true;
      root.dataset.wheelBeatTransition = "idle";
      if (activeGestureType === "wheel") scheduleQuietRelease();
      releaseIfReady();
    };

    if (isReducedMotion()) {
      if (lenis && typeof lenis.scrollTo === "function") {
        lenis.scrollTo(target, { immediate: true, force: true });
      } else {
        scrollTo(0, target);
      }
      done();
      return;
    }

    if (lenis && typeof lenis.scrollTo === "function") {
      lenis.scrollTo(target, {
        duration: SCROLL_DURATION_MS / 1000,
        easing: tauEase,
        force: true,
        userData: { source: "wheel-beat", gestureId: state.gestureId, beatIndex: targetIndex },
        onComplete: done
      });
    } else {
      const startY = scrollY;
      const distance = target - startY;
      const started = performance.now();
      const tick = (now) => {
        if (generation !== smoothScrollGeneration || paused || !gestureLocked) return;
        const progress = clamp((now - started) / SCROLL_DURATION_MS, 0, 1);
        scrollTo(0, startY + distance * tauEase(progress));
        if (progress < 1) smoothScrollFrame = requestAnimationFrame(tick);
        else done();
      };
      smoothScrollFrame = requestAnimationFrame(tick);
    }
    smoothScrollWatchdog = setTimeout(done, SCROLL_DURATION_MS + 450);
    releaseIfReady();
  }

  function moveOneBeat(direction) {
    if (document.documentElement.scrollHeight !== documentHeight) refreshStops();
    const current = scrollY;
    const fromIndex = nearestIndex(current);
    let nextIndex = fromIndex;
    if (direction > 0) {
      nextIndex = state.stops.findIndex((stop) => stop > current + 12);
      if (nextIndex < 0) nextIndex = state.stops.length - 1;
      const approachWindow = Math.max(96, Math.round(visibleHeight() * .2));
      if (nextIndex === fromIndex
        && state.stops[fromIndex] - current < approachWindow) {
        nextIndex = Math.min(fromIndex + 1, state.stops.length - 1);
      }
    } else {
      for (let index = state.stops.length - 1; index >= 0; index -= 1) {
        if (state.stops[index] < current - 12) {
          nextIndex = index;
          break;
        }
      }
      const approachWindow = Math.max(96, Math.round(visibleHeight() * .2));
      if (nextIndex === fromIndex
        && current - state.stops[fromIndex] < approachWindow) {
        nextIndex = Math.max(fromIndex - 1, 0);
      }
    }

    state.gestureId += 1;
    state.fromIndex = fromIndex;
    state.direction = direction;
    if (nextIndex === fromIndex) {
      state.boundaryAttempts += 1;
      state.targetY = state.stops[fromIndex];
      state.state = "settling";
      movementComplete = true;
      releaseIfReady();
      return;
    }

    state.stepCount += 1;
    state.index = nextIndex;
    state.targetY = state.stops[nextIndex];
    state.state = "settling";
    movementComplete = false;
    activeStep = true;
    syncState();
    dispatchBeat("start");
    smoothToBeat(nextIndex);
  }

  function ownsVerticalScroll(target, direction) {
    let element = target instanceof Element ? target : null;
    while (element && element !== document.body && element !== document.documentElement) {
      const style = getComputedStyle(element);
      if (/auto|scroll/.test(style.overflowY) && element.scrollHeight > element.clientHeight + 1) {
        const canMove = direction > 0
          ? element.scrollTop + element.clientHeight < element.scrollHeight - 1
          : element.scrollTop > 1;
        if (canMove) return true;
      }
      element = element.parentElement;
    }
    return false;
  }

  function resetTouchGesture(mode = "idle") {
    nativeTouchActive = false;
    touchGesture.id = null;
    touchGesture.mode = mode;
    touchGesture.target = null;
    touchGesture.startX = 0;
    touchGesture.startY = 0;
    touchGesture.stepped = false;
  }

  function markTouchNative(event) {
    touchGesture.mode = "native";
    nativeTouchActive = Boolean(event?.touches?.length);
    if (touchGesture.id === null && event?.touches?.length) {
      touchGesture.id = event.touches[0].identifier;
    }
  }

  function trackedTouch(list) {
    for (let index = 0; index < list.length; index += 1) {
      if (list[index].identifier === touchGesture.id) return list[index];
    }
    return null;
  }

  function touchTargetIsNative(target) {
    return target instanceof Element && Boolean(target.closest(NATIVE_TOUCH_SELECTOR));
  }

  function touchBeatThreshold() {
    return clamp(Math.round(visibleHeight() * .065), 36, 64);
  }

  function onTouchStart(event) {
    if (paused || !viewportCanFitBeat()) return;
    clearTimeout(nativeTouchSettleTimer);
    nativeTouchSettling = false;
    if (event.touches.length !== 1) {
      if (gestureLocked || state.state === "moving") yieldToNativeNavigation();
      markTouchNative(event);
      return;
    }
    const touch = event.touches[0];
    touchGesture.id = touch.identifier;
    touchGesture.mode = touchTargetIsNative(event.target) ? "native" : "pending";
    nativeTouchActive = touchGesture.mode === "native";
    touchGesture.target = event.target;
    touchGesture.startX = touch.clientX;
    touchGesture.startY = touch.clientY;
    touchGesture.stepped = false;
  }

  function onTouchMove(event) {
    if (paused || !viewportCanFitBeat()) return;
    if (touchGesture.id === null || touchGesture.mode === "native") return;
    if (event.touches.length !== 1) {
      if (gestureLocked || state.state === "moving") yieldToNativeNavigation();
      markTouchNative(event);
      return;
    }
    const touch = trackedTouch(event.touches);
    if (!touch) return;
    const deltaX = touch.clientX - touchGesture.startX;
    const deltaY = touchGesture.startY - touch.clientY;
    const absX = Math.abs(deltaX);
    const absY = Math.abs(deltaY);

    if (touchGesture.mode === "pending") {
      if (Math.max(absX, absY) < TOUCH_INTENT_PX) return;
      if (absX * TOUCH_AXIS_RATIO >= absY) {
        markTouchNative(event);
        return;
      }
      const direction = Math.sign(deltaY);
      if (!direction || ownsVerticalScroll(touchGesture.target, direction)) {
        markTouchNative(event);
        return;
      }
      if (!event.cancelable) {
        markTouchNative(event);
        return;
      }
      touchGesture.mode = "captured";
      quiet = false;
      clearTimeout(quietTimer);
    }

    if (touchGesture.mode !== "captured") return;
    if (!event.cancelable) {
      quiet = true;
      releaseIfReady();
      markTouchNative(event);
      return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();

    if (touchGesture.stepped) {
      state.inputCount += 1;
      state.suppressedCount += 1;
      syncState();
      return;
    }
    if (absY < touchBeatThreshold()) return;

    touchGesture.stepped = true;
    state.inputCount += 1;
    if (resizeSettling || !armed) {
      lastBootInputAt = performance.now();
      state.suppressedCount += 1;
      state.state = resizeSettling ? "settling" : "booting";
      syncState();
      return;
    }
    if (gestureLocked) {
      state.suppressedCount += 1;
      syncState();
      return;
    }
    if (focusFallbackLocked || !atomicCaptureFocusIsSafe()) {
      quiet = true;
      holdFocusFallback();
      resetTouchGesture();
      return;
    }

    gestureLocked = true;
    activeGestureType = "touch";
    moveOneBeat(Math.sign(deltaY));
  }

  function finishTouch(event) {
    if (touchGesture.mode === "native") {
      nativeTouchActive = event.touches.length > 0;
      if (nativeTouchActive) {
        touchGesture.id = event.touches[0].identifier;
      } else {
        resetTouchGesture();
        nativeTouchSettling = true;
        clearTimeout(nativeTouchSettleTimer);
        nativeTouchSettleTimer = setTimeout(() => {
          nativeTouchSettling = false;
          refreshAfterNativeTouch();
        }, 250);
      }
      return;
    }
    if (touchGesture.id === null) return;
    const ended = trackedTouch(event.changedTouches);
    if (!ended) return;
    if (touchGesture.mode === "captured") {
      event.stopImmediatePropagation();
      clearTimeout(quietTimer);
      quiet = true;
      releaseIfReady();
    }
    resetTouchGesture();
  }

  function refreshAfterNativeTouch() {
    if (!viewportRefreshPending || nativeTouchActive) return;
    viewportRefreshPending = false;
    root.dataset.wheelBeatLayout = isDesktopViewport() ? "desktop" : "mobile";
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (!viewportCanFitBeat()) {
        onViewportResize();
        return;
      }
      if (paused) {
        paused = false;
        state.enabled = true;
        state.reason = "enabled";
        ensureCurtains();
        root.dataset.wheelBeatMode = "on";
        scheduleArm();
        return;
      }
      resizeSettling = false;
      refreshStops();
      armed = true;
      state.enabled = true;
      state.reason = "enabled";
      state.state = "idle";
      syncState();
      updateRestingField();
    }, 180);
  }

  function onWheel(event) {
    if (paused || !viewportCanFitBeat()) return;
    if (!event.cancelable || event.ctrlKey) return;
    if (!event.deltaY || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
    const direction = Math.sign(event.deltaY);
    if (ownsVerticalScroll(event.target, direction)) return;
    if (resizeSettling || !armed) {
      event.preventDefault();
      event.stopImmediatePropagation();
      state.inputCount += 1;
      lastBootInputAt = performance.now();
      state.suppressedCount += 1;
      state.state = resizeSettling ? "settling" : "booting";
      syncState();
      return;
    }
    if (gestureLocked) {
      event.preventDefault();
      event.stopImmediatePropagation();
      state.inputCount += 1;
      scheduleQuietRelease();
      state.suppressedCount += 1;
      syncState();
      return;
    }
    if (focusFallbackLocked || !atomicCaptureFocusIsSafe()) {
      holdFocusFallback();
      return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();
    state.inputCount += 1;
    scheduleQuietRelease();

    gestureLocked = true;
    activeGestureType = "wheel";
    moveOneBeat(direction);
  }

  addEventListener("wheel", onWheel, { capture: true, passive: false });
  addEventListener("scroll", () => {
    state.currentY = Math.round(scrollY);
    state.currentIndex = nearestIndex(scrollY);
    if (!gestureLocked && !resizeSettling) {
      state.index = state.currentIndex;
      state.settledY = state.currentY;
      state.state = armed && !paused
        ? (focusFallbackLocked || !focusAllowsGroup(beatGroups[state.currentIndex] || [])
          ? "focus-fallback"
          : "moving")
        : state.state;
      hideRestingField();
      if (focusFallbackLocked) holdFocusFallback();
      clearTimeout(nativeSettleTimer);
      nativeSettleTimer = setTimeout(() => {
        if (gestureLocked || paused || !armed) return;
        if (focusFallbackLocked) return;
        state.currentY = Math.round(scrollY);
        state.currentIndex = nearestIndex(scrollY);
        state.index = state.currentIndex;
        state.targetY = state.stops[state.index] || state.currentY;
        state.settledY = state.currentY;
        state.state = "idle";
        syncState();
        updateRestingField();
      }, 140);
    }
    syncState();
  }, { passive: true });
  function onViewportResize() {
    root.dataset.wheelBeatLayout = isDesktopViewport() ? "desktop" : "mobile";
    if (gestureLocked
      || !movementComplete
      || touchGesture.mode === "captured"
      || touchGesture.mode === "native"
      || nativeTouchActive
      || nativeTouchSettling) {
      viewportRefreshPending = true;
      return;
    }
    viewportRefreshPending = false;
    if (!paused && root.dataset.wheelBeatMode === "on") {
      cancelAnimationFrame(resizeReleaseFrame);
      resizeReleaseFrame = 0;
      resizeSettling = true;
      state.state = "settling";
      root.style.setProperty("--wheel-beat-matte-top", topInset + "px");
      root.style.setProperty("--wheel-beat-matte-bottom-start", topInset + "px");
      root.dataset.wheelBeatMatte = "on";
      syncState();
      cancelActiveMovement();
    }
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (viewportCanFitBeat()) {
        if (paused) {
          resizeSettling = false;
          paused = false;
          state.enabled = true;
          state.reason = "enabled";
          ensureCurtains();
          root.dataset.wheelBeatMode = "on";
          scheduleArm();
        } else if (!armed
          || loaderIsVisible()
        || performance.now() - lastBootInputAt < GESTURE_QUIET_MS) {
          scheduleArm();
        } else {
          settleAtCurrentGeometry();
        }
      } else {
        resizeSettling = false;
        cancelAnimationFrame(resizeReleaseFrame);
        resizeReleaseFrame = 0;
        paused = true;
        armed = false;
        state.enabled = false;
        state.reason = isDesktopViewport() ? "viewport-too-short" : "desktop-only";
        state.state = "paused";
        cancelActiveMovement();
        resetTouchGesture();
        hideRestingField();
        removeCurtains();
        root.style.removeProperty("--wheel-beat-stage-height");
        root.style.removeProperty("--wheel-beat-full-stage-height");
        root.style.removeProperty("--wheel-beat-scale-media-height");
        root.style.removeProperty("--wheel-beat-work-media-height");
        root.style.removeProperty("--wheel-beat-healed-media-height");
        root.dataset.wheelBeatMode = "paused";
        resizeTimer = 0;
        document.documentElement.offsetHeight;
        if (window.ScrollTrigger && typeof ScrollTrigger.refresh === "function") {
          ScrollTrigger.refresh();
        }
        if (lenis && typeof lenis.resize === "function") lenis.resize();
        syncState();
      }
    }, 180);
  }

  addEventListener("resize", onViewportResize);
  window.visualViewport?.addEventListener("resize", onViewportResize);

  function loaderIsVisible() {
    const loader = document.getElementById("loader");
    if (!loader || loader.hidden) return false;
    const style = getComputedStyle(loader);
    return style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0";
  }

  function scheduleArm() {
    cancelAnimationFrame(armFrame);
    if (paused) {
      state.enabled = false;
      state.state = "paused";
      syncState();
      return;
    }
    state.state = resizeSettling ? "settling" : "booting";
    syncState();
    const waitForOpening = () => {
      if (paused) return;
      const bootInputIsQuiet = performance.now() - lastBootInputAt >= GESTURE_QUIET_MS;
      if (loaderIsVisible() || !bootInputIsQuiet) {
        armFrame = requestAnimationFrame(waitForOpening);
        return;
      }
      refreshStops();
      armed = true;
      state.enabled = true;
      resizeSettling = false;
      state.state = "idle";
      syncState();
      updateRestingField();
    };
    armFrame = requestAnimationFrame(waitForOpening);
  }

  if (initiallyFits) {
    scheduleArm();
  } else {
    syncState();
    hideRestingField();
  }
  addEventListener("load", () => requestAnimationFrame(scheduleArm), { once: true });
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => requestAnimationFrame(scheduleArm));
  }
  addEventListener("click", (event) => {
    const anchor = event.target instanceof Element
      ? event.target.closest('a[href^="#"]')
      : null;
    if (anchor) yieldToNativeNavigation();
  }, true);
  addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest('input, textarea, select, [contenteditable="true"]')) return;
    const navigationKeys = new Set([
      "Home",
      "End",
      "PageUp",
      "PageDown",
      "ArrowUp",
      "ArrowDown",
      " "
    ]);
    if (navigationKeys.has(event.key)) yieldToNativeNavigation();
  }, true);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) return;
    yieldToNativeNavigation();
    resetTouchGesture();
  });
  addEventListener("pagehide", () => {
    cancelActiveMovement();
    resetTouchGesture();
  });
  addEventListener("focusin", (event) => {
    const focused = event.target;
    const fixedChrome = header?.contains(focused) || dock?.contains(focused);
    if (touchGesture.mode === "captured" && touchTargetIsNative(focused)) {
      yieldToNativeNavigation();
      resetTouchGesture();
    }
    if (state.state === "moving" && !fixedChrome) {
      cancelActiveMovement();
      state.index = nearestIndex(scrollY);
      state.currentIndex = state.index;
      state.targetY = state.stops[state.index] || Math.round(scrollY);
      state.state = "idle";
      syncState();
    }
    updateRestingField();
  });
})();
