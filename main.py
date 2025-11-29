import os
import csv
import requests
import sys

SHOP = os.getenv("SHOPIFY_SHOP")
TOKEN = os.getenv("SHOPIFY_TOKEN")
CSV_URL = os.getenv("DREAMLOVE_CSV_URL")
TAG = os.getenv("PRODUCT_TAG", "Manuel")

HEADERS = {
    "X-Shopify-Access-Token": TOKEN,
    "Content-Type": "application/json"
}

def fetch_dreamlove_stock():
    print("📥 Téléchargement du stock Dreamlove...")

    r = requests.get(CSV_URL, timeout=30)
    r.raise_for_status()

    r.encoding = "utf-8"
    reader = csv.DictReader(r.text.splitlines())

    stock_map = {}

    for row in reader:
        sku = row.get("sku") or row.get("SKU")
        qty = row.get("stock") or row.get("quantity") or row.get("qty")

        if sku and qty:
            try:
                stock_map[sku.strip()] = int(float(qty))
            except:
                print("⚠️ Stock invalide:", sku, qty)

    print(f"✅ {len(stock_map)} SKU trouvés")
    return stock_map


def fetch_manual_products():
    print(f"🔍 Produits avec le tag : {TAG}")

    products = []
    url = f"https://{SHOP}/admin/api/2024-07/products.json?limit=250&tag={TAG}"

    while url:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()

        data = r.json()
        products.extend(data.get("products", []))
        url = r.links.get("next", {}).get("url")

    print(f"✅ {len(products)} produits trouvés")
    return products


def update_stock(inventory_item_id, new_stock):
    r = requests.get(
        f"https://{SHOP}/admin/api/2024-07/locations.json",
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

    location_id = r.json()["locations"][0]["id"]

    payload = {
        "location_id": location_id,
        "inventory_item_id": inventory_item_id,
        "available": new_stock
    }

    r = requests.post(
        f"https://{SHOP}/admin/api/2024-07/inventory_levels/set.json",
        headers=HEADERS,
        json=payload,
        timeout=30
    )

    if r.status_code == 200:
        print(f"✅ Stock mis à jour → {new_stock}")
    else:
        print("❌ Erreur Shopify :", r.text)


def sync():
    dreamlove_stock = fetch_dreamlove_stock()
    products = fetch_manual_products()

    total = 0

    for product in products:
        for variant in product["variants"]:
            sku = variant.get("sku")

            if not sku:
                continue

            if sku in dreamlove_stock:
                new_stock = dreamlove_stock[sku]
                inventory_item_id = variant["inventory_item_id"]

                print(f"🔁 {sku} → {new_stock}")
                update_stock(inventory_item_id, new_stock)
                total += 1

    print(f"✅ {total} variantes mises à jour")


# ============================
# LANCEMENT CRON UNIQUE
# ============================

print("🟢 SERVICE STOCK MANUEL ACTIF")
print("🚀 LANCEMENT SYNCHRO")

try:
    sync()
    print("✅ SYNCHRO TERMINÉE AVEC SUCCÈS")
    sys.exit(0)
except Exception as e:
    print("❌ ERREUR FATALE :", str(e))
    sys.exit(1)
