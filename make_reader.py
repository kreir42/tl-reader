#!/usr/bin/env python3
"""
make_reader.py — Build a bilingual HTML reader from aligned JP/EN chapter files.

Usage:
    make_reader.py JP.txt EN.txt [-o out.html]
    make_reader.py --all [--dir .] [-o out.html]

Pairing in --all mode is by the 3-digit index prefix: `NNN - ` files whose
remainder starts with `NNN ` are the English side, everything else is Japanese.
Only indices that have both sides are built.

The output is a single self-contained file (no network, no build step) with a
bottom bar offering four reading modes: JP only, EN only, side-by-side, and
interleaved-with-spoilers.

In --all mode the file is named after the book (`The Spider's Thread` ->
`the_spiders_thread.html`). The same slug namespaces the reader's saved state
and is exposed as `<meta name="reader-book">`, so several books can share one
origin (TL Reader) without overwriting each other's place.
"""

import argparse
import glob
import html
import os
import re
import sys
import unicodedata

TL_NOTE_RE = re.compile(r"^\[TL\s*Note:", re.IGNORECASE)
TAG_LINE_RE = re.compile(r"^\[(.*)\]$")

# Aozora-style ruby: |base《ruby》 (both ASCII and full-width pipe).
RUBY_RE = re.compile(r"[|｜]([^|｜《》\n]+)《([^》\n]+)》")

# A ruby body of only dots is *bouten* (emphasis marks), not furigana.
BOUTEN_RE = re.compile(r"^[・、﹅・]+$")

EN_FILE_RE = re.compile(r"^(\d{3}) - \d{3}[ .]")
ANY_FILE_RE = re.compile(r"^(\d{3}) - ")


def slugify(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    # Drop apostrophes rather than splitting on them: "Son's" -> "sons", not "son_s".
    ascii_name = re.sub(r"['\u2019]", "", ascii_name.lower())
    return re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_") or "reader"


def read_lines(path):
    with open(path, encoding="utf-8-sig") as f:
        return f.read().splitlines()


def parse_japanese(path):
    return [l for l in read_lines(path) if l.strip()]


def parse_english(path):
    """Returns (paras, tags) where:
    paras is [{'text': str, 'notes': [str, ...]}], TL notes bound to the
    paragraph they follow (or, at the top of a file, the one they precede).
    tags is a list of lowercase string tags from an optional `[...]` line on
    line 2 of the file. A file without one and a file with an empty `[]` both
    yield tags == []. Only a line that actually looks like `[...]` is ever
    treated as (and removed as) a tag line."""
    lines = read_lines(path)
    tags = []
    tag_line_idx = None

    if len(lines) > 1:
        line2_strip = lines[1].strip()
        m = TAG_LINE_RE.match(line2_strip)
        if m and not TL_NOTE_RE.match(line2_strip):
            tag_line_idx = 1
            inner = m.group(1).strip()
            if inner:
                tags = [t.strip().lower() for t in inner.split(",") if t.strip()]

    paras = []
    pending = []
    for idx, line in enumerate(lines):
        if idx == tag_line_idx:
            continue
        if not line.strip():
            continue
        if TL_NOTE_RE.match(line.strip()):
            if paras:
                paras[-1]["notes"].append(line.strip())
            else:
                pending.append(line.strip())
        else:
            paras.append({"text": line, "notes": pending})
            pending = []
    if pending and paras:
        paras[-1]["notes"].extend(pending)
    return paras, tags


def markup(text):
    """Escape, then convert Aozora ruby to <ruby>/bouten."""
    out = html.escape(text, quote=False)

    def repl(m):
        base, ruby = m.group(1), m.group(2)
        if BOUTEN_RE.match(ruby):
            return f'<em class="bouten">{base}</em>'
        return f"<ruby>{base}<rt>{ruby}</rt></ruby>"

    return RUBY_RE.sub(repl, out)


def pair_up(jp_paras, en_paras, label):
    """Zip the two sides, tolerating (and reporting) a count mismatch."""
    if len(jp_paras) != len(en_paras):
        print(
            f"warning: {label}: {len(jp_paras)} JP paragraphs vs "
            f"{len(en_paras)} EN paragraphs — unmatched ones are marked "
            f'"orphan" in the output.',
            file=sys.stderr,
        )
    pairs = []
    for i in range(max(len(jp_paras), len(en_paras))):
        jp = jp_paras[i] if i < len(jp_paras) else None
        en = en_paras[i] if i < len(en_paras) else None
        pairs.append((jp, en))
    return pairs


def render_pair(jp, en, cls="pair", tags=None):
    orphan = " orphan" if jp is None or en is None else ""
    bits = [f'<div class="{cls}{orphan}">']
    if jp is not None:
        bits.append(f'<p class="jp">{markup(jp)}</p>')
    if en is not None:
        for note in en["notes"]:
            bits.append(f'<p class="tl">{markup(note)}</p>')
        bits.append(f'<p class="en"><span>{markup(en["text"])}</span></p>')
        if tags:
            tags_html = "".join(
                f'<span class="tag">{html.escape(t)}</span>' for t in tags
            )
            bits.append(f'<div class="tags">{tags_html}</div>')
    bits.append("</div>")
    return "".join(bits)


def render_chapter(index, jp_path, en_path):
    jp_paras = parse_japanese(jp_path)
    en_paras, tags = parse_english(en_path)
    pairs = pair_up(jp_paras, en_paras, os.path.basename(en_path))

    jp_title = pairs[0][0] if pairs and pairs[0][0] else index
    en_title = pairs[0][1]["text"] if pairs and pairs[0][1] else index

    body = [f'<article class="chapter" id="ch{index}">']
    body.append('<header class="chapter-head">')
    body.append(render_pair(pairs[0][0], pairs[0][1], cls="pair title", tags=tags))
    body.append("</header>")
    for jp, en in pairs[1:]:
        body.append(render_pair(jp, en))
    body.append("</article>")

    return {
        "id": f"ch{index}",
        "index": index,
        "jp_title": jp_title,
        "en_title": en_title,
        "html": "\n".join(body),
    }


def discover_pairs(directory):
    """Map index -> (jp_path, en_path) for every index that has both sides."""
    en_by_index = {}
    all_by_index = {}
    jp_char_re = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")
    for path in sorted(glob.glob(os.path.join(directory, "*.txt"))):
        name = os.path.basename(path)
        m = ANY_FILE_RE.match(name)
        if not m:
            continue
        index = m.group(1)
        if EN_FILE_RE.match(name) or not jp_char_re.search(name):
            en_by_index[index] = path
        else:
            all_by_index.setdefault(index, path)
    return [
        (i, all_by_index[i], en_by_index[i])
        for i in sorted(en_by_index)
        if i in all_by_index
    ]


CSS = r"""
:root {
  --fs: 18px;
  --bg: #fbf9f5; --fg: #221f1c; --muted: #6f6862; --rule: #e4ded4;
  --accent: #8a4436; --spoiler: #cec6ba; --bar: #ffffff; --barline: #e4ded4;
  --note: #6a6f57; --shadow: rgba(40, 32, 24, .13);
}
:root[data-theme="dark"] {
  --bg: #16171b; --fg: #dad6cf; --muted: #918a82; --rule: #33353c;
  --accent: #d9917f; --spoiler: #3c4048; --bar: #1e2026; --barline: #33353c;
  --note: #9aa77e; --shadow: rgba(0, 0, 0, .5);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #16171b; --fg: #dad6cf; --muted: #918a82; --rule: #33353c;
    --accent: #d9917f; --spoiler: #3c4048; --bar: #1e2026; --barline: #33353c;
    --note: #9aa77e; --shadow: rgba(0, 0, 0, .5);
  }
}

* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; scroll-behavior: auto; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font-size: var(--fs);
  font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  padding-bottom: 7.5rem;
}

.wrap {
  max-width: 44rem;
  margin: 0 auto;
  padding: 2.5rem 1.25rem 0;
}
body.mode-split .wrap { max-width: 84rem; }

/* ---------- paragraphs ---------- */
.pair { margin: 0 0 1.15em; }
.pair p { margin: 0; }

.jp {
  font-family: "Hiragino Mincho ProN", "Yu Mincho", "YuMincho",
               "Noto Serif JP", "Noto Serif CJK JP", "Source Han Serif",
               "MS Mincho", serif;
  line-height: 2.05;              /* headroom so <rt> never clips */
  letter-spacing: .02em;
}
.en { line-height: 1.68; }
.tl {
  font-size: .82em;
  line-height: 1.55;
  color: var(--note);
  font-style: italic;
  border-left: 2px solid var(--rule);
  padding-left: .7em;
  margin: .35em 0 .35em .2em;
}

ruby { ruby-position: over; }
rt {
  font-size: .5em;
  font-weight: 400;
  letter-spacing: 0;
  opacity: .78;
  user-select: none;
}
body.furigana-off rt { display: none; }

em.bouten {
  font-style: normal;
  -webkit-text-emphasis: filled dot;
  text-emphasis: filled dot;
  -webkit-text-emphasis-position: over right;
  text-emphasis-position: over right;
}

.orphan > p { outline: 1px dashed var(--accent); outline-offset: .3em; }

/* ---------- chapter headings ---------- */
.chapter { margin: 0 0 4.5rem; }
.chapter + .chapter { border-top: 1px solid var(--rule); padding-top: 3rem; }
.chapter-head { margin: 0 0 2.2rem; }
.pair.title p { font-weight: 600; }
.pair.title .jp { font-size: 1.5em; line-height: 1.75; }
.pair.title .en { font-size: 1.32em; line-height: 1.35; }
.pair.title .en span { background: none !important; color: inherit !important; }

/* ---------- tags ---------- */
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin: 0.5rem 0 0;
}
.tag {
  display: inline-block;
  font-size: 0.62em;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-weight: 500;
  text-transform: lowercase;
  letter-spacing: 0.02em;
  padding: 0.15em 0.55em;
  border-radius: 9999px;
  background: var(--rule);
  color: var(--muted);
  border: 1px solid var(--barline);
  line-height: 1.4;
  user-select: none;
}

/* ---------- mode: japanese only ---------- */
body.mode-jp .en, body.mode-jp .tags { display: none; }

/* ---------- mode: english only ---------- */
body.mode-en .jp { display: none; }
/* the note follows the paragraph it annotates; only mode 4 wants it first */
body.mode-en .pair { display: flex; flex-direction: column; }
body.mode-en .en { order: 1; }
body.mode-en .tags { order: 2; }
body.mode-en .tl { order: 3; }

/* ---------- mode: side by side ---------- */
body.mode-split .pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-areas: "jp en" "jp tl";
  gap: 0 2.6rem;
  align-items: start;
  margin-bottom: 1.35em;
}
body.mode-split .pair.title {
  grid-template-areas: "jp en" "jp tags" "jp tl";
}
body.mode-split .jp { grid-area: jp; }
body.mode-split .en { grid-area: en; }
body.mode-split .tags { grid-area: tags; }
body.mode-split .tl { grid-area: tl; }
/* one continuous rule down the gutter, rather than a segment per pair */
body.mode-split .wrap {
  background: linear-gradient(var(--rule), var(--rule)) 50% 0 / 1px 100% no-repeat;
}

/* ---------- mode: interleaved with spoilers ---------- */
body.mode-mix .pair { padding-bottom: .35em; }
body.mode-mix .en { cursor: pointer; margin-top: .25em; }
body.mode-mix .en > span {
  background: var(--spoiler);
  color: transparent;
  text-shadow: none;
  border-radius: 3px;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
  padding: 0 .12em;
  transition: background-color .12s ease, color .12s ease;
}
body.mode-mix .en.revealed > span,
body.mode-mix.reveal-all .en > span {
  background: transparent;
  color: inherit;
  cursor: auto;
}
body.mode-mix .en.revealed, body.mode-mix.reveal-all .en { cursor: auto; }
body.mode-mix .en > span * { visibility: inherit; }
body.mode-mix .en:not(.revealed) > span { user-select: none; }
body.mode-mix.reveal-all .en:not(.revealed) > span { user-select: auto; }

body.notes-off .tl { display: none; }

/* ---------- bottom bar ---------- */
.bar {
  position: fixed;
  left: 0; right: 0; bottom: 0;
  z-index: 20;
  background: var(--bar);
  border-top: 1px solid var(--barline);
  box-shadow: 0 -2px 14px var(--shadow);
  padding: .5rem max(.6rem, env(safe-area-inset-left))
           calc(.5rem + env(safe-area-inset-bottom))
           max(.6rem, env(safe-area-inset-right));
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 14px;
}
.bar-inner {
  max-width: 84rem;
  margin: 0 auto;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .4rem .75rem;
  justify-content: space-between;
}
.group { display: flex; align-items: center; gap: .3rem; }

.modes { border: 1px solid var(--barline); border-radius: 8px; overflow: hidden; gap: 0; }
.modes button {
  border: 0;
  border-right: 1px solid var(--barline);
  background: transparent;
  color: var(--muted);
  font: inherit;
  padding: .42rem .7rem;
  cursor: pointer;
  white-space: nowrap;
}
.modes button:last-child { border-right: 0; }
.modes button:hover { color: var(--fg); background: color-mix(in srgb, var(--fg) 6%, transparent); }
.modes button[aria-pressed="true"] {
  background: var(--accent);
  color: #fff;
}

.bar button.plain, .bar select {
  border: 1px solid var(--barline);
  background: transparent;
  color: var(--muted);
  font: inherit;
  border-radius: 7px;
  padding: .38rem .55rem;
  cursor: pointer;
}
.bar button.plain:hover, .bar select:hover { color: var(--fg); }
.bar button.plain[aria-pressed="true"] { color: var(--fg); border-color: var(--accent); }
.bar select { max-width: 15rem; background: var(--bar); }
.bar .sep { width: 1px; height: 1.4rem; background: var(--barline); }
#revealAll[hidden] { display: none; }
.long { display: inline; }
.short { display: none; }

@media (max-width: 720px) {
  .long { display: none; }
  .short { display: inline; }
  .bar-inner { justify-content: center; gap: .35rem .5rem; }
  .bar select { max-width: 9.5rem; }
  body.mode-split .wrap { padding-left: .6rem; padding-right: .6rem; }
  body.mode-split .pair { gap: 0 1rem; }
}

@media print {
  .bar { display: none; }
  body { padding-bottom: 0; }
}
"""

JS = r"""
(function () {
  var KEY = "reader:__BOOK__:";
  var body = document.body;
  var root = document.documentElement;
  var MODES = ["jp", "en", "split", "mix"];

  function load(k, d) { try { var v = localStorage.getItem(KEY + k); return v === null ? d : v; } catch (e) { return d; } }
  function save(k, v) { try { localStorage.setItem(KEY + k, v); } catch (e) {} }

  /* ---- keep the reader's place across any layout change ---- */
  function anchor() {
    var pairs = document.querySelectorAll(".pair");
    var best = null, bestTop = -Infinity;
    for (var i = 0; i < pairs.length; i++) {
      var t = pairs[i].getBoundingClientRect().top;
      if (t <= 80 && t > bestTop) { bestTop = t; best = pairs[i]; }
      if (t > 80) break;
    }
    if (!best && pairs.length) { best = pairs[0]; bestTop = best.getBoundingClientRect().top; }
    return best ? { el: best, top: bestTop } : null;
  }
  function preserve(fn) {
    var a = anchor();
    fn();
    if (!a) return;
    function fix() { window.scrollBy(0, a.el.getBoundingClientRect().top - a.top); }
    fix();
    requestAnimationFrame(fix);   /* idempotent: converges if layout settles late */
  }

  /* ---- keep the bar from covering the last paragraphs ---- */
  var bar = document.querySelector(".bar");
  function padForBar() { body.style.paddingBottom = (bar.offsetHeight + 28) + "px"; }
  window.addEventListener("resize", padForBar);

  /* ---- mode ---- */
  var modeButtons = document.querySelectorAll(".modes button");
  function setMode(m, remember) {
    MODES.forEach(function (x) { body.classList.toggle("mode-" + x, x === m); });
    modeButtons.forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.mode === m)); });
    document.getElementById("revealAll").hidden = (m !== "mix");
    padForBar();
    if (remember !== false) save("mode", m);
  }
  modeButtons.forEach(function (b) {
    b.addEventListener("click", function () { preserve(function () { setMode(b.dataset.mode); }); });
  });

  /* ---- spoilers ---- */
  document.addEventListener("click", function (e) {
    if (!body.classList.contains("mode-mix")) return;
    var p = e.target.closest(".en");
    if (!p || p.closest(".title")) return;
    if (window.getSelection && String(window.getSelection()).length) return;
    p.classList.toggle("revealed");
  });
  var revealAll = document.getElementById("revealAll");
  revealAll.addEventListener("click", function () {
    var on = !body.classList.contains("reveal-all");
    preserve(function () {
      body.classList.toggle("reveal-all", on);
      document.querySelectorAll(".en.revealed").forEach(function (p) { p.classList.remove("revealed"); });
    });
    revealAll.setAttribute("aria-pressed", String(on));
    revealAll.querySelector(".long").textContent = on ? "Hide all" : "Reveal all";
    revealAll.querySelector(".short").textContent = on ? "Hide" : "Reveal";
  });

  /* ---- toggles ---- */
  function toggle(id, cls, key, offValue) {
    var btn = document.getElementById(id);
    function apply(off, remember) {
      body.classList.toggle(cls, off);
      btn.setAttribute("aria-pressed", String(!off));
      if (remember !== false) save(key, off ? "off" : "on");
    }
    btn.addEventListener("click", function () {
      preserve(function () { apply(!body.classList.contains(cls)); });
    });
    apply(load(key, offValue) === "off", false);
  }
  toggle("furiganaBtn", "furigana-off", "furigana", "on");
  toggle("notesBtn", "notes-off", "notes", "on");

  /* ---- text size ---- */
  var SIZES = [15, 16, 17, 18, 20, 22, 24, 27];
  var size = parseInt(load("size", "18"), 10);
  function applySize(remember) {
    root.style.setProperty("--fs", size + "px");
    if (remember !== false) save("size", String(size));
  }
  function step(dir) {
    var i = SIZES.indexOf(size);
    if (i < 0) i = SIZES.indexOf(18);
    i = Math.min(SIZES.length - 1, Math.max(0, i + dir));
    size = SIZES[i];
    preserve(applySize);
  }
  document.getElementById("smaller").addEventListener("click", function () { step(-1); });
  document.getElementById("bigger").addEventListener("click", function () { step(1); });
  applySize(false);

  /* ---- theme ---- */
  var themeBtn = document.getElementById("themeBtn");
  function applyTheme(t, remember) {
    if (t === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", t);
    themeBtn.textContent = t === "dark" ? "◑" : (t === "light" ? "○" : "◐");
    themeBtn.title = "Theme: " + t;
    if (remember !== false) save("theme", t);
  }
  var theme = load("theme", "system");
  themeBtn.addEventListener("click", function () {
    theme = theme === "system" ? "light" : (theme === "light" ? "dark" : "system");
    applyTheme(theme);
  });
  applyTheme(theme, false);

  /* ---- chapters ---- */
  var sel = document.getElementById("chapSel");
  var chapters = sel ? Array.prototype.map.call(sel.options, function (o) { return o.value; }) : [];
  function goto(id) {
    var el = document.getElementById(id);
    if (el) { el.scrollIntoView({ block: "start" }); window.scrollBy(0, -12); }
  }
  if (sel) {
    sel.addEventListener("change", function () { goto(sel.value); });
    document.getElementById("prevCh").addEventListener("click", function () {
      var i = chapters.indexOf(current()); if (i > 0) { sel.value = chapters[i - 1]; goto(sel.value); }
    });
    document.getElementById("nextCh").addEventListener("click", function () {
      var i = chapters.indexOf(current()); if (i > -1 && i < chapters.length - 1) { sel.value = chapters[i + 1]; goto(sel.value); }
    });
  }
  var arts = document.querySelectorAll(".chapter");
  function current() {
    var id = arts.length ? arts[0].id : "";
    for (var i = 0; i < arts.length; i++) {
      if (arts[i].getBoundingClientRect().top <= 80) id = arts[i].id; else break;
    }
    return id;
  }

  /* ---- remember reading position ---- */
  var ticking = false;
  window.addEventListener("scroll", function () {
    if (ticking) return;
    ticking = true;
    setTimeout(function () {
      ticking = false;
      var id = current();
      if (sel && sel.value !== id) sel.value = id;
      var a = anchor();
      if (a) {
        var art = a.el.closest(".chapter");
        var idx = Array.prototype.indexOf.call(art.querySelectorAll(".pair"), a.el);
        save("pos", JSON.stringify({ ch: art.id, i: idx, top: Math.round(a.top) }));
      }
    }, 250);
  }, { passive: true });

  setMode(MODES.indexOf(load("mode", "mix")) > -1 ? load("mode", "mix") : "mix", false);

  try {
    var pos = JSON.parse(load("pos", "null"));
    if (pos && !location.hash) {
      var art = document.getElementById(pos.ch);
      if (art) {
        var pairs = art.querySelectorAll(".pair");
        var el = pairs[Math.min(pos.i, pairs.length - 1)];
        if (el) {
          el.scrollIntoView({ block: "start" });
          window.scrollBy(0, -(pos.top || 0));
        }
      }
    }
  } catch (e) {}
})();
"""


BAR = """
<nav class="bar" aria-label="Reading controls">
  <div class="bar-inner">
    <div class="group modes" role="group" aria-label="Reading mode">
      <button data-mode="jp" aria-pressed="false" title="Japanese only">日本語</button>
      <button data-mode="en" aria-pressed="false" title="English only">EN</button>
      <button data-mode="split" aria-pressed="false" title="Side by side">日 | EN</button>
      <button data-mode="mix" aria-pressed="false" title="Interleaved, English hidden">日 + EN</button>
    </div>
    <div class="group">
      <button class="plain" id="revealAll" aria-pressed="false" title="Reveal every English paragraph"><span class="long">Reveal all</span><span class="short">Reveal</span></button>
      <button class="plain" id="furiganaBtn" aria-pressed="true" title="Show or hide furigana">ふり<span class="long">がな</span></button>
      <button class="plain" id="notesBtn" aria-pressed="true" title="Show or hide translator's notes">TL</button>
      <span class="sep"></span>
      <button class="plain" id="smaller" title="Smaller text">A&minus;</button>
      <button class="plain" id="bigger" title="Larger text">A+</button>
      <button class="plain" id="themeBtn" title="Theme">&#9686;</button>
    </div>
    __CHAPTERNAV__
  </div>
</nav>
"""


def chapter_nav(chapters):
    if len(chapters) < 2:
        return ""
    options = "".join(
        '<option value="{id}">{i} &middot; {t}</option>'.format(
            id=c["id"], i=c["index"], t=html.escape(c["en_title"], quote=True)
        )
        for c in chapters
    )
    return (
        '<div class="group">'
        '<button class="plain" id="prevCh" title="Previous chapter">&lsaquo;</button>'
        f'<select id="chapSel" aria-label="Jump to chapter">{options}</select>'
        '<button class="plain" id="nextCh" title="Next chapter">&rsaquo;</button>'
        "</div>"
    )


def build_document(chapters, doc_title, book):
    bar = BAR.replace("__CHAPTERNAV__", chapter_nav(chapters))
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="reader-book" content="{book}">
<title>{html.escape(doc_title, quote=False)}</title>
<style>{CSS}</style>
</head>
<body class="mode-mix">
<main class="wrap">
{chr(10).join(c["html"] for c in chapters)}
</main>
{bar}
<script>{JS.replace("__BOOK__", book)}</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(
        description="Build a bilingual HTML reader from aligned JP/EN chapter .txt files."
    )
    ap.add_argument("jp", nargs="?", help="Japanese chapter .txt")
    ap.add_argument("en", nargs="?", help="English translated chapter .txt")
    ap.add_argument(
        "--all",
        action="store_true",
        help="Build every chapter that has both sides into one HTML file.",
    )
    ap.add_argument("--dir", default=".", help="Folder to scan with --all (default: .)")
    ap.add_argument("-o", "--output", help="Output .html path")
    ap.add_argument(
        "--title", help="Document title prefix (default: the book folder's name)"
    )
    args = ap.parse_args()

    if args.all:
        found = discover_pairs(args.dir)
        if not found:
            ap.error(f"no JP/EN pairs found in {args.dir!r}")
        chapters = [render_chapter(i, jp, en) for i, jp, en in found]
        title = args.title or os.path.basename(os.path.abspath(args.dir))
        doc_title = f"{title} — {found[0][0]}–{found[-1][0]}"
        out = args.output or os.path.join(args.dir, slugify(title) + ".html")
    else:
        if not (args.jp and args.en):
            ap.error("give a JP and an EN file, or use --all")
        m = ANY_FILE_RE.match(os.path.basename(args.jp))
        index = m.group(1) if m else "001"
        chapters = [render_chapter(index, args.jp, args.en)]
        title = args.title or os.path.basename(os.path.abspath(os.path.dirname(args.en)))
        doc_title = f"{title} — {chapters[0]['en_title']}"
        out = args.output or os.path.splitext(args.en)[0] + ".html"

    with open(out, "w", encoding="utf-8") as f:
        f.write(build_document(chapters, doc_title, slugify(title)))

    pairs = sum(c["html"].count('<div class="pair') for c in chapters)
    print(f"wrote {out} — {len(chapters)} chapter(s), {pairs} paragraph pairs")


if __name__ == "__main__":
    main()
