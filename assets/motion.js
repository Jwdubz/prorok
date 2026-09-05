/* Full motion remains the default. Only an explicit visitor choice is saved. */
(() => {
  const root = document.documentElement;
  const storageKey = "prorok-motion";
  const requested = new URLSearchParams(location.search).get("motion");
  let preference = requested;
  if (preference !== "full" && preference !== "reduced") {
    try { preference = localStorage.getItem(storageKey); } catch (_) { /* Storage may be unavailable. */ }
  }
  root.dataset.motion = preference === "reduced" ? "reduced" : "full";

  function remember() {
    try { localStorage.setItem(storageKey, root.dataset.motion); } catch (_) { /* Current-page control still works. */ }
  }
  if (requested === "full" || requested === "reduced") remember();

  let button;
  const isPaused = () => root.dataset.motion === "reduced";
  function syncMedia() {
    document.querySelectorAll("video, audio").forEach((media) => {
      if (isPaused()) media.pause();
      else if (media.autoplay) media.play().catch(() => {});
    });
  }
  function setPaused(paused) {
    root.dataset.motion = paused ? "reduced" : "full";
    remember();
    if (button) button.textContent = paused ? "Resume motion" : "Pause motion";
    // Keep explicit query links consistent with the choice without reloading the page.
    const url = new URL(location.href);
    if (url.searchParams.has("motion")) {
      url.searchParams.set("motion", root.dataset.motion);
      history.replaceState(history.state, "", url);
    }
    syncMedia();
    window.dispatchEvent(new CustomEvent("prorok:motion-change", { detail: { paused } }));
  }
  window.PROROK_MOTION = { get paused() { return isPaused(); }, setPaused };

  // Source changes and browser autoplay must not restart a video after Pause.
  document.addEventListener("play", (event) => {
    if (isPaused() && event.target instanceof HTMLMediaElement) event.target.pause();
  }, true);

  function mount() {
    button = document.createElement("button");
    button.type = "button";
    button.className = "motion-toggle";
    button.textContent = isPaused() ? "Resume motion" : "Pause motion";
    document.querySelector(".site-header")?.append(button);
    if (!button.isConnected) document.body.append(button);
    button.addEventListener("click", () => setPaused(!isPaused()));
    syncMedia();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount, { once: true });
  else mount();
})();
