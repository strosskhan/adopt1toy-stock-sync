import os
import csv
import requests
import time
from tqdm import tqdm
from datetime import datetime

# =========================
# CONFIG
# =========================

SHOP = os.getenv("SHOPIFY_SHOP")
TOKEN = os.getenv("SHOPIFY_TOKEN")
TAG = os.getenv("PRODUCT_TAG", "Manuel")

CSV_URL = "https://store.dreamlove.es/dyndata/exportaciones/csvzip/catalog_1_52_125_2_dd65d46c9efc3d9364272c55399d5b56_csv_plain.csv"

OUTPUT_DIR = "output"
LOG_FILE = os.path.join(OUTPUT_DIR, "sync_log.csv")

HEADERS = {
    "X-Shopify-Access-Token": TOKEN,
    "Content-Type": "application/json"
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("🟢 SERVICE STOCK ADOPT1TOY ACTIF")
print("🚀 LANCEMENT SYNCHRO\n")

# =========================
# 1. RÉCUPÉRATION STOCK DREAMLOVE
# =========================

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

    print(f"✅ {len(stock_map)} SKU chargés depuis Dreamlove\n")
    return stock_map

# =========================
# 2. RÉCUPÉRATION PRODUITS SHOPIFY (TAG MANUEL)
# =========================

def fetch_manual_products():
    print("🔍 Récupération des produits avec le TAG :", TAG)
    products = []

    url = f"https://{SHOP}/admin/api/2024-07/products.json?limit=250&tag={TAG}"

    while url:
        r = requests.get(url, headers=HEADERS)
        data = r.json()
        products.extend(data.get("products", []))
        url = r.links.get("next", {}).get("url")

    print(f"✅ {len(products)} produits détectés dans Shopify\n")
    return products

# =========================
# 3. RÉCUPÉRATION EMPLACEMENT ADOPT1TOY
# =========================

def fetch_adopt1toy_location_id():
    r = requests.get(
        f"https://{SHOP}/admin/api/2024-07/locations.json",
        headers=HEADERS
    )

    locations = r.json()["locations"]

    for loc in locations:
        if loc["name"].lower() == "adopt1toy":
            print(f"✅ Emplacement trouvé : Adopt1toy (ID {loc['id']})\n")
            return loc["id"]

    print("❌ ERREUR : emplacement 'Adopt1toy' introuvable")
    return None

# =========================
# 4. CONNEXION + MISE À JOUR DU STOCK (CORRECTION DÉFINITIVE)
# =========================

def update_stock(location_id, inventory_item_id, new_stock):

    # 1. CONNECTER L'INVENTORY ITEM À L'EMPLACEMENT
    connect_payload = {
        "location_id": location_id,
        "inventory_item_id": inventory_item_id
    }

    requests.post(
        f"https://{SHOP}/admin/api/2024-07/inventory_levels/connect.json",
        headers=HEADERS,
        json=connect_payload
    )

    # 2. METTRE À JOUR LE STOCK
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

    return r.status_code == 200, r.text

# =========================
# 5. SYNCHRONISATION
# =========================

def sync():
    dreamlove_stock = fetch_dreamlove_stock()
    products = fetch_manual_products()
    location_id = fetch_adopt1toy_location_id()

    if not location_id:
        return

    logs = []
    match_count = 0

    print("🔁 Synchronisation en cours...\n")

    for product in tqdm(products, desc="Produits"):
        for variant in product["variants"]:
            sku = variant.get("sku")

            if sku in dreamlove_stock:
                new_stock = dreamlove_stock[sku]
                inventory_item_id = variant["inventory_item_id"]

                success, response = update_stock(location_id, inventory_item_id, new_stock)

                logs.append([
                    sku,
                    inventory_item_id,
                    new_stock,
                    "OK" if success else "ERREUR",
                    response[:200],
                    datetime.now().isoformat()
                ])

                if success:
                    print(f"✅ {sku} → {new_stock} (Adopt1toy)")
                    match_count += 1
                else:
                    print(f"❌ {sku} → ERREUR")

    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "SKU",
            "Inventory Item ID",
            "Stock",
            "Résultat",
            "Message",
            "Date"
        ])
        writer.writerows(logs)

    print(f"\n✅ {match_count} variantes synchronisées")
    print(f"📁 Log enregistré : {LOG_FILE}\n")


