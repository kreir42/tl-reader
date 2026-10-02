# TL Reader

An offline, installable web app for reading bilingual Japanese–English books on a phone. **[Open the app](https://kreir42.github.io/tl-reader/)** and tap **Try a sample**.

It opens any self-contained HTML file. Books built with [`make_reader.py`](#making-a-book) also get a reading position per book and four reading modes.

<p>
  <img src="docs/library-light.png" width="240" alt="Library with one book">
  <img src="docs/book-mix-light.png" width="240" alt="Interleaved reading mode with furigana">
  <img src="docs/book-split-dark.png" width="240" alt="Side-by-side reading mode in dark theme">
</p>

## Why

Each of my bilingual books is a single HTML file that saves your place in `localStorage`. On Android, Firefox won't open local HTML files. Chrome does, but through a `content://` URL that gets a new origin every time, so your place is lost whenever the browser closes. TL Reader gives every book a permanent home on one origin.

## Features

- Import books from the device. Re-importing a book replaces it and keeps your place.
- Each book remembers its own position and display settings.
- Works fully offline. Books never leave the device.
- Native text selection, for looking words up in a dictionary.
- Light and dark themes.

## Making a book

`make_reader.py` (Python 3, no dependencies) builds a single HTML book from aligned chapter pairs:

```bash
python3 make_reader.py --all --dir sample --title "The Spider's Thread"   # writes sample/the_spiders_thread.html
python3 make_reader.py JP.txt EN.txt -o chapter.html                      # one chapter
```

Each chapter is a pair of UTF-8 `.txt` files named `NNN - <title>.txt`. The English file's title starts with the index again (`001 - 001 The Spider's Thread I.txt`), which is how `--all` tells the two sides apart. In both files the first line is the chapter title and paragraphs are separated by blank lines. Paragraph *n* of the English file translates paragraph *n* of the Japanese file. Beyond that:

- Japanese ruby is written `｜base《reading》`. A reading made only of dots becomes emphasis marks.
- A `[TL Note: …]` line directly under an English paragraph annotates that paragraph and doesn't count toward the alignment.
- An optional `[tag, tag]` line directly under the English title shows the tags as chips under the title.

A count mismatch is reported as a warning, and the unmatched paragraphs are marked in the output.

`sample/` holds the source for the built-in sample book. After changing it, rebuild into `app/sample/`:

```bash
python3 make_reader.py --all --dir sample --title "The Spider's Thread" -o app/sample/the_spiders_thread.html
```

## HTML file requirements

Any HTML file opens. To get replace-on-import and per-book state, a file needs to:

1. declare `<meta name="reader-book" content="<id>">`, and
2. store its `localStorage` keys under `reader:<id>:`.
