import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";
import { ASSET_NAMESPACE } from "../build/protection-config.mjs";

const root = new URL("../", import.meta.url);
const html = await readFile(new URL("public/index.html", root), "utf8");
const robots = await readFile(new URL("public/robots.txt", root), "utf8");
const wrangler = JSON.parse(await readFile(new URL("dist/server/wrangler.json", root), "utf8"));
const { default: worker } = await import(new URL("dist/server/index.js", root));

function makeEnvironment() {
  const requests = [];
  return {
    requests,
    env: {
      ASSETS: {
        async fetch(request) {
          requests.push(request);
          return new Response("asset", {
            status: 200,
            headers: { "Content-Type": "text/html; charset=utf-8" },
          });
        },
      },
    },
  };
}

test("published HTML and robots.txt opt out of indexing", () => {
  assert.match(html, /<meta name="robots" content="noindex, nofollow, noarchive, nosnippet, noimageindex/);
  assert.match(html, /<meta name="googlebot" content="noindex, nofollow, noarchive, nosnippet, noimageindex"/);
  assert.equal(robots, "User-agent: *\nDisallow: /\n");
});

test("production routes static assets through the protection Worker", () => {
  assert.equal(wrangler.assets?.run_worker_first, true);
});

test("published assets cannot bypass the protection Worker at public paths", async () => {
  await assert.rejects(access(new URL("dist/client/index.html", root)), { code: "ENOENT" });
  await assert.rejects(access(new URL("dist/client/robots.txt", root)), { code: "ENOENT" });
  await access(new URL(`dist/client/${ASSET_NAMESPACE.slice(1)}/index.html`, root));
  await access(new URL(`dist/client/${ASSET_NAMESPACE.slice(1)}/robots.txt`, root));
});

test("normal browsers reach the site and receive protective headers", async () => {
  const { env, requests } = makeEnvironment();
  const response = await worker.fetch(
    new Request("https://prorok.jarrettwroten.com/", {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36",
      },
    }),
    env,
  );

  assert.equal(response.status, 200);
  assert.equal(requests.length, 1);
  assert.equal(new URL(requests[0].url).pathname, `${ASSET_NAMESPACE}/index.html`);
  assert.match(response.headers.get("x-robots-tag") ?? "", /noindex/);
  assert.equal(response.headers.get("cross-origin-resource-policy"), "same-origin");
  assert.match(response.headers.get("vary") ?? "", /User-Agent/i);
});

test("known scrapers and clients without an identity are blocked before assets", async () => {
  for (const userAgent of [
    "Googlebot/2.1",
    "GPTBot/1.2",
    "python-requests/2.32",
    "HeadlessChrome/140.0",
    "",
  ]) {
    const { env, requests } = makeEnvironment();
    const headers = userAgent ? { "User-Agent": userAgent } : undefined;
    const response = await worker.fetch(
      new Request("https://prorok.jarrettwroten.com/", { headers }),
      env,
    );

    assert.equal(response.status, 403, userAgent || "missing user-agent");
    assert.equal(requests.length, 0, userAgent || "missing user-agent");
    assert.equal(response.headers.get("cache-control"), "private, no-store");
  }
});

test("social link previews and robots.txt remain reachable", async () => {
  const social = makeEnvironment();
  const socialResponse = await worker.fetch(
    new Request("https://prorok.jarrettwroten.com/", {
      headers: { "User-Agent": "facebookexternalhit/1.1" },
    }),
    social.env,
  );
  assert.equal(socialResponse.status, 200);
  assert.equal(social.requests.length, 1);

  const crawler = makeEnvironment();
  const robotsResponse = await worker.fetch(
    new Request("https://prorok.jarrettwroten.com/robots.txt", {
      headers: { "User-Agent": "Googlebot/2.1" },
    }),
    crawler.env,
  );
  assert.equal(robotsResponse.status, 200);
  assert.equal(crawler.requests.length, 1);
  assert.equal(new URL(crawler.requests[0].url).pathname, `${ASSET_NAMESPACE}/robots.txt`);
});
