import { chromium } from "playwright-core";
const CHROME = String.raw`C:\Program Files\Google\Chrome\Application\chrome.exe`;
const WEB = "https://preflight-web-584136898465.us-central1.run.app";
const browser = await chromium.launch({ executablePath: CHROME });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
const fails = [];
page.on("console", (m) => { if (m.type() === "error") fails.push(m.text().slice(0, 120)); });

const email = `live-${Date.now()}@preflight.test`;
await page.goto(`${WEB}/signin`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2500);
await page.click("text=Create one").catch(() => {});
await page.waitForTimeout(400);
await page.fill("#email", email);
await page.fill("#password", "Preflight!2026");
await page.click('button[type="submit"]');
await page.waitForTimeout(9000);
console.log("1 signed up ->", page.url());

await page.waitForTimeout(2500);
console.log("2 empty state:", (await page.$("h1")) ? (await page.textContent("h1")).trim() : "(none)");
await page.screenshot({ path: "/tmp/live-empty.png", fullPage: true });

await page.goto(`${WEB}/projects/new`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(3500);
await page.fill("#title", "Landing QA pass");
await page.fill("#runtime", "12");
await page.click('button[type="submit"]');
await page.waitForTimeout(8000);
console.log("3 after create ->", page.url());

const id = page.url().split("/projects/")[1]?.split("/")[0];
if (id && id !== "new") {
  for (const step of ["master", "destinations", "preflight", "plan", "packages", "passport"]) {
    await page.goto(`${WEB}/projects/${id}/${step}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(3500);
    const h = await page.$("h2, h1");
    console.log(`   ${step}: ${h ? (await h.textContent()).trim().slice(0, 46) : "(no heading)"}`);
  }
  await page.goto(`${WEB}/projects/${id}/destinations`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);
  const names = await page.$$eval("h3", (h) => h.map((x) => x.textContent.trim()));
  console.log("4 destinations from API:", names.join(" | ") || "(none)");
  await page.screenshot({ path: "/tmp/live-destinations.png", fullPage: true });
}
if (fails.length) console.log("console errors:", [...new Set(fails)].slice(0, 4));
await browser.close();
