/* MAINTAINED ASSET — protected Sites build layout.
   Canonical path: build/protect-static-assets.mjs.
   Future consumer: the Sites packaging step that must prevent static files from
   bypassing worker/index.ts before a browser or automated client is classified.
   Activation: npm run build, immediately after vinext emits dist/client.
   Behavioral check: npm test verifies public-path files are absent, protected
   copies exist, and Worker asset lookups use the private namespace.
   Retirement: remove with worker/index.ts when authenticated access replaces
   the anti-scrape boundary or Sites honors run_worker_first in production. */
import { access, mkdir, readdir, rename, rm, writeFile } from "node:fs/promises";
import { resolve, sep } from "node:path";
import { ASSET_NAMESPACE } from "./protection-config.mjs";

const clientRoot = resolve(process.cwd(), "dist", "client");
const namespaceName = ASSET_NAMESPACE.slice(1);
const protectedRoot = resolve(clientRoot, namespaceName);
const metadataFiles = new Set([".assetsignore", "_headers"]);

if (!namespaceName || !protectedRoot.startsWith(`${clientRoot}${sep}`)) {
  throw new Error("Protected asset namespace must resolve inside dist/client.");
}

await access(resolve(clientRoot, "index.html"));
await rm(protectedRoot, { recursive: true, force: true });
await mkdir(protectedRoot, { recursive: true });

for (const entry of await readdir(clientRoot, { withFileTypes: true })) {
  if (entry.name === namespaceName || metadataFiles.has(entry.name)) continue;
  await rename(resolve(clientRoot, entry.name), resolve(protectedRoot, entry.name));
}

await access(resolve(protectedRoot, "index.html"));
await access(resolve(protectedRoot, "robots.txt"));

await writeFile(
  resolve(clientRoot, "_headers"),
  `/${namespaceName}/assets/*\n` +
    "  Cache-Control: public, max-age=31536000, immutable\n" +
    `/${namespaceName}/*\n` +
    "  X-Robots-Tag: noindex, nofollow, noarchive, nosnippet, noimageindex, max-snippet:0, max-image-preview:none, max-video-preview:0\n" +
    "  X-Content-Type-Options: nosniff\n" +
    "  X-Frame-Options: DENY\n" +
    "  Referrer-Policy: strict-origin-when-cross-origin\n",
  "utf8",
);
