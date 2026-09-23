(() => {
  const pair = document.querySelector("#fresh-healed");
  const fresh = pair?.querySelector("[data-sleeve-fresh]");
  const healed = pair?.querySelector("[data-sleeve-healed]");
  if (!fresh || !healed) return;

  // Preserve the approved camera-pass alignment without changing either source
  // file or combining the SDR Fresh and HDR Healed pixels into one color space.
  const anchors = [[0, 0], [5, 2.8], [8, 5.5], [11, 8.5], [14.5, 11], [18, 12.5]];
  const driftTolerance = 0.12;
  const hardDriftTolerance = 0.75;
  let frame = null;
  let previousFreshTime = null;
  let buffering = false;
  let playPending = false;
  let playRejected = false;
  let followerPlaying = false;
  let needsAlignment = true;
  let alignAfter = 0;
  let retryAfter = 0;

  healed.muted = true;
  healed.playsInline = true;

  function ready() {
    return fresh.readyState >= 1 && healed.readyState >= 1
      && Number.isFinite(fresh.duration) && fresh.duration > 18
      && Number.isFinite(healed.duration) && healed.duration > 12.5;
  }

  function targetAt(time) {
    const points = [...anchors, [fresh.duration, healed.duration]];
    let segment = 0;
    while (segment < points.length - 2 && time >= points[segment + 1][0]) segment++;
    const [start, finish] = [points[segment], points[segment + 1]];
    const rate = (finish[1] - start[1]) / (finish[0] - start[0]);
    return {
      // Keep the follower on its final frame until the master's native loop.
      time: Math.min(healed.duration - 1 / 30, Math.max(0, start[1] + (time - start[0]) * rate)),
      rate: rate * fresh.playbackRate,
    };
  }

  function active() {
    return !document.hidden && !fresh.paused && !fresh.ended && !fresh.seeking && !buffering;
  }

  function stopFrames() {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
  }

  function requestPlayback() {
    if (!active() || playPending || playRejected || performance.now() < retryAfter
      || (!healed.paused && followerPlaying)) return;
    // A play request is what permits metadata-only mobile loading to progress.
    // Do not require a decoded frame or seek to a moving target before this.
    playPending = true;
    healed.play().then(() => {
      followerPlaying = active();
    }).catch((error) => {
      followerPlaying = false;
      if (error.name === "AbortError") retryAfter = performance.now() + 500;
      else playRejected = true;
    }).finally(() => {
      playPending = false;
      if (!active()) healed.pause();
      schedule();
    });
  }

  function synchronize(force = false) {
    if (force) needsAlignment = true;
    if (!active()) {
      healed.pause();
      return;
    }
    requestPlayback();
    if (!ready() || playPending || !followerPlaying || healed.paused
      || healed.seeking || healed.readyState < 2) return;
    const time = fresh.currentTime;
    const looped = previousFreshTime !== null && time < previousFreshTime - driftTolerance;
    previousFreshTime = time;
    if (looped) needsAlignment = true;
    const target = targetAt(time);
    const drift = target.time - healed.currentTime;
    const tolerance = needsAlignment ? 1 / 60 : hardDriftTolerance;
    let rate = target.rate;
    if (performance.now() >= alignAfter && Math.abs(drift) > tolerance) {
      needsAlignment = false;
      alignAfter = performance.now() + 500;
      healed.currentTime = target.time;
    } else if (!needsAlignment && Math.abs(drift) > driftTolerance) {
      // Small decoder/seek delays are caught up while playing, not by chasing
      // each completed seek with another seek before a frame can be displayed.
      rate += Math.max(-0.15, Math.min(0.15, drift * 0.5));
    } else if (Math.abs(drift) <= 1 / 60) {
      needsAlignment = false;
    }
    if (Math.abs(healed.playbackRate - rate) > 0.001) healed.playbackRate = rate;
  }

  function schedule() {
    if (frame !== null || !active() || playRejected) return;
    frame = requestAnimationFrame(() => {
      frame = null;
      synchronize();
      schedule();
    });
  }

  function resume() {
    buffering = false;
    playRejected = false;
    retryAfter = 0;
    synchronize(true);
    schedule();
  }

  function suspend() {
    stopFrames();
    followerPlaying = false;
    healed.pause();
  }

  fresh.addEventListener("playing", resume);
  fresh.addEventListener("pause", suspend);
  fresh.addEventListener("ended", suspend);
  fresh.addEventListener("waiting", () => { buffering = true; suspend(); });
  fresh.addEventListener("seeking", suspend);
  fresh.addEventListener("seeked", resume);
  fresh.addEventListener("ratechange", () => synchronize(true));
  // timeupdate also covers native loops and browsers that throttle animation frames.
  fresh.addEventListener("timeupdate", () => { synchronize(); schedule(); });
  [fresh, healed].forEach((video) => {
    video.addEventListener("loadedmetadata", () => { synchronize(); schedule(); });
    video.addEventListener("canplay", () => {
      synchronize();
      schedule();
    });
  });
  healed.addEventListener("playing", () => {
    if (!active()) { healed.pause(); return; }
    followerPlaying = true;
    schedule();
  });
  healed.addEventListener("pause", () => { followerPlaying = false; });
  healed.addEventListener("seeked", () => {
    alignAfter = performance.now() + 500;
    requestPlayback();
    schedule();
  });
  function retryFromGesture() {
    if (!active()) return;
    playRejected = false;
    retryAfter = 0;
    requestPlayback();
    schedule();
  }
  pair.addEventListener("pointerdown", retryFromGesture, { passive: true });
  pair.addEventListener("touchend", retryFromGesture, { passive: true });
  pair.addEventListener("keydown", retryFromGesture);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) suspend();
    else {
      playRejected = false;
      retryAfter = 0;
      synchronize(true);
      schedule();
    }
  });
  window.addEventListener("pagehide", suspend);
  window.addEventListener("pageshow", () => { synchronize(true); schedule(); });
  synchronize(true);
  schedule();
})();
