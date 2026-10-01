/* Shared by the page and the service worker, so it attaches to `self`. */
self.BookDB = (() => {
  const NAME = "tl-reader", STORE = "books";
  let dbp = null;

  function open() {
    if (!dbp) {
      dbp = new Promise((resolve, reject) => {
        const req = indexedDB.open(NAME, 1);
        req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id" });
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => { dbp = null; reject(req.error); };
      });
    }
    return dbp;
  }

  async function run(mode, fn) {
    const db = await open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const req = fn(tx.objectStore(STORE));
      tx.oncomplete = () => resolve(req && req.result);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  }

  return {
    get: (id) => run("readonly", (s) => s.get(id)),
    all: () => run("readonly", (s) => s.getAll()),
    put: (book) => run("readwrite", (s) => s.put(book)),
    remove: (id) => run("readwrite", (s) => s.delete(id)),
  };
})();
