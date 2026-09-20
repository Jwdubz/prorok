const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const script = fs.readFileSync(path.join(__dirname, "../assets/sleeve-sync.js"), "utf8");

class Events {
  listeners = new Map();
  addEventListener(name, listener) {
    const listeners = this.listeners.get(name) || [];
    listeners.push(listener);
    this.listeners.set(name, listeners);
  }
  emit(name) { (this.listeners.get(name) || []).forEach((listener) => listener()); }
}

class Video extends Events {
  currentTime = 0;
  playbackRate = 1;
  readyState = 4;
  paused = false;
  ended = false;
  seeking = false;
  playCalls = 0;
  constructor(duration) { super(); this.duration = duration; }
  pause() { this.paused = true; }
  play() { this.playCalls++; this.paused = false; return Promise.resolve(); }
}

function create({ missing = false, metadata = true } = {}) {
  const fresh = new Video(22.843333);
  const healed = new Video(15.635);
  const trio = new Video(9);
  healed.paused = true;
  if (!metadata) { fresh.readyState = 0; healed.readyState = 0; }
  const document = new Events();
  document.hidden = false;
  document.querySelector = (selector) => {
    assert.equal(selector, "#fresh-healed");
    return missing ? null : {
      querySelector: (selector) => selector === "[data-sleeve-fresh]" ? fresh : healed,
    };
  };
  const window = new Events();
  const frames = new Map();
  let id = 0;
  vm.runInNewContext(script, {
    document, window,
    requestAnimationFrame: (callback) => { frames.set(++id, callback); return id; },
    cancelAnimationFrame: (id) => frames.delete(id),
  });
  return { fresh, healed, trio, document, window, frames, tick() {
    const pending = [...frames.values()];
    frames.clear();
    pending.forEach((callback) => callback());
  } };
}

test("only the sleeve pair is selected; missing pair is safe", () => {
  const state = create({ missing: true });
  assert.equal(state.frames.size, 0);
  assert.equal(state.trio.playbackRate, 1);
  assert.equal(state.trio.currentTime, 0);
});

test("approved movement anchors and interval speeds are preserved", () => {
  const { fresh, healed, tick, frames } = create();
  for (const [time, expected, rate] of [[5, 2.8, 0.9], [8, 5.5, 1], [11, 8.5, 2.5 / 3.5], [14.5, 11, 1.5 / 3.5], [18, 12.5, 3.135 / 4.843333]]) {
    fresh.currentTime = time;
    tick();
    assert.ok(Math.abs(healed.currentTime - expected) < 0.000001);
    assert.ok(Math.abs(healed.playbackRate - rate) < 0.000001);
    assert.equal(frames.size, 1, "there is at most one pending frame");
  }
});

test("native master loop resets follower without letting follower loop early", () => {
  const { fresh, healed, tick } = create();
  fresh.currentTime = fresh.duration - 0.001;
  tick();
  assert.ok(healed.currentTime < healed.duration);
  assert.ok(healed.duration - healed.currentTime <= 1 / 30 + 0.000001);
  fresh.currentTime = 0.01;
  tick();
  assert.ok(Math.abs(healed.currentTime - 0.0056) < 0.000001);
});

test("small drift does not cause repeated seeks; material drift is corrected", () => {
  const { fresh, healed, tick } = create();
  fresh.currentTime = 4;
  healed.currentTime = 2.28;
  tick();
  assert.equal(healed.currentTime, 2.28);
  healed.currentTime = 1.5;
  tick();
  assert.ok(Math.abs(healed.currentTime - 2.24) < 0.000001);
});

test("metadata wait, pause, buffering, seek and resume do not leave runaway frames", async () => {
  const { fresh, healed, frames, tick } = create({ metadata: false });
  assert.equal(frames.size, 0);
  assert.equal(healed.paused, true);
  fresh.readyState = 4;
  healed.readyState = 4;
  healed.emit("loadedmetadata");
  assert.equal(frames.size, 1);
  await Promise.resolve();
  await Promise.resolve();
  fresh.emit("waiting");
  assert.equal(frames.size, 0);
  assert.equal(healed.paused, true);
  fresh.currentTime = 8;
  fresh.emit("playing");
  assert.equal(frames.size, 1);
  assert.equal(healed.currentTime, 5.5);
  fresh.seeking = true;
  fresh.emit("seeking");
  assert.equal(frames.size, 0);
  fresh.currentTime = 11;
  fresh.seeking = false;
  fresh.emit("seeked");
  assert.equal(healed.currentTime, 8.5);
  fresh.paused = true;
  fresh.emit("pause");
  tick();
  assert.equal(frames.size, 0);
  assert.equal(healed.paused, true);
});

test("hidden document suspends work and showing does not unpause a paused master", () => {
  const { fresh, healed, frames, document } = create();
  document.hidden = true;
  document.emit("visibilitychange");
  assert.equal(frames.size, 0);
  assert.equal(healed.paused, true);
  fresh.paused = true;
  document.hidden = false;
  document.emit("visibilitychange");
  assert.equal(frames.size, 0);
  assert.equal(healed.paused, true);
});

test("rejected play request is not retried every frame", async () => {
  const { fresh, healed, tick } = create({ metadata: false });
  healed.play = () => { healed.playCalls++; return Promise.reject(new Error("NotAllowedError")); };
  fresh.readyState = 4;
  healed.readyState = 4;
  fresh.emit("playing");
  await Promise.resolve();
  await Promise.resolve();
  for (let i = 0; i < 10; i++) tick();
  assert.equal(healed.playCalls, 1);
});
