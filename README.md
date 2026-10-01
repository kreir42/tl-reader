# TL Reader

A tiny offline web app for reading the bilingual readers built by `make_reader.py` on a phone. It is meant for Firefox on Android, and also works in Chrome.

It contains only the app itself. Books are imported from files on the device and stored in that browser's IndexedDB. They are never uploaded anywhere.

## Why it exists

Android browsers open local `.html` files through a `content://` URL, which gets a new origin each time. Anything the reader saves in `localStorage` (position, mode, text size, theme) is lost when the browser is closed. Serving every book from one fixed origin makes that state stick.

## How it works

| File | Role |
| :--- | :--- |
| `index.html`, `app.js`, `style.css` | Library: import, list, delete, storage status, update prompt |
| `db.js` | IndexedDB wrapper, shared by the page and the service worker |
| `sw.js` | Caches the app for offline use; serves each stored book at `book/<id>` |
| `404.html` | GitHub Pages fallback: a `book/` link opened before the worker controls the page goes back to the library |
| `manifest.webmanifest`, `icon*` | Installability ("Add app to Home screen") |

- **Book identity** comes from `<meta name="reader-book">`, which `make_reader.py` writes. If a file doesn't have it, the file name is used, with a trailing ` (1)` stripped. Importing a book that is already in the library replaces it.
- **Reading state** belongs to the reader page itself, not to the app. It lives in `localStorage` under `reader:<id>:`. Position is stored as chapter plus paragraph, so it survives a replacement that adds chapters. Deleting a book also clears its saved state.
- **Persistence:** after an import the app asks for persistent storage. Firefox shows a prompt; allow it so the browser never clears the books under storage pressure.

## Using it

1. Open <https://kreir42.github.io/tl-reader/> in Firefox. Choose menu → **Add app to Home screen**.
2. Copy `<book>.html` to the phone, tap **Import**, and pick it.
3. To add new chapters, rebuild with `make_reader.py --all --dir "<Work>"`, copy the new file over, and import it again.

To copy text for a dictionary, long-press. Unrevealed English in interleaved mode can't be selected until you reveal it.

## Releasing a change

1. Edit the files. If you add a new file, add it to `SHELL` in `sw.js`.
2. **Bump `VERSION` in `sw.js`.** Browsers only detect an update when `sw.js` changes.
3. Commit and push to `main`. GitHub Pages serves the new version within about 10 minutes.
4. On the phone, open the app. An **Update ready** bar appears; tap **Reload**. Books and reading positions are not affected.
