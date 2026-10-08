import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

TOTAL_PER_CLASS = 10000

OUTPUT_DIR = Path("data/training_data")
OUTPUT_FILE = OUTPUT_DIR / "sensor_training.csv"

random.seed(42)

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

# ============================================================
# HELPER
# ============================================================

def random_value(mean, std, minimum, maximum):
    """
    Sinh giá trị theo phân phối Gaussian
    và giới hạn trong khoảng hợp lý.
    """
    value = random.gauss(mean, std)
    return round(max(minimum, min(maximum, value)), 2)


def generate_sensor_record(label, sensor_id, zone, timestamp):
    """
    Tạo một record sensor cho 1 trong 3 class:
        0 = NORMAL
        1 = FIRE_RISK
        2 = FIRE

    Có vùng chồng lấn giữa các class để dữ liệu
    không quá dễ cho Machine Learning.
    """

    # ========================================================
    # NORMAL
    # ========================================================

    if label == 0:

        temperature = random_value(
            mean=29,
            std=5,
            minimum=22,
            maximum=42
        )

        humidity = random_value(
            mean=65,
            std=9,
            minimum=40,
            maximum=85
        )

        smoke_ppm = random_value(
            mean=80,
            std=45,
            minimum=20,
            maximum=180
        )

        lpg_gas_ppm = random_value(
            mean=140,
            std=80,
            minimum=40,
            maximum=300
        )

        co_gas_ppm = random_value(
            mean=18,
            std=9,
            minimum=3,
            maximum=50
        )

    # ========================================================
    # FIRE RISK
    # ========================================================

    elif label == 1:

        temperature = random_value(
            mean=42,
            std=8,
            minimum=28,
            maximum=65
        )

        humidity = random_value(
            mean=52,
            std=10,
            minimum=30,
            maximum=75
        )

        smoke_ppm = random_value(
            mean=250,
            std=120,
            minimum=50,
            maximum=550
        )

        lpg_gas_ppm = random_value(
            mean=650,
            std=350,
            minimum=100,
            maximum=1600
        )

        co_gas_ppm = random_value(
            mean=90,
            std=40,
            minimum=25,
            maximum=210
        )

    # ========================================================
    # FIRE
    # ========================================================

    else:

        temperature = random_value(
            mean=62,
            std=11,
            minimum=38,
            maximum=90
        )

        humidity = random_value(
            mean=40,
            std=10,
            minimum=20,
            maximum=65
        )

        smoke_ppm = random_value(
            mean=520,
            std=180,
            minimum=200,
            maximum=900
        )

        lpg_gas_ppm = random_value(
            mean=800,
            std=300,
            minimum=300,
            maximum=1400
        )

        co_gas_ppm = random_value(
            mean=170,
            std=50,
            minimum=70,
            maximum=300
        )

    return [
        sensor_id,
        zone,
        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        temperature,
        humidity,
        smoke_ppm,
        lpg_gas_ppm,
        co_gas_ppm,
        label
    ]


# ============================================================
# CREATE DATASET
# ============================================================

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

rows = []

start_time = datetime(2026, 10, 1, 8, 0, 0)

print("Generating training data...")

for label in [0, 1, 2]:

    if label == 0:
        label_name = "NORMAL"
    elif label == 1:
        label_name = "FIRE_RISK"
    else:
        label_name = "FIRE"

    print(f"Generating {TOTAL_PER_CLASS} records: {label_name}")

    for i in range(TOTAL_PER_CLASS):

        sensor_number = random.randint(1, 50)

        sensor_id = f"SENSOR_{sensor_number:03d}"

        zone = random.choice(zones)

        timestamp = start_time + timedelta(
            seconds=random.randint(0, 30 * 24 * 60 * 60)
        )

        row = generate_sensor_record(
            label,
            sensor_id,
            zone,
            timestamp
        )

        rows.append(row)


# ============================================================
# SHUFFLE
# ============================================================

random.shuffle(rows)


# ============================================================
# WRITE CSV
# ============================================================

header = [
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

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:

    writer = csv.writer(f)

    writer.writerow(header)

    writer.writerows(rows)


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 60)
print("TRAINING DATA GENERATED SUCCESSFULLY")
print("=" * 60)

print(f"Output file : {OUTPUT_FILE}")
print(f"Total rows  : {len(rows)}")
print()

print("Class distribution:")

print(f"NORMAL    (0): {TOTAL_PER_CLASS}")
print(f"FIRE_RISK (1): {TOTAL_PER_CLASS}")
print(f"FIRE      (2): {TOTAL_PER_CLASS}")

print()
print("Total:", TOTAL_PER_CLASS * 3)
print("=" * 60)
