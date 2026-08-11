import app.database as db
products = db.get_all_products()
categories = [p['category'] for p in products]
print("All categories:", set(categories))
for p in products:
    if "MLOps" in p['category']:
        print(f"ID: {p['id']}, Title: {p['title']}, Category: '{p['category']}'")
