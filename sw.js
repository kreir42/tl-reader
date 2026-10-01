/* Bump VERSION on every release: the browser only notices an update when
   this file's bytes change, and the old cache is dropped by name. */
const VERSION = "v1";
const CACHE = "tl-reader-" + VERSION;
const SHELL = ["./", "index.html", "app.js", "db.js", "style.css", "manifest.webmanifest",
               "icon.svg", "icon-192.png", "icon-512.png"];

importScripts("db.js");

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  // No skipWaiting here: the page asks for it, so an update never swaps the
  // app out from under an open book.
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== CACHE) await caches.delete(k);
    await self.clients.claim();
  })());
});

self.addEventListener("message", (e) => {
  if (e.data === "skipWaiting") self.skipWaiting();
});

const BOOK_PATH = new URL("book/", self.registration.scope).pathname;

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;

  if (url.pathname.startsWith(BOOK_PATH)) {
    e.respondWith(serveBook(decodeURIComponent(url.pathname.slice(BOOK_PATH.length))));
    return;
  }
  e.respondWith(caches.match(e.request, { ignoreSearch: true })
    .then((hit) => hit || fetch(e.request)));
});

async function serveBook(id) {
  const book = await BookDB.get(id);
  if (!book) {
    return new Response(
      `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">` +
      `<p style="font-family:sans-serif;padding:1rem">Book not found. <a href="../">Library</a></p>`,
      { status: 404, headers: { "Content-Type": "text/html; charset=utf-8" } });
  }
  return new Response(book.blob, {
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
  });
}
