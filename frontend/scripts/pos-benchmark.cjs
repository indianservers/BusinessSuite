const { expect } = require("playwright/test");

const families = ["Coffee", "Tea", "Pasta", "Rice", "Crackers", "Juice", "Sparkling Water", "Yogurt",
  "Spices", "Flour", "Soap", "Shampoo", "Toothpaste", "Tissues", "Batteries", "Detergent"];
const brands = ["Hilltop", "Meadow", "Riverbend", "Orchard", "Cornerstone", "Evergreen"];
const size = 4800;
const samples = 30;
const barcode = id => String(8901000000000 + id);

function benchmarkCatalog() {
  const items = Array.from({length: size}, (_, index) => {
    const id = index + 1;
    const family = families[index % families.length];
    const brand = brands[Math.floor(index / families.length) % brands.length];
    const variant = Math.floor(index / (families.length * brands.length)) + 1;
    return {
      id, item_name: `${brand} ${family} ${variant} · ${[100, 200, 350, 500, 750][variant % 5]} pack`,
      sku: `POS-${id}`, barcode: barcode(id), category: {name: family}, product_type: "product",
      sales_rate: 29 + (id * 13 % 599) + 0.95, gst_rate: [0, 5, 12, 18, 28][id % 5],
      current_quantity: 250 + id % 130, reorder_level: 15, track_inventory: true, currency: "INR", active: true,
    };
  });
  return {items, total: items.length};
}

async function timeAction(page, operation, text) {
  return page.evaluate(({operation, text}) => new Promise((resolve, reject) => {
    const search = document.querySelector('input[aria-label="Search or scan items"]');
    const catalog = document.querySelector(".pos-catalog-results");
    const button = label => [...document.querySelectorAll("button")].find(node => node.textContent.trim() === label);
    const matches = {
      search: () => catalog.querySelector("article")?.textContent.includes(text),
      scan: () => document.querySelector(".pos-cart-line"),
      checkout: () => [...document.querySelectorAll('[role="dialog"] h2')].some(node => node.textContent === "Cash sale saved"),
      shift: () => [...document.querySelectorAll('[role="dialog"]')].some(node => node.textContent.includes("Cash collected")),
    };
    const actions = {
      search: () => {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(search, text);
        search.dispatchEvent(new Event("input", {bubbles: true}));
      },
      scan: () => search.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true, cancelable: true})),
      checkout: () => button("Complete Sale").click(),
      shift: () => button("Local shift report").click(),
    };
    if (matches[operation]()) { reject(new Error("Benchmark end marker was already present: " + operation)); return; }
    let start;
    const deadline = setTimeout(() => { observer.disconnect(); reject(new Error("Timed out: " + operation)); }, 5000);
    const observer = new MutationObserver(() => {
      if (!matches[operation]()) return;
      observer.disconnect();
      clearTimeout(deadline);
      // The second animation frame follows a browser rendering opportunity.
      requestAnimationFrame(() => requestAnimationFrame(() => resolve(performance.now() - start)));
    });
    observer.observe(document.body, {subtree: true, childList: true, characterData: true, attributes: true});
    requestAnimationFrame(() => { start = performance.now(); actions[operation](); });
  }), {operation, text});
}

async function benchmarkPOS(page, controls) {
  const search = page.getByRole("textbox", {name: "Search or scan items"});
  const button = name => page.getByRole("button", {name, exact: true});
  const summary = {};
  const collect = async (mode, count, warmup = 0) => {
    const times = {scan: [], search: [], checkout: [], shift: []};
    const measure = async (operation, text) => {
      if (mode === "syncing") await expect.poll(controls.isUploading).toBe(true);
      return timeAction(page, operation, text);
    };
    for (let i = 0; i < count + warmup; i++) {
      const term = i % 2 ? "Meadow Tea" : "Hilltop Coffee";
      const searchTime = await measure("search", term);
      await search.fill(barcode(4600 + i));
      const scanTime = await measure("scan");
      await page.keyboard.press("F7");
      await expect(button("Complete Sale")).toBeEnabled();
      const checkoutTime = await measure("checkout");
      await button("New Sale").click();
      const shiftTime = await measure("shift");
      await page.keyboard.press("Escape");
      if (i < warmup) continue;
      times.search.push(searchTime);
      times.scan.push(scanTime);
      times.checkout.push(checkoutTime);
      times.shift.push(shiftTime);
    }
    const quantile = (values, q) => Math.round([...values].sort((a, b) => a - b)[Math.ceil(q * values.length) - 1] * 10) / 10;
    summary[mode] = {samples: count, ms: Object.fromEntries(Object.entries(times).map(([key, values]) =>
      [key, {p50: quantile(values, .5), p95: quantile(values, .95), max: quantile(values, 1)}]))};
    console.log(mode, JSON.stringify(summary[mode]));
  };

  await collect("online", samples, 5);
  await controls.setOffline(true);
  await collect("offline", samples, 5);
  controls.setUploadDelay(900);
  await controls.setOffline(false);
  await expect.poll(controls.isUploading).toBe(true);
  await collect("syncing", samples, 3);
  console.log(JSON.stringify({products: size, ...summary}, null, 2));
}

module.exports = { benchmarkCatalog, benchmarkPOS };
