# TL Reader

An offline, installable web app for reading bilingual Japanese–English books on a phone. **[Open the app](https://kreir42.github.io/tl-reader/)** and tap **Try a sample**.

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

## HTML file requirements

Any HTML file opens. To get replace-on-import and per-book state, a file needs to:

1. declare `<meta name="reader-book" content="<id>">`, and
2. store its `localStorage` keys under `reader:<id>:`.
