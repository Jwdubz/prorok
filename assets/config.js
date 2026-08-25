/* Integration seam for inquiry and newsletter delivery.
   GitHub Pages cannot process multipart forms or store uploads.
   Set formEndpoint to a same-origin or CORS-enabled POST URL when ready.
   Leave it empty to fail openly to the existing Acuity consultation.
   Never place secrets, API keys, or inbox addresses here. */
/* Launch seam: scripts/configure-launch.py rewrites origin, robots, canonicals,
   Open Graph, JSON-LD, and sitemaps. Default rehearsal stays on the GitHub
   preview host and remains non-indexable. Pass --indexable only for a real
   production origin cutover. This file never holds secrets. */
window.PROROK = {
  origin: "https://prorok.jarrettwroten.com",
  consultationUrl: "https://dylanprorok.as.me/schedule/b21deb93/appointment/61957220/calendar/10046225",
  schedulingUrl: "https://dylanprorok.as.me/",
  formEndpoint: "",
  newsletterEndpoint: "",
  acceptedImageTypes: ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"],
  maxImageBytes: 10 * 1024 * 1024
};
