const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const script = process.env.SLEEVE_SYNC_BASELINE === "1"
  ? require("node:child_process").execFileSync("git", ["show", "HEAD:assets/sleeve-sync.js"], { cwd: path.join(__dirname, ".."), encoding: "utf8" })
  : fs.readFileSync(path.join(__dirname, "../assets/sleeve-sync.js"), "utf8");

class Events {
  listeners = new Map();
  addEventListener(name, listener, options = {}) {
    const listeners = this.listeners.get(name) || [];
    listeners.push({ listener, once: options.once });
    this.listeners.set(name, listeners);
  }
  emit(name) {
    const listeners = [...(this.listeners.get(name) || [])];
    this.listeners.set(name, listeners.filter((entry) => !entry.once));
    listeners.forEach(({ listener }) => listener({ type: name, target: this }));
  }
}

// This is a media state-machine regression harness, not an iPhone/WebKit emulator.
function create({ missing = false, metadata = true, frameDelay = 0, seekDelay = 0, outcomes = [] } = {}) {
  let now = 0, id = 0;
  const timers = new Map(), frames = new Map();
  const later = (callback, delay = 0) => { timers.set(++id, { callback, at: now + delay }); return id; };
  class Video extends Events {
    time = 0; playbackRate = 1; readyState = metadata ? 4 : 0;
    paused = false; ended = false; seeking = false;
    playCalls = 0; seeks = 0; motion = 0;
    constructor(duration) { super(); this.duration = duration; }
    get currentTime() { return this.time; }
    set currentTime(time) {
      this.time = time;
      this.seeks++;
      this.seeking = true;
      this.emit("seeking");
      later(() => { this.seeking = false; this.emit("seeked"); }, seekDelay);
    }
    pause() { this.paused = true; }
    play() {
      this.playCalls++;
      const outcome = outcomes.shift();
      if (outcome) return Promise.reject(Object.assign(new Error(outcome), { name: outcome }));
      this.paused = false;
      return new Promise((resolve) => later(() => {
        this.readyState = 4;
        this.emit("loadeddata");
        this.emit("playing");
        resolve();
      }, frameDelay));
    }
  }
  const fresh = new Video(22.843333), healed = new Video(15.635), trio = new Video(9);
  healed.paused = true;
  const pair = new Events();
  pair.querySelector = (selector) => selector === "[data-sleeve-fresh]" ? fresh : healed;
  const document = new Events(), window = new Events();
  document.hidden = false;
  document.querySelector = (selector) => { assert.equal(selector, "#fresh-healed"); return missing ? null : pair; };
  vm.runInNewContext(script, {
    document, window, performance: { now: () => now }, Date: { now: () => now },
    setTimeout: later, clearTimeout: (id) => timers.delete(id),
    requestAnimationFrame: (callback) => { frames.set(++id, callback); return id; },
    cancelAnimationFrame: (id) => frames.delete(id),
  });
  async function tick(ms = 16) {
    now += ms;
    for (const video of [fresh, healed]) {
      if (!video.paused && !video.seeking && video.readyState >= 2) {
        const progress = ms / 1000 * video.playbackRate;
        video.time += progress;
        video.motion += progress;
      }
    }
    // New timers wait for the next turn; event handlers cannot recursively seek forever.
    for (const [id, timer] of [...timers]) if (timer.at <= now) {
      timers.delete(id);
      timer.callback();
    }
    const pending = [...frames.values()];
    frames.clear();
    pending.forEach((callback) => callback(now));
    for (let i = 0; i < 4; i++) await Promise.resolve();
  }
  return { fresh, healed, trio, pair, document, window, frames, timers, tick,
    jump: (video, time) => { video.time = time; },
    async run(ms) { for (let elapsed = 0; elapsed < ms; elapsed += 16) await tick(Math.min(16, ms - elapsed)); },
  };
}

test("only the sleeve pair is selected; missing pair is safe", () => {
  const state = create({ missing: true });
  assert.equal(state.frames.size, 0);
  assert.equal(state.trio.playCalls, 0);
  assert.equal(state.trio.playbackRate, 1);
  assert.equal(state.trio.currentTime, 0);
});

test("metadata-only follower requests play before a decoded frame is available", async () => {
  const state = create({ metadata: false, frameDelay: 250 });
  state.fresh.readyState = 4;
  state.healed.readyState = 1;
  state.healed.emit("loadedmetadata");
  assert.equal(state.healed.playCalls, 1);
  assert.equal(state.healed.readyState, 1);
  await state.run(300);
  assert.equal(state.healed.readyState, 4);
  assert.ok(state.healed.motion > 0);
});

test("pending play and first-frame startup are not interrupted by alignment seeks", async () => {
  const state = create({ metadata: false, frameDelay: 400, seekDelay: 300 });
  state.fresh.readyState = 4;
  state.healed.readyState = 1;
  state.jump(state.fresh, 8);
  state.healed.emit("loadedmetadata");
  await state.run(350);
  assert.equal(state.healed.playCalls, 1);
  assert.equal(state.healed.seeks, 0, "decode startup gets to finish before the first seek");
  await state.run(1200);
  assert.ok(state.healed.motion > 0, "follower actually advances after startup");
});

test("300ms asynchronous seeks leave recovery time for follower playback", async () => {
  const state = create({ seekDelay: 300 });
  await state.tick(0);
  state.jump(state.fresh, 8);
  await state.run(2400);
  assert.ok(state.healed.motion > 0.8, "seeking must not starve all decoded playback");
  assert.ok(state.healed.seeks <= 4, `bounded corrections, observed ${state.healed.seeks}`);
  assert.equal(state.healed.paused, false);
});

test("approved movement anchors and interval rates remain unchanged", async () => {
  for (const [time, expected, rate] of [[5, 2.8, 0.9], [8, 5.5, 1], [11, 8.5, 2.5 / 3.5], [14.5, 11, 1.5 / 3.5], [18, 12.5, 3.135 / 4.843333]]) {
    const state = create();
    await state.tick(0);
    await state.tick(0);
    state.jump(state.fresh, time);
    state.fresh.emit("seeked");
    await state.tick(0);
    assert.ok(Math.abs(state.healed.currentTime - expected) < 0.000001);
    assert.ok(Math.abs(state.healed.playbackRate - rate) < 0.000001);
    assert.equal(state.frames.size, 1);
    assert.equal(state.trio.playCalls, 0);
  }
});

test("master loop realigns after seek recovery without starving playback", async () => {
  const state = create();
  await state.tick(0);
  await state.tick(0);
  state.jump(state.fresh, state.fresh.duration - 0.001);
  state.fresh.emit("seeked");
  await state.tick(0);
  assert.ok(state.healed.currentTime < state.healed.duration);
  state.jump(state.fresh, 0.01);
  await state.run(650);
  assert.ok(Math.abs(state.healed.currentTime - state.fresh.currentTime * 0.56) < 0.12);
  assert.equal(state.healed.paused, false);
  assert.ok(state.healed.seeks <= 2, "one correction for the end jump and one for the loop");
});

test("small drift causes no seek; large drift is corrected", async () => {
  const state = create();
  await state.tick(0);
  await state.tick(0);
  state.jump(state.fresh, 4);
  state.jump(state.healed, 2.28);
  await state.tick(0);
  assert.equal(state.healed.seeks, 0);
  state.jump(state.healed, 2);
  await state.tick(0);
  assert.equal(state.healed.seeks, 0, "moderate drift is corrected while playing");
  assert.ok(state.healed.playbackRate > 0.56 && state.healed.playbackRate <= 0.71);
  state.jump(state.healed, 1);
  await state.tick(0);
  assert.ok(Math.abs(state.healed.currentTime - 2.24) < 0.000001);
});

test("pause, buffering and master seeking suspend work and can resume", async () => {
  const state = create();
  await state.tick(0);
  for (const event of ["waiting", "seeking", "pause"]) {
    if (event === "seeking") state.fresh.seeking = true;
    if (event === "pause") state.fresh.paused = true;
    state.fresh.emit(event);
    assert.equal(state.frames.size, 0);
    assert.equal(state.healed.paused, true);
    state.fresh.seeking = false;
    state.fresh.paused = false;
    state.fresh.emit("playing");
    await state.tick(0);
    assert.equal(state.healed.paused, false);
    assert.equal(state.frames.size, 1);
  }
});

test("hidden document pauses follower and showing cannot unpause a paused master", async () => {
  const state = create({ frameDelay: 250 });
  state.document.hidden = true;
  state.document.emit("visibilitychange");
  await state.run(300);
  assert.equal(state.frames.size, 0);
  assert.equal(state.healed.paused, true, "pending play cannot escape a tab suspension");
  state.fresh.paused = true;
  state.document.hidden = false;
  state.document.emit("visibilitychange");
  assert.equal(state.frames.size, 0);
  assert.equal(state.healed.paused, true);
  const beforeGesture = state.healed.playCalls;
  state.pair.emit("pointerdown");
  assert.equal(state.healed.playCalls, beforeGesture, "gesture must not unpause a paused master");
});

test("NotAllowedError is latched until a direct pair gesture retries playback", async () => {
  const state = create({ outcomes: ["NotAllowedError"] });
  await state.tick(0);
  await state.run(2000);
  assert.equal(state.healed.playCalls, 1, "do not hammer an autoplay denial every frame");
  state.pair.emit("pointerdown");
  state.pair.emit("touchend");
  await state.tick(0);
  assert.equal(state.healed.playCalls, 2);
  assert.equal(state.healed.paused, false);
});

test("transient AbortError retries after backoff rather than remaining latched", async () => {
  const state = create({ outcomes: ["AbortError"] });
  await state.tick(0);
  await state.run(1500);
  assert.equal(state.healed.playCalls, 2);
  assert.ok(state.healed.motion > 0);
});

test("repeated transient failures are rate-limited", async () => {
  const state = create({ outcomes: Array(100).fill("AbortError") });
  await state.run(2000);
  assert.ok(state.healed.playCalls >= 2);
  assert.ok(state.healed.playCalls <= 6, `bounded retry rate, observed ${state.healed.playCalls}`);
});
