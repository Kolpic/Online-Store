import csv
import random
# Define product templates to generate varied names and categories
product_templates = [
    {"name": "LED Bulb {power}W", "category": "Lighting"},
    {"name": "Garden Chair {type}", "category": "Furniture"},
    {"name": "Electric Drill {power}W", "category": "Tools"},
    {"name": "Ceramic Vase {style}", "category": "Decor"},
    {"name": "Bluetooth Speaker {model}", "category": "Electronics"}
]

image_filenames = [
    "arka-600x400.jpg", "ba-2-600x400.jpg", "dsc_2638-600x400.jpg", 
    "dsc_2731-600x400.jpg", "dsc_2783-600x400.jpg", "dsc_2992-600x400.jpg",
    "dsc_3031-600x400.jpg", "dsc_3898900x600.jpg", "modul.jpg",
    "rrrr.jpg", "fura.jpg", "gggg-g-570c07ed5f.jpg", "huhuhuh.jpg"
]

# Helper function to generate a random product name
def generate_product_name(template):
    placeholders = {
        "{power}": str(random.randint(5, 100)),
        "{type}": random.choice(["Wooden", "Metal", "Plastic"]),
        "{style}": random.choice(["Modern", "Classic", "Abstract"]),
        "{model}": random.choice(["X100", "A500", "ProMax"])
    }
    for placeholder, value in placeholders.items():
        template = template.replace(placeholder, value)
    return template

# Generate dummy products
products = []
for _ in range(100000):
    template = random.choice(product_templates)
    product_name = generate_product_name(template['name'])
    random_image = random.choice(image_filenames)  # Select a random image filename
    product = {
        "name": product_name,
        "price": "{:.2f}".format(random.uniform(5, 150)),
        "quantity": str(random.randint(10, 500)),
        "category": template['category'],
        "image": random_image  # Use the random image filename
    }
    products.append(product)

# Path to save the CSV file
csv_file_path = './large_products.csv'

# Write to CSV in chunks to avoid large memory usage
def write_csv_in_chunks(filepath, data, chunk_size=1000):
    with open(filepath, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()
        for i in range(0, len(data), chunk_size):
            writer.writerows(data[i:i+chunk_size])

# Define the header
fields = ['name', 'price', 'quantity', 'category', 'image']

# Write the CSV file with 100,000 products
write_csv_in_chunks(csv_file_path, products)

csv_file_path