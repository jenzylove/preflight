import { chromium } from "playwright-core";
const CHROME = String.raw`C:\Program Files\Google\Chrome\Application\chrome.exe`;
const WEB = "https://preflight-web-584136898465.us-central1.run.app";
const browser = await chromium.launch({ executablePath: CHROME });
for (const [name, width, scale] of [["desktop", 1440, 1], ["mobile", 390, 1]]) {
  const ctx = await browser.newContext({
    viewport: { width, height: 900 }, deviceScaleFactor: scale,
    isMobile: width < 600, hasTouch: width < 600,
  });
  const page = await ctx.newPage();
  await page.goto(WEB, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += window.innerHeight) {
      window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `/tmp/final/landing-${name}.jpg`, fullPage: true, type: "jpeg", quality: 72 });
  await ctx.close();
}
await browser.close();
console.log("done");
