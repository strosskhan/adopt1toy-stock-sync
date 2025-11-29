import os
import sys
import time
import requests
import pandas as pd
from io import StringIO

# =========================
# VARIABLES RAILWAY
# =========================

SHOP_DOMAIN = os.getenv("SHOP_DOMAIN")  # ex: adopt1toy.myshopify.com
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_LOCATION_ID = os.getenv("SHOPIFY_LOCATION_ID")

DREAMLOVE_STOCK_URL = os.getenv("DREAMLOVE_STOCK_URL")
DREAMLOVE_SKU_COLUMN = os.getenv("DREAMLOVE_SKU_COLUMN", "sku")
DREAMLOVE_STOCK_COLUMN = os.getenv("DREAMLOVE_STOCK_COLUMN", "stock")

MANUAL_TAG = os.getenv("MANUAL_TAG", "Manuel")
API_VERSION = "2024-01"

# =========================
# SÉCURITÉ CONFIG
# =========================

if not all([
    SHOP_DOMAIN,
    SHOPIFY_ACCESS_TOKEN,
    SHOPIFY_LOCATION_ID,
    DREAMLOVE_STOCK_URL,
]):
    print("❌ Variables Railway manquantes")
    sys.exit(1)

# =========================
# SESSION SHOPIFY
# =========================

session = requests.Session()
session.headers.update({
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
})

# =========================
# LECTURE STOCK DREAMLOVE
# =========================

def fetch_dreamlove_stock():
    print("🔄 Téléchargement du CSV Dreamlove...")

    r = requests.get(DREAMLOVE_STOCK_URL, timeout=60)
    r.raise_for_status()

    try:
        df = pd.read_csv(StringIO(r.text), dtype=str)
    except:
        df = pd.read_csv(StringIO(r.text), dtype=str, sep=";")

    if DREAMLOVE_SKU_COLUMN not in df.columns:
        print("❌ Colonne SKU introuvable :", df.columns)
        sys.exit(1)

    if DREAMLOVE_STOCK_COLUMN not in df.columns:
        print("❌ Colonne STOCK introuvable :", df.columns)
        sys.exit(1)

    df[DREAMLOVE_SKU_COLUMN] = df[DREAMLOVE_SKU_COLUMN].astype(str).str.strip()
    df[DREAMLOVE_STOCK_COLUMN] = df[DREAMLOVE_STOCK_COLUMN].astype(str).str.strip()

    stock_map = {}

    for _, row in df.iterrows():
        sku = row[DREAMLOVE_SKU_COLUMN]

        try:
            qty = int(float(row[DREAMLOVE_STOCK_COLUMN].replace(",", ".")))
        except:
            qty = 0

        stock_map[sku] = qty

    print(f"✅ {len(stock_map)} SKU chargés depuis Dreamlove")
    return stock_map

# =========================
# RÉCUPÉRATION PRODUITS TAGUÉS MANUEL
# =========================

def get_manual_products():
    print("🔎 Récupération des produits tagués Manuel...")
    products = []

    url = f"https://{SHOP_DOMAIN}/admin/api/{API_VERSION}/products.json?limit=250"

    while url:
        r = session.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()

        for product in data.get("products", []):
            tags = [t.strip() for t in product.get("tags", "").split(",")]
            if MANUAL_TAG in tags:
                products.append(product)

        link = r.headers.get("Link")
        if link and 'rel="next"' in link:
            url = link.split(";")[0].strip("<>")
        else:
            url = None

    print(f"✅ {len(products)} produits MANUELS trouvés")
    return products

# =========================
# MISE À JOUR DU STOCK
# =========================

def set_stock(inventory_item_id, qty):
    url = f"https://{SHOP_DOMAIN}/admin/api/{API_VERSION}/inventory_levels/set.json"

    payload = {
        "location_id": int(SHOPIFY_LOCATION_ID),
        "inventory_item_id": int(inventory_item_id),
        "available": int(qty),
    }

    r = session.post(url, json=payload, timeout=20)

    if r.status_code >= 400:
        print("⚠️ Erreur MAJ stock :", r.text)

# =========================
# MAIN
# =========================

def main():
    print("=== DÉMARRAGE SYNC STOCK MANUEL DREAMLOVE ===")

    stock_map = fetch_dreamlove_stock()
    products = get_manual_products()

    updated = 0
    skipped = 0

    for product in products:
        for variant in product["variants"]:
            sku = (variant.get("sku") or "").strip()

            if not sku:
                continue

            if sku not in stock_map:
                skipped += 1
                continue

            qty = stock_map[sku]
            inventory_item_id = variant["inventory_item_id"]

            set_stock(inventory_item_id, qty)
            print(f"✅ {sku} → {qty}")

            updated += 1
            time.sleep(0.15)  # anti-blocage API Shopify

    print("✅ SYNC TERMINÉE")
    print(f"🔁 Variantes mises à jour : {updated}")
    print(f"❌ SKU non trouvés : {skipped}")

# =========================

if __name__ == "__main__":
    main()
