import csv
import random
from datetime import datetime, timedelta

OUTPUT_FILE = "data/training_data/sensor_training.csv"
TOTAL_PER_CLASS = 10000

zones = [
    "Kho_Nguyen_Lieu",
    "Kho_Vat_Lieu",
    "Kho_Hoa_Chat",
    "Kho_Thanh_Pham",
    "Kho_Linh_Kien",
    "Xuong_San_Xuat",
    "Khu_Dong_Goi",
    "Khu_Kiem_Tra",
    "Phong_May",
    "Khu_Bao_Tri"
]


def generate_normal():
    return {
        "temperature": round(random.uniform(24, 35), 2),
        "humidity": round(random.uniform(55, 75), 2),
        "smoke_ppm": round(random.uniform(30, 100), 2),
        "lpg_gas_ppm": round(random.uniform(50, 180), 2),
        "co_gas_ppm": round(random.uniform(5, 25), 2),
        "label": 0
    }


def generate_fire_risk():
    # Có 2 kiểu FIRE_RISK:
    # 1. Nhiệt tăng bất thường
    # 2. Rò rỉ gas
    if random.random() < 0.5:
        return {
            "temperature": round(random.uniform(40, 59), 2),
            "humidity": round(random.uniform(40, 55), 2),
            "smoke_ppm": round(random.uniform(120, 400), 2),
            "lpg_gas_ppm": round(random.uniform(150, 700), 2),
            "co_gas_ppm": round(random.uniform(40, 120), 2),
            "label": 1
        }
    else:
        return {
            "temperature": round(random.uniform(30, 39), 2),
            "humidity": round(random.uniform(45, 65), 2),
            "smoke_ppm": round(random.uniform(80, 250), 2),
            "lpg_gas_ppm": round(random.uniform(700, 1600), 2),
            "co_gas_ppm": round(random.uniform(60, 180), 2),
            "label": 1
        }


def generate_fire():
    return {
        "temperature": round(random.uniform(60, 90), 2),
        "humidity": round(random.uniform(25, 45), 2),
        "smoke_ppm": round(random.uniform(500, 900), 2),
        "lpg_gas_ppm": round(random.uniform(500, 1200), 2),
        "co_gas_ppm": round(random.uniform(120, 250), 2),
        "label": 2
    }


random.seed(42)

rows = []
start_time = datetime.now() - timedelta(days=7)

# NORMAL
for i in range(TOTAL_PER_CLASS):
    values = generate_normal()

    rows.append({
        "sensor_id": f"S{random.randint(1, 50):03d}",
        "zone": random.choice(zones),
        "timestamp": (
            start_time + timedelta(seconds=i)
        ).strftime("%Y-%m-%d %H:%M:%S"),
        **values
    })

# FIRE_RISK
for i in range(TOTAL_PER_CLASS):
    values = generate_fire_risk()

    rows.append({
        "sensor_id": f"S{random.randint(1, 50):03d}",
        "zone": random.choice(zones),
        "timestamp": (
            start_time + timedelta(seconds=TOTAL_PER_CLASS + i)
        ).strftime("%Y-%m-%d %H:%M:%S"),
        **values
    })

# FIRE
for i in range(TOTAL_PER_CLASS):
    values = generate_fire()

    rows.append({
        "sensor_id": f"S{random.randint(1, 50):03d}",
        "zone": random.choice(zones),
        "timestamp": (
            start_time + timedelta(seconds=2 * TOTAL_PER_CLASS + i)
        ).strftime("%Y-%m-%d %H:%M:%S"),
        **values
    })


random.shuffle(rows)

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "sensor_id",
            "zone",
            "timestamp",
            "temperature",
            "humidity",
            "smoke_ppm",
            "lpg_gas_ppm",
            "co_gas_ppm",
            "label"
        ]
    )

    writer.writeheader()
    writer.writerows(rows)

print(f"Đã tạo: {OUTPUT_FILE}")
print(f"Tổng số record: {len(rows)}")
print("NORMAL = 0")
print("FIRE_RISK = 1")
print("FIRE = 2")
