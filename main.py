import os
import time
import csv
import requests

SHOP = os.getenv("SHOPIFY_SHOP")
TOKEN = os.getenv("SHOPIFY_TOKEN")
CSV_URL = os.getenv("DREAMLOVE_CSV_URL")
TAG = os.getenv("PRODUCT_TAG")
INTERVAL = int(os.getenv("SYNC_INTERVAL", "1800"))

HEADERS = {
    "X-Shopify-Access-Token": TOKEN,
    "Content-Type": "application/json"
}

def fetch_dreamlove_stock():
    print("🔄 Téléchargement du stock Dreamlove...")
    r = requests.get(CSV_URL)
    r.encoding = "utf-8"
    lines = r.text.splitlines()
    reader = csv.DictReader(lines)

    stock_map = {}
    for row in reader:
        sku = row.get("sku") or row.get("SKU")
        qty = row.get("stock") or row.get("quantity") or row.get("qty")
        if sku and qty:
            try:
                stock_map[sku.strip()] = int(float(qty))
            except:
                pass

    print(f"✅ {len(stock_map)} SKU trouvés dans le stock Dreamlove")
    return stock_map


def fetch_manual_products():
    print("🔍 Récupération des produits TAG =", TAG)
    products = []
    url = f"https://{SHOP}/admin/api/2024-07/products.json?limit=250&tag={TAG}"

    while url:
        r = requests.get(url, headers=HEADERS)
        data = r.json()
        products.extend(data.get("products", []))
        url = r.links.get("next", {}).get("url")

    print(f"✅ {len(products)} produits manuels détectés")
    return products


def update_stock(variant_id, inventory_item_id, new_stock):
    # 1. Récupérer location_id
    r = requests.get(f"https://{SHOP}/admin/api/2024-07/locations.json", headers=HEADERS)
    location_id = r.json()["locations"][0]["id"]

    # 2. Mise à jour du stock
    payload = {
        "location_id": location_id,
        "inventory_item_id": inventory_item_id,
        "available": new_stock
    }

    r = requests.post(
        f"https://{SHOP}/admin/api/2024-07/inventory_levels/set.json",
        headers=HEADERS,
        json=payload
    )

    if r.status_code == 200:
        print(f"✅ Stock mis à jour → {new_stock}")
    else:
        print("❌ Erreur mise à jour stock :", r.text)


def sync():
    dreamlove_stock = fetch_dreamlove_stock()
    products = fetch_manual_products()

    for product in products:
        for variant in product["variants"]:
            sku = variant.get("sku")
            if sku in dreamlove_stock:
                new_stock = dreamlove_stock[sku]
                inventory_item_id = variant["inventory_item_id"]
                print(f"🔁 {sku} → {new_stock}")
                update_stock(variant["id"], inventory_item_id, new_stock)


print("🚀 SYNCHRO STOCK MANUELLE DÉMARRÉE")
while True:
    try:
        sync()
    except Exception as e:
        print("❌ ERREUR GLOBALE :", str(e))

    print(f"⏳ Attente {INTERVAL} secondes...\n")
    time.sleep(INTERVAL)
