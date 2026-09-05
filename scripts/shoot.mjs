/**
 * Capture the landing page as it actually renders.
 *
 * Full-page captures at desktop and mobile, plus above-the-fold crops, driven
 * through the system Chrome. Reading the markup tells you what should happen;
 * only a screenshot tells you whether the cinema image is sitting on top of
 * the headline.
 *
 *   node scripts/shoot.mjs [baseUrl] [outDir]
 */

import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const BASE = process.argv[2] ?? "http://localhost:3100";
const OUT = process.argv[3] ?? "/tmp/shots";

const CHROME =
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "laptop", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844, mobile: true },
];

const PAGES = [
  { path: "/", name: "landing", full: true },
  { path: "/signin", name: "signin", full: false },
  { path: "/projects", name: "projects", full: false },
];

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: CHROME });

for (const viewport of VIEWPORTS) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: 2,
    isMobile: Boolean(viewport.mobile),
    hasTouch: Boolean(viewport.mobile),
  });
  const page = await context.newPage();

  const problems = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(message.text());
  });
  page.on("pageerror", (error) => problems.push(String(error)));

  for (const spec of PAGES) {
    await page.goto(`${BASE}${spec.path}`, { waitUntil: "networkidle" });
    // Let fonts settle and any parallax reach its resting position.
    await page.waitForTimeout(700);

    await page.screenshot({
      path: join(OUT, `${spec.name}-${viewport.name}-fold.png`),
      fullPage: false,
    });

    if (spec.full) {
      // Scroll through once so lazy work and scroll listeners have run before
      // the full-page capture stitches the page together.
      await page.evaluate(async () => {
        const step = window.innerHeight;
        for (let y = 0; y < document.body.scrollHeight; y += step) {
          window.scrollTo(0, y);
          await new Promise((r) => setTimeout(r, 120));
        }
        window.scrollTo(0, 0);
      });
      await page.waitForTimeout(400);
      await page.screenshot({
        path: join(OUT, `${spec.name}-${viewport.name}-full.png`),
        fullPage: true,
      });
    }

    if (spec.name === "landing") {
      // The one failure mode that matters most: does anything overlap the
      // headline, the paragraph or the call to action?
      const overlap = await page.evaluate(() => {
        const heading = document.querySelector("#hero-heading");
        if (!heading) return { error: "no #hero-heading" };
        const box = heading.getBoundingClientRect();
        const cta = [...document.querySelectorAll("a")].find((a) =>
          a.textContent?.trim().startsWith("Prepare your film"),
        );
        const ctaBox = cta?.getBoundingClientRect() ?? null;

        // What is actually painted at the centre of the headline and the CTA?
        const at = (b) =>
          b
            ? document
                .elementFromPoint(b.left + b.width / 2, b.top + b.height / 2)
                ?.tagName ?? null
            : null;

        return {
          headingTop: Math.round(box.top),
          headingWidth: Math.round(box.width),
          headingVisible: box.width > 0 && box.height > 0,
          topmostAtHeading: at(box),
          topmostAtCta: at(ctaBox),
          ctaVisible: Boolean(ctaBox && ctaBox.width > 0),
          docWidth: document.documentElement.scrollWidth,
          viewportWidth: window.innerWidth,
          horizontalOverflow:
            document.documentElement.scrollWidth > window.innerWidth + 1,
        };
      });
      console.log(`${viewport.name}:`, JSON.stringify(overlap));
    }
  }

  if (problems.length) {
    console.log(`${viewport.name} console errors:`, problems.slice(0, 5));
  }
  await context.close();
}

await browser.close();
console.log("shots written to", OUT);
