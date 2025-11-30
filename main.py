import os
import csv
import requests

# =========================
# VARIABLES RAILWAY
# =========================

SHOP = os.getenv("SHOPIFY_SHOP")
TOKEN = os.getenv("SHOPIFY_TOKEN")
TAG = os.getenv("PRODUCT_TAG")
CSV_URL = os.getenv("DREAMLOVE_CSV_URL")

HEADERS = {
    "X-Shopify-Access-Token": TOKEN,
    "Content-Type": "application/json"
}

print("🟢 SERVICE STOCK ADOPT1TOY ACTIF")
print("🚀 LANCEMENT SYNCHRO")

# =========================
# 1. LECTURE CSV DREAMLOVE (sku + available_stock)
# =========================

def fetch_dreamlove_stock():
    print("📥 Téléchargement du stock Dreamlove...")
    r = requests.get(CSV_URL, timeout=120)
    r.encoding = "utf-8"

    reader = csv.DictReader(r.text.splitlines(), delimiter=";")
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

# =========================
# 2. PRODUITS SHOPIFY AVEC TAG MANUEL
# =========================

def fetch_shopify_products():
    print("🔍 Récupération des produits Shopify avec le tag :", TAG)
    products = []
    url = f"https://{SHOP}/admin/api/2024-07/products.json?limit=250&tag={TAG}"

    while url:
        r = requests.get(url, headers=HEADERS)
        data = r.json()
        products.extend(data.get("products", []))
        url = r.links.get("next", {}).get("url")

    print(f"✅ {len(products)} produits Shopify récupérés")
    return products

# =========================
# 3. ID DE L’EMPLACEMENT ADOPT1TOY
# =========================

def fetch_adopt1toy_location_id():
    r = requests.get(f"https://{SHOP}/admin/api/2024-07/locations.json", headers=HEADERS)
    locations = r.json()["locations"]

    for loc in locations:
        if loc["name"].lower() == "adopt1toy":
            print(f"✅ Emplacement Adopt1toy trouvé (ID {loc['id']})")
            return loc["id"]

    print("❌ ERREUR : emplacement Adopt1toy introuvable")
    return None

# =========================
# 4. CONNEXION + MISE À JOUR STOCK
# =========================

def update_stock(location_id, inventory_item_id, new_stock):
    requests.post(
        f"https://{SHOP}/admin/api/2024-07/inventory_levels/connect.json",
        headers=HEADERS,
        json={
            "location_id": location_id,
            "inventory_item_id": inventory_item_id
        }
    )

    r = requests.post(
        f"https://{SHOP}/admin/api/2024-07/inventory_levels/set.json",
        headers=HEADERS,
        json={
            "location_id": location_id,
            "inventory_item_id": inventory_item_id,
            "available": new_stock
        }
    )

    return r.status_code == 200

# =========================
# 5. SYNCHRONISATION
# =========================

def sync():
    dreamlove_stock = fetch_dreamlove_stock()
    products = fetch_shopify_products()
    location_id = fetch_adopt1toy_location_id()

    if not location_id:
        return

    updated = 0

    print("🔁 Comparaison et mise à jour...")

    for product in products:
        for variant in product["variants"]:
            sku = variant.get("sku")
            inv_id = variant.get("inventory_item_id")
            shopify_qty = variant.get("inventory_quantity")

            if sku in dreamlove_stock:
                dl_qty = dreamlove_stock[sku]

                if shopify_qty != dl_qty:
                    ok = update_stock(location_id, inv_id, dl_qty)

                    if ok:
                        print(f"✅ {sku} : {shopify_qty} → {dl_qty}")
                        updated += 1
                    else:
                        print(f"❌ ERREUR MAJ {sku}")

    print(f"✅ SYNCHRO TERMINÉE — {updated} variantes mises à jour")

# =========================
# 6. LANCEMENT CRON (ONE SHOT)
# =========================

if __name__ == "__main__":
    try:
        sync()
    except Exception as e:
        print("❌ ERREUR GLOBALE :", str(e))
