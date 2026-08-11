/* MAINTAINED ASSET — Sites protected static delivery boundary.
   Canonical path: worker/index.ts.
   Future consumer: the Sites production runtime serving Dylan's portfolio
   without exposing it to well-identified automated collectors.
   Activation: auto-load through vite.config.ts as the Worker entry point.
   Behavioral check: npm test exercises normal-browser, social-preview, robots,
   missing-agent, and known-scraper requests against the built Worker; production
   probes repeat the normal-browser and known-scraper paths after deployment.
   Retirement: remove when the portfolio leaves Sites, becomes intentionally
   indexable, or moves behind stronger authenticated access. */
import { ASSET_NAMESPACE } from "../build/protection-config.mjs";

interface Env {
  ASSETS: {
    fetch(request: Request): Promise<Response>;
  };
}

const SOCIAL_PREVIEW_USER_AGENT =
  /(?:facebookexternalhit|facebot|twitterbot|slackbot|discordbot|linkedinbot|whatsapp|telegrambot|skypeuripreview|imessagelinkpreview)/i;

const AUTOMATED_USER_AGENT =
  /(?:bot\b|crawler|spider|scrap(?:e|er|ing)|headlesschrome|phantomjs|selenium|playwright|puppeteer|gptbot|chatgpt-user|oai-searchbot|claudebot|claude-user|claude-searchbot|anthropic-ai|perplexitybot|perplexity-user|ccbot|bytespider|google-extended|amazonbot|applebot-extended|cohere-ai|meta-externalagent|meta-externalfetcher|diffbot|imagesiftbot|timpibot|youbot|curl\b|wget\b|python-requests|aiohttp|httpx|go-http-client|libwww-perl|apache-httpclient)/i;

const ROBOTS_DIRECTIVE =
  "noindex, nofollow, noarchive, nosnippet, noimageindex, max-snippet:0, max-image-preview:none, max-video-preview:0";

function shouldBlockAutomatedClient(request: Request, pathname: string): boolean {
  if (pathname === "/robots.txt") return false;

  const userAgent = request.headers.get("user-agent")?.trim() ?? "";
  if (!userAgent) return true;
  if (SOCIAL_PREVIEW_USER_AGENT.test(userAgent)) return false;

  return AUTOMATED_USER_AGENT.test(userAgent);
}

function applyProtectionHeaders(response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set("X-Robots-Tag", ROBOTS_DIRECTIVE);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  headers.set("Cross-Origin-Resource-Policy", "same-origin");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");

  const vary = headers.get("Vary");
  if (!vary) headers.set("Vary", "User-Agent");
  else if (!vary.toLowerCase().split(",").map((value) => value.trim()).includes("user-agent")) {
    headers.set("Vary", `${vary}, User-Agent`);
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

const worker = {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    const assetUrl = new URL(request.url);
    const requestedPathname = assetUrl.pathname === "/" ? "/index.html" : assetUrl.pathname;

    if (shouldBlockAutomatedClient(request, requestedPathname)) {
      return applyProtectionHeaders(
        new Response("Automated access is not permitted.", {
          status: 403,
          headers: { "Cache-Control": "private, no-store" },
        }),
      );
    }

    // Sites currently serves matching static paths before invoking the Worker,
    // even when the packaged Wrangler config requests run_worker_first. The
    // build therefore stores assets under a private namespace while public URLs
    // stay unchanged; only this classified request path knows the mapping.
    assetUrl.pathname = `${ASSET_NAMESPACE}${requestedPathname}`;

    const response = await env.ASSETS.fetch(
      new Request(assetUrl.toString(), {
        method: request.method,
        headers: request.headers,
      }),
    );

    return applyProtectionHeaders(response);
  },
};

export default worker;
