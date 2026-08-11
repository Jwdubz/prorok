/* MAINTAINED ASSET — Sites static delivery bridge.
   Canonical path: worker/index.ts.
   Future consumer: the Sites production runtime serving Dylan's portfolio.
   Activation: auto-load through vite.config.ts as the Worker entry point.
   Behavioral check: PASS — Wrangler served the packaged root with HTTP 200;
   Sites production served every local image/video byte-identically (2026-08-10).
   Retirement: remove when the portfolio leaves Sites or uses native app routes. */
interface Env {
  ASSETS: Fetcher;
}

const worker = {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    const assetUrl = new URL(request.url);
    if (assetUrl.pathname === "/") assetUrl.pathname = "/index.html";

    return env.ASSETS.fetch(
      new Request(assetUrl.toString(), {
        method: request.method,
        headers: request.headers,
      }),
    );
  },
};

export default worker;
