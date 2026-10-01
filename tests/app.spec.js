import { test, expect } from "@playwright/test";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const SAMPLE = fileURLToPath(new URL("../app/sample/the_spiders_thread.html", import.meta.url));

/* A second, distinct book built from the sample by renaming it. */
async function otherBook(testInfo) {
  const html = (await readFile(SAMPLE, "utf8"))
    .replace('content="the_spiders_thread"', 'content="second_book"')
    .replaceAll("reader:the_spiders_thread:", "reader:second_book:")
    .replace(/<title>[^<]*<\/title>/, "<title>Second Book — 001–003</title>");
  const path = testInfo.outputPath("second_book.html");
  await writeFile(path, html);
  return path;
}

async function openLibrary(page) {
  await page.goto("./");
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null);
}

/* Index of the first paragraph pair whose top is in view. */
const firstVisiblePair = (page) => page.evaluate(() =>
  [...document.querySelectorAll(".pair")].findIndex((p) => p.getBoundingClientRect().top > -5));

async function scrollToPair(page, i) {
  await page.evaluate((i) => document.querySelectorAll(".pair")[i].scrollIntoView(), i);
  await page.waitForTimeout(600); // the reader debounces position saves
}

test.beforeEach(async ({ page }) => {
  page.on("dialog", (d) => d.accept());
});

test("sample book loads from the empty library", async ({ page }) => {
  await openLibrary(page);
  await expect(page.locator("#empty")).toBeVisible();
  await page.click("#sample");
  await expect(page.locator("#books li")).toHaveCount(1);
  await expect(page.locator("#books .title")).toHaveText("The Spider's Thread");
  await expect(page.locator("#books .meta")).toContainText("001–003");
});

test("an imported book opens at a stable URL with selectable text", async ({ page }) => {
  await openLibrary(page);
  await page.setInputFiles("#picker", SAMPLE);
  await expect(page.locator("#toast")).toHaveText("Added The Spider's Thread");

  await page.click("#books a");
  await expect(page).toHaveURL(/\/tl-reader\/book\/the_spiders_thread$/);
  await expect(page.locator(".pair").first()).toBeVisible();
  expect(await page.locator(".jp").first().evaluate((el) => getComputedStyle(el).userSelect)).not.toBe("none");
});

test("reading position and display mode survive leaving the book", async ({ page }) => {
  await openLibrary(page);
  await page.setInputFiles("#picker", SAMPLE);
  await page.click("#books a");

  await page.click('button[data-mode="en"]');
  await scrollToPair(page, 10);
  const before = await firstVisiblePair(page);

  await page.goBack();
  await page.click("#books a");
  await expect(page.locator("body")).toHaveClass(/mode-en/);
  await expect.poll(() => firstVisiblePair(page)).toBe(before);
});

test("re-importing a renamed download replaces the book and keeps the place", async ({ page }, testInfo) => {
  await openLibrary(page);
  await page.setInputFiles("#picker", SAMPLE);
  await page.click("#books a");
  await scrollToPair(page, 10);
  const before = await firstVisiblePair(page);

  // Android names a repeat download "name (1).html".
  await page.goto("./");
  await page.setInputFiles("#picker", {
    name: "the_spiders_thread (1).html", mimeType: "text/html", buffer: await readFile(SAMPLE),
  });
  await expect(page.locator("#toast")).toHaveText("Updated The Spider's Thread");
  await expect(page.locator("#books li")).toHaveCount(1);

  await page.click("#books a");
  await expect.poll(() => firstVisiblePair(page)).toBe(before);
});

test("each book keeps its own state, and deleting one clears only its state", async ({ page }, testInfo) => {
  await openLibrary(page);
  await page.setInputFiles("#picker", [SAMPLE, await otherBook(testInfo)]);
  await expect(page.locator("#books li")).toHaveCount(2);

  await page.locator("#books a", { hasText: "Spider" }).click();
  await page.click('button[data-mode="split"]');
  await page.goBack();
  await page.locator("#books a", { hasText: "Second" }).click();
  await expect(page.locator("body")).toHaveClass(/mode-mix/); // the reader's default, untouched
  await page.click('button[data-mode="jp"]');
  await page.goBack();

  await page.locator("#books li", { hasText: "Second" }).getByRole("button").click();
  await expect(page.locator("#books li")).toHaveCount(1);
  const keys = await page.evaluate(() => Object.keys(localStorage));
  expect(keys.some((k) => k.startsWith("reader:second_book:"))).toBe(false);
  expect(keys).toContain("reader:the_spiders_thread:mode");
});

test("library and books work offline", async ({ page, context }) => {
  await openLibrary(page);
  await page.setInputFiles("#picker", SAMPLE);

  await context.setOffline(true);
  await page.reload();
  await page.click("#books a");
  await expect(page.locator(".pair").first()).toBeVisible();
  await context.setOffline(false);
});

test("a new release shows an update prompt and keeps the library", async ({ page, request }) => {
  await openLibrary(page);
  await page.setInputFiles("#picker", SAMPLE);

  await request.post("/__test/release");
  await page.reload();
  await expect(page.locator("#update")).toBeVisible();
  await page.click("#reload");

  // Tapping Reload navigates, so a poll may land mid-navigation; retry it.
  await expect.poll(() => page.evaluate(() => caches.keys()).catch(() => []))
    .toContainEqual(expect.stringMatching(/-test\d+$/));
  await expect(page.locator("#update")).toBeHidden();
  await expect(page.locator("#books li")).toHaveCount(1);
});

test("a book link opened before the service worker is installed falls back to the library", async ({ page }) => {
  await page.goto("book/the_spiders_thread");
  await expect(page).toHaveURL(/\/tl-reader\/$/);
  await expect(page.locator("h1")).toHaveText("Library");
});
