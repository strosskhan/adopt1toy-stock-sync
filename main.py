import os
import csv
import requests

SHOP = os.getenv("SHOPIFY_SHOP")
TOKEN = os.getenv("SHOPIFY_TOKEN")
CSV_URL = os.getenv("DREAMLOVE_CSV_URL")
TAG = os.getenv("PRODUCT_TAG", "Manuel")

HEADERS = {
    "X-Shopify-Access-Token": TOKEN,
    "Content-Type": "application/json"
}

def fetch_dreamlove_stock():
    print("🔄 Téléchargement du stock Dreamlove...")
    r = requests.get(CSV_URL, timeout=30)
    r.encoding = "utf-8"

    reader = csv.DictReader(r.text.splitlines())
    stock_map = {}

    for row in reader:
        sku = (row.get("sku") or row.get("SKU") or "").strip()
        qty = row.get("stock") or row.get("quantity") or row.get("qty")

        if sku and qty:
            try:
                stock_map[sku] = int(float(qty))
            except:
                pass

    print(f"✅ {len(stock_map)} SKU chargés depuis Dreamlove")
    return stock_map


def fetch_manual_products():
    print(f"🔍 Récupération des produits avec tag : {TAG}")
    products = []
    url = f"https://{SHOP}/admin/api/2024-07/products.json?limit=250&tag={TAG}"

    while url:
        r = requests.get(url, headers=HEADERS)
        data = r.json()
        products.extend(data.get("products", []))
        url = r.links.get("next", {}).get("url")

    print(f"✅ {len(products)} produits manuels trouvés")
    return products


def update_stock(inventory_item_id, new_stock):
    r = requests.get(f"https://{SHOP}/admin/api/2024-07/locations.json", headers=HEADERS)
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
        print("❌ Erreur stock :", r.text)


def main():
    print("🟢 SERVICE STOCK MANUEL ACTIF")
    print("🚀 LANCEMENT SYNCHRO")

    dreamlove_stock = fetch_dreamlove_stock()
    products = fetch_manual_products()

    updated = 0

    for product in products:
        for variant in product["variants"]:
            sku = variant.get("sku")

            if sku in dreamlove_stock:
                new_stock = dreamlove_stock[sku]
                inventory_item_id = variant["inventory_item_id"]

                print(f"🔁 {sku} → {new_stock}")
                update_stock(inventory_item_id, new_stock)
                updated += 1

    print(f"✅ SYNCHRO TERMINÉE — {updated} stocks mis à jour")
    print("🛑 FIN DU JOB — EXIT OK")


if __name__ == "__main__":
    main()
