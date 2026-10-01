"use strict";

const $ = (s) => document.querySelector(s);
const booksEl = $("#books"), emptyEl = $("#empty"), toastEl = $("#toast");

/* ---------- service worker + updates ---------- */

let swReady = Promise.resolve(null);
if ("serviceWorker" in navigator) {
  swReady = navigator.serviceWorker.register("sw.js").then((reg) => {
    if (reg.waiting && navigator.serviceWorker.controller) offerUpdate(reg.waiting);
    reg.addEventListener("updatefound", () => {
      const sw = reg.installing;
      sw.addEventListener("statechange", () => {
        // With no controller this is the first install, not an update.
        if (sw.state === "installed" && navigator.serviceWorker.controller) offerUpdate(sw);
      });
    });
    return reg;
  });
  let reloading = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (reloading) return;
    reloading = true;
    location.reload();
  });
}

function offerUpdate(sw) {
  $("#update").hidden = false;
  $("#reload").onclick = () => sw.postMessage("skipWaiting");
}

/* ---------- import ---------- */

$("#picker").addEventListener("change", async (e) => {
  const files = [...e.target.files];
  e.target.value = "";
  const done = [];
  for (const f of files) {
    try { done.push(await importFile(f)); }
    catch (err) { toast(`Couldn't import ${f.name}: ${err.message}`); return; }
  }
  await render();
  toast(done.join(" · "));
  keepStorage();
});

$("#sample").addEventListener("click", async () => {
  try {
    const res = await fetch("sample/the_spiders_thread.html");
    if (!res.ok) throw new Error(res.statusText);
    const file = new File([await res.blob()], "the_spiders_thread.html", { type: "text/html" });
    toast(await importFile(file));
    await render();
  } catch (err) {
    toast(`Couldn't load the sample: ${err.message}`);
  }
});

async function importFile(file) {
  // The metadata lives in <head>; no need to parse 10 MB to find it.
  const head = await file.slice(0, 8192).text();
  const doc = new DOMParser().parseFromString(head, "text/html");
  const meta = doc.querySelector('meta[name="reader-book"]');
  const id = (meta && meta.content) || slugFromFilename(file.name);
  const [title, range] = (doc.title || id).split(" — ");

  const existed = !!(await BookDB.get(id));
  await BookDB.put({
    id, title, range: range || "",
    blob: new Blob([file], { type: "text/html" }),
    size: file.size,
    imported: Date.now(),
  });
  return `${existed ? "Updated" : "Added"} ${title}`;
}

/* Android saves repeat downloads as "name (1).html"; that must still replace "name". */
function slugFromFilename(name) {
  return name.replace(/\.html?$/i, "").replace(/\s*\(\d+\)$/, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "book";
}

/* ---------- library ---------- */

async function render() {
  const books = (await BookDB.all()).sort((a, b) => a.title.localeCompare(b.title));
  emptyEl.hidden = books.length > 0;
  booksEl.replaceChildren(...books.map(bookItem));
  showStorage();
}

function bookItem(b) {
  const li = document.createElement("li");
  const a = document.createElement("a");
  a.href = "book/" + encodeURIComponent(b.id);
  a.innerHTML = `<span class="title"></span><span class="meta"></span>`;
  a.querySelector(".title").textContent = b.title;
  a.querySelector(".meta").textContent =
    [b.range, mb(b.size), "updated " + new Date(b.imported).toLocaleDateString()]
      .filter(Boolean).join(" · ");
  a.addEventListener("click", async (e) => {
    // Book pages exist only inside the service worker; after a hard reload
    // it isn't controlling this page yet, so wait for it first.
    if (navigator.serviceWorker && navigator.serviceWorker.controller) return;
    e.preventDefault();
    await swReady;
    await navigator.serviceWorker.ready;
    if (navigator.serviceWorker.controller) location.href = a.href;
    else location.reload();
  });

  const del = document.createElement("button");
  del.className = "btn del";
  del.title = "Delete";
  del.setAttribute("aria-label", "Delete " + b.title);
  del.textContent = "✕";
  del.addEventListener("click", async () => {
    if (!confirm(`Delete “${b.title}” and its saved place and settings?`)) return;
    await BookDB.remove(b.id);
    forgetState(b.id);
    render();
  });

  li.append(a, del);
  return li;
}

/* The reader saves under "reader:<book>:" (see "HTML file requirements" in README.md). */
function forgetState(id) {
  try {
    const prefix = `reader:${id}:`;
    Object.keys(localStorage).filter((k) => k.startsWith(prefix))
      .forEach((k) => localStorage.removeItem(k));
  } catch (e) {}
}

/* ---------- storage ---------- */

async function keepStorage() {
  if (!(navigator.storage && navigator.storage.persist)) return;
  if (!(await navigator.storage.persisted())) await navigator.storage.persist();
  showStorage();
}

async function showStorage() {
  const footer = $("#storage");
  if (!navigator.storage || !navigator.storage.estimate) { footer.textContent = ""; return; }
  const { usage } = await navigator.storage.estimate();
  const kept = navigator.storage.persisted && (await navigator.storage.persisted());
  footer.textContent = `${mb(usage || 0)} used · `;
  if (kept) {
    footer.append("kept permanently");
  } else {
    const btn = document.createElement("button");
    btn.className = "link";
    btn.textContent = "browser may clear this — keep permanently";
    btn.onclick = keepStorage;
    footer.append(btn);
  }
}

/* ---------- bits ---------- */

function mb(bytes) { return (bytes / 1048576).toFixed(1) + " MB"; }

let toastTimer;
function toast(msg) {
  if (!msg) return;
  toastEl.textContent = msg;
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.hidden = true; }, 4000);
}

render();
