import json
import random
import time
from datetime import datetime
from kafka import KafkaProducer

# ============================================================
# Kafka configuration
# ============================================================

KAFKA_SERVER = "localhost:9092"
TOPIC = "sensor-raw"

producer = KafkaProducer(
    bootstrap_servers=KAFKA_SERVER,
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

# ============================================================
# Sensor configuration
# ============================================================

NUM_SENSORS = 50
INTERVAL_SECONDS = 0.5

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
sensors = []

for i in range(NUM_SENSORS):
    sensors.append({
        "sensor_id": f"S{i + 1:03d}",
        "zone": zones[i % len(zones)]
    })

# ============================================================
# Trạng thái hiện tại của từng sensor
# ============================================================

sensor_state = {}

for sensor in sensors:
    sensor_state[sensor["sensor_id"]] = {
        "state": "NORMAL",
        "remaining": 0
    }

# ============================================================
# Sinh giá trị theo trạng thái
# ============================================================

def generate_values(state):

    # --------------------------------------------------------
    # NORMAL
    # --------------------------------------------------------

    if state == "NORMAL":

        return {
            "temperature": round(random.uniform(24, 35), 2),
            "humidity": round(random.uniform(55, 75), 2),
            "smoke_ppm": round(random.uniform(30, 100), 2),
            "lpg_gas_ppm": round(random.uniform(50, 180), 2),
            "co_gas_ppm": round(random.uniform(5, 25), 2)
        }

    # --------------------------------------------------------
    # FIRE_RISK
    # --------------------------------------------------------

    elif state == "FIRE_RISK":

        # Có 2 kiểu nguy cơ:
        # 1. Nhiệt tăng + khói/khí tăng
        # 2. Rò rỉ LPG/CO

        if random.random() < 0.5:

            return {
                "temperature": round(random.uniform(40, 59), 2),
                "humidity": round(random.uniform(40, 55), 2),
                "smoke_ppm": round(random.uniform(120, 400), 2),
                "lpg_gas_ppm": round(random.uniform(150, 700), 2),
                "co_gas_ppm": round(random.uniform(40, 120), 2)
            }

        else:

            return {
                "temperature": round(random.uniform(30, 39), 2),
                "humidity": round(random.uniform(45, 65), 2),
                "smoke_ppm": round(random.uniform(80, 250), 2),
                "lpg_gas_ppm": round(random.uniform(700, 1600), 2),
                "co_gas_ppm": round(random.uniform(60, 180), 2)
            }

    # --------------------------------------------------------
    # FIRE
    # --------------------------------------------------------

    else:

        return {
            "temperature": round(random.uniform(60, 90), 2),
            "humidity": round(random.uniform(25, 45), 2),
            "smoke_ppm": round(random.uniform(500, 900), 2),
            "lpg_gas_ppm": round(random.uniform(500, 1200), 2),
            "co_gas_ppm": round(random.uniform(120, 250), 2)
        }


# ============================================================
# Cập nhật trạng thái sensor
# ============================================================

def update_state(sensor_id):

    info = sensor_state[sensor_id]

    # Sensor đang ở trạng thái bất thường
    if info["remaining"] > 0:

        info["remaining"] -= 1

        if info["remaining"] == 0:
            info["state"] = "NORMAL"

        return info["state"]

    # --------------------------------------------------------
    # Xác suất bắt đầu bất thường
    # --------------------------------------------------------

    if random.random() < 0.002:

        # FIRE_RISK xảy ra nhiều hơn FIRE
        if random.random() < 0.7:
            info["state"] = "FIRE_RISK"
        else:
            info["state"] = "FIRE"

        info["remaining"] = random.randint(8, 16)

    return info["state"]


# ============================================================
# Main
# ============================================================

print("=" * 70)
print("SMART FACTORY SENSOR PRODUCER")
print("=" * 70)
print(f"Number of sensors : {NUM_SENSORS}")
print(f"Rate              : ~{NUM_SENSORS / INTERVAL_SECONDS:.0f} records/sec")
print(f"Kafka topic       : {TOPIC}")
print("=" * 70)

try:

    while True:

        for sensor in sensors:

            sensor_id = sensor["sensor_id"]
            zone = sensor["zone"]

            state = update_state(sensor_id)

            values = generate_values(state)

            record = {
                "sensor_id": sensor_id,
                "zone": zone,
                "timestamp": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "temperature": values["temperature"],
                "humidity": values["humidity"],
                "smoke_ppm": values["smoke_ppm"],
                "lpg_gas_ppm": values["lpg_gas_ppm"],
                "co_gas_ppm": values["co_gas_ppm"]
            }

            producer.send(TOPIC, record)

            # Chỉ in trạng thái bất thường ra màn hình
            if state == "FIRE_RISK":

                print(
                    f"[FIRE_RISK] "
                    f"{sensor_id} | {zone} | "
                    f"T={values['temperature']}°C | "
                    f"Smoke={values['smoke_ppm']} | "
                    f"LPG={values['lpg_gas_ppm']} | "
                    f"CO={values['co_gas_ppm']}"
                )

            elif state == "FIRE":

                print(
                    f"[FIRE] "
                    f"{sensor_id} | {zone} | "
                    f"T={values['temperature']}°C | "
                    f"Smoke={values['smoke_ppm']} | "
                    f"LPG={values['lpg_gas_ppm']} | "
                    f"CO={values['co_gas_ppm']}"
                )

        producer.flush()

        time.sleep(INTERVAL_SECONDS)

except KeyboardInterrupt:

    print("\nĐã dừng sensor producer.")

finally:

    producer.close()
