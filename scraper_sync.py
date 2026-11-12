import asyncio, json, os, re
from datetime import datetime
from playwright.async_api import async_playwright

BRANDS = [
    {"id": "pierrecardin", "name": "Pierre Cardin", "prefix": "PC", "url": "https://www.pierrecardin.com.tr/erkek-takim-elbise/"},
    {"id": "babaterzi",    "name": "Baba Terzi",    "prefix": "BT", "url": "https://www.babaterzi.com/takim-elbise"},
    {"id": "damattween",   "name": "Damat Tween",   "prefix": "DT", "url": "https://www.damattween.com/erkek-takim-elbise-modelleri/"},
    {"id": "dsdamat",      "name": "D'S Damat",     "prefix": "DS", "url": "https://www.dsdamat.com/erkek-takim-elbise-modelleri/"},
    {"id": "sabriozel",    "name": "Sabri Özel",    "prefix": "SO", "url": "https://www.sabriozel.com.tr/takim-elbise-42"}
]

def parse_tl_price(raw_text):
    nums = re.findall(r"[\d\.]+,\d{2}|\d+\.\d{3}", raw_text or "")
    if not nums:
        return 4999.00, 9999.00
    cleaned = [float(n.replace(".", "").replace(",", ".")) for n in nums]
    return min(cleaned), max(cleaned) if len(cleaned) > 1 else min(cleaned) * 1.5

async def sync_catalog():
    prev_db = {}
    if os.path.exists("suits_500_tl.json"):
        try:
            with open("suits_500_tl.json", "r", encoding="utf-8") as f:
                prev_db = json.load(f)
        except Exception:
            prev_db = {}

    updated_db = {"last_sync": datetime.now().strftime("%Y-%m-%d 00:00:00")}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for b in BRANDS:
            known_urls = {item.get("url"): item for item in prev_db.get(b["id"], []) if isinstance(item, dict) and "url" in item}
            try:
                await page.goto(b["url"], wait_until="domcontentloaded", timeout=60000)
                for _ in range(12):
                    await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                    await asyncio.sleep(1.2)

                scraped = await page.evaluate("""() => {
                    const cards = document.querySelectorAll('[class*="product"], [class*="urun"], .product-item, .product-layout');
                    const out = [];
                    const seen = new Set();
                    cards.forEach((c) => {
                        const t = c.querySelector('a[title], h2, h3, .product-name, .name, .prd-name');
                        const p = c.querySelector('[class*="price"], [class*="fiyat"], .price-new');
                        const a = c.querySelector('a[href]');
                        const imgs = [...c.querySelectorAll('img')]
                            .map(i => i.dataset.src || i.currentSrc || i.src)
                            .filter(u => u && u.startsWith('http') && !u.includes('logo') && !u.includes('icon'));
                        if (t && p && imgs.length && a && !seen.has(a.href)) {
                            seen.add(a.href);
                            out.push({
                                titleTR: (t.innerText || t.getAttribute('title') || '').trim(),
                                price_raw: p.innerText.trim(),
                                url: a.href,
                                images: [...new Set(imgs)]
                            });
                        }
                    });
                    return out;
                }""")

                merged = []
                for idx, item in enumerate(scraped[:100]):
                    final_tl, orig_tl = parse_tl_price(item["price_raw"])
                    is_new = bool(known_urls) and (item["url"] not in known_urls)
                    merged.append({
                        "id": f"{b['id']}_{idx + 1}",
                        "rank": idx + 1,
                        "brandId": b["id"],
                        "brandName": b["name"],
                        "code": f"{b['prefix']}-{101 + idx}",
                        "officialSku": f"{b['prefix']}-{101 + idx}",
                        "titleTR": item["titleTR"],
                        "titleFA": "کت و شلوار اورجینال بروزرسانی‌شده از سایت رسمی",
                        "priceTL": final_tl,
                        "origTL": orig_tl,
                        "discountPct": max(10, round(((orig_tl - final_tl) / max(orig_tl, 1)) * 100)),
                        "fit": "Kruvaze" if "kruvaze" in item["titleTR"].lower() else ("Yelekli" if "yelek" in item["titleTR"].lower() else "Slim Fit"),
                        "color": "Siyah" if "siyah" in item["titleTR"].lower() else ("Lacivert" if "lacivert" in item["titleTR"].lower() else "Gri"),
                        "colorFA": "رنگ اصلی کاتالوگ",
                        "fabric": "کالکشن رسمی برند",
                        "url": item["url"],
                        "images": item["images"],
                        "sizes": ["46", "48", "50", "52", "54", "56"],
                        "isNewArrival": is_new
                    })
                if merged:
                    updated_db[b["id"]] = merged
                else:
                    updated_db[b["id"]] = prev_db.get(b["id"], [])
            except Exception as e:
                print(f"Error scraping {b['name']}: {e}")
                updated_db[b["id"]] = prev_db.get(b["id"], [])

        await browser.close()

    with open("suits_500_tl.json", "w", encoding="utf-8") as f:
        json.dump(updated_db, f, ensure_ascii=False, indent=2)

asyncio.run(sync_catalog())
