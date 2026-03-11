import puppeteer from 'puppeteer';
import { readdirSync, mkdirSync } from 'fs';
import { join } from 'path';

const url = process.argv[2] || 'http://localhost:1001';
const label = process.argv[3] || '';
const screenshotDir = join(import.meta.dirname, 'temporary screenshots');

// Ensure directory exists
mkdirSync(screenshotDir, { recursive: true });

// Auto-increment: find highest existing screenshot number
const existing = readdirSync(screenshotDir).filter(f => f.startsWith('screenshot-') && f.endsWith('.png'));
let maxN = 0;
for (const f of existing) {
  const match = f.match(/^screenshot-(\d+)/);
  if (match) maxN = Math.max(maxN, parseInt(match[1]));
}
const n = maxN + 1;
const filename = label ? `screenshot-${n}-${label}.png` : `screenshot-${n}.png`;
const filepath = join(screenshotDir, filename);

const browser = await puppeteer.launch({
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
});

const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });
await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });

// Wait a bit for any Alpine.js / async rendering
await new Promise(r => setTimeout(r, 1500));

await page.screenshot({ path: filepath, fullPage: true });
await browser.close();

console.log(`Screenshot saved: ${filepath}`);
