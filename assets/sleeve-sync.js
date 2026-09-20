(() => {
  const pair = document.querySelector("#fresh-healed");
  const fresh = pair?.querySelector("[data-sleeve-fresh]");
  const healed = pair?.querySelector("[data-sleeve-healed]");
  if (!fresh || !healed) return;

  // Preserve the approved camera-pass alignment without changing either source
  // file or combining the SDR Fresh and HDR Healed pixels into one color space.
  const anchors = [[0, 0], [5, 2.8], [8, 5.5], [11, 8.5], [14.5, 11], [18, 12.5]];
  const driftTolerance = 0.12;
  let frame = null;
  let previousFreshTime = null;
  let buffering = false;
  let playPending = false;
  let playRejected = false;

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

  function synchronize(force = false) {
    if (!ready()) {
      healed.pause();
      return;
    }
    const time = fresh.currentTime;
    const looped = previousFreshTime !== null && time < previousFreshTime - driftTolerance;
    previousFreshTime = time;
    const target = targetAt(time);
    if (Math.abs(healed.playbackRate - target.rate) > 0.001) healed.playbackRate = target.rate;
    const tolerance = force || looped ? 1 / 60 : driftTolerance;
    if (!healed.seeking && Math.abs(healed.currentTime - target.time) > tolerance) {
      healed.currentTime = target.time;
    }
    if (!active()) {
      healed.pause();
    } else if (healed.paused && !healed.seeking && healed.readyState >= 2 && !playPending && !playRejected) {
      playPending = true;
      healed.play().catch(() => { playRejected = true; }).finally(() => {
        playPending = false;
        // A pause or tab switch can happen while play() is still pending.
        if (!active()) healed.pause();
      });
    }
  }

  function schedule() {
    if (frame !== null || !active() || !ready()) return;
    frame = requestAnimationFrame(() => {
      frame = null;
      synchronize();
      schedule();
    });
  }

  function resume() {
    buffering = false;
    playRejected = false;
    synchronize(true);
    schedule();
  }

  function suspend() {
    stopFrames();
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
    video.addEventListener("loadedmetadata", () => { synchronize(true); schedule(); });
    video.addEventListener("canplay", () => {
      playRejected = false;
      synchronize();
      schedule();
    });
  });
  healed.addEventListener("seeked", () => { synchronize(); schedule(); });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) suspend();
    else {
      playRejected = false;
      synchronize(true);
      schedule();
    }
  });
  window.addEventListener("pagehide", suspend);
  window.addEventListener("pageshow", () => { synchronize(true); schedule(); });
  synchronize(true);
  schedule();
})();
