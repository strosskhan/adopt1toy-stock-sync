import os
import csv
import requests

SHOP = os.getenv("SHOPIFY_SHOP")
TOKEN = os.getenv("SHOPIFY_TOKEN")
TAG = os.getenv("PRODUCT_TAG", "Manuel")

CSV_URL = "https://store.dreamlove.es/dyndata/exportaciones/csvzip/catalog_1_52_125_2_dd65d46c9efc3d9364272c55399d5b56_csv_plain.csv"

HEADERS = {
    "X-Shopify-Access-Token": TOKEN,
    "Content-Type": "application/json"
}

print("🟢 SERVICE STOCK MANUEL ACTIF")
print("🚀 LANCEMENT SYNCHRO")


def fetch_dreamlove_stock():
    print("🔄 Téléchargement du stock Dreamlove...")
    r = requests.get(CSV_URL, timeout=90)
    r.encoding = "utf-8"

    lines = r.text.splitlines()
    reader = csv.DictReader(lines, delimiter=";")

    stock_map = {}

    for row in reader:
        sku = row.get("sku")
        qty = row.get("available_stock")

        if sku and qty:
            try:
                stock_map[sku.strip()] = int(float(qty))
            except:
                pass

    print(f"✅ {len(stock_map)} SKU chargés depuis Dreamlove")
    return stock_map


def fetch_manual_products():
    print("🔍 Récupération des produits avec le TAG :", TAG)
    products = []
    url = f"https://{SHOP}/admin/api/2024-07/products.json?limit=250&tag={TAG}"

    while url:
        r = requests.get(url, headers=HEADERS)
        data = r.json()
        products.extend(data.get("products", []))
        url = r.links.get("next", {}).get("url")

    print(f"✅ {len(products)} produits détectés dans Shopify")
    return products


def update_stock(inventory_item_id, new_stock):
    r = requests.get(
        f"https://{SHOP}/admin/api/2024-07/locations.json",
        headers=HEADERS
    )

    location_id = r.json()["locations"][0]["id"]

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
        print("❌ ERREUR MAJ STOCK :", r.text)


def sync():
    dreamlove_stock = fetch_dreamlove_stock()
    products = fetch_manual_products()

    match_count = 0

    for product in products:
        for variant in product["variants"]:
            sku = variant.get("sku")

            if sku in dreamlove_stock:
                new_stock = dreamlove_stock[sku]
                inventory_item_id = variant["inventory_item_id"]

                print(f"🔁 {sku} → {new_stock}")
                update_stock(inventory_item_id, new_stock)
                match_count += 1

    print(f"✅ {match_count} variantes synchronisées")


try:
    sync()
    print("✅ SYNCHRONISATION TERMINÉE")
except Exception as e:
    print("❌ ERREUR GLOBALE :", str(e))
