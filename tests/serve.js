// Static server that mimics GitHub Pages for this project: `app/` is served
// under /tl-reader/, and unknown paths get app/404.html with a 404 status.
//
// Test hook: POST /__test/release makes sw.js report a new VERSION, the way a
// real deploy would, so the update flow can be exercised end to end.

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../app/", import.meta.url));
const BASE = "/tl-reader/";
const PORT = Number(process.env.PORT) || 4173;
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".webmanifest": "application/manifest+json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
};

let release = 0;

createServer(async (req, res) => {
  const path = decodeURIComponent(new URL(req.url, "http://x").pathname);

  if (req.method === "POST" && path === "/__test/release") {
    release++;
    return res.writeHead(204).end();
  }

  if (path === "/" || path === BASE.slice(0, -1)) {
    return res.writeHead(301, { Location: BASE }).end();
  }

  let file = path.startsWith(BASE) ? path.slice(BASE.length) || "index.html" : null;
  if (file && file.endsWith("/")) file += "index.html";
  if (file) file = normalize(file).replace(/^(\.\.[/\\])+/, "");

  try {
    let body = await readFile(join(ROOT, file ?? "\0"));
    if (file === "sw.js" && release) {
      body = body.toString().replace(/const VERSION = "([^"]*)"/, `const VERSION = "$1-test${release}"`);
    }
    res.writeHead(200, { "Content-Type": TYPES[extname(file)] || "application/octet-stream" });
    res.end(body);
  } catch {
    res.writeHead(404, { "Content-Type": TYPES[".html"] });
    res.end(await readFile(join(ROOT, "404.html")));
  }
}).listen(PORT, () => console.log(`Serving ${ROOT} at http://localhost:${PORT}${BASE}`));
