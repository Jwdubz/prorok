# Dylan Prorok redesign

Production: <https://prorok.jarrettwroten.com/>

The canonical website source is `public/`. Production is hosted by GitHub Pages from the root of the `gh-pages` branch; the former OpenAI Sites deployment is retired and is not a production target.

## Publishing contract

- Canonical path: `public/` on `main`, deployed as the root tree of `gh-pages` with `CNAME` and `.nojekyll` preserved.
- Future consumer: the maintainer publishing the next Dylan Prorok website update.
- Activation: auto-load - GitHub Pages publishes the `gh-pages` branch to `prorok.jarrettwroten.com`.
- Behavioral check: the secure production URL must report `Server: GitHub.com`, return the deployed `index.html` bytes, and return HTTP 200 for every referenced image and video.
- Retirement: replace this contract when `prorok.jarrettwroten.com` no longer uses GitHub Pages or when another branch becomes the production source.

GitHub Pages is static hosting. The included `robots.txt` and page-level directives are best-effort crawler guidance; they are not server-side scraper blocking.
