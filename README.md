# Smart Factory – Real-Time Fire Monitoring & Alerting

Hệ thống mô phỏng **giám sát và cảnh báo nguy cơ cháy trong nhà máy theo thời gian thực** bằng dữ liệu sensor được sinh tự động.

Project sử dụng Apache Kafka để tiếp nhận dữ liệu, Spark Structured Streaming để xử lý dữ liệu streaming theo chu kỳ 30 giây, Spark ML với Random Forest để phân loại trạng thái sensor, HDFS để lưu dữ liệu lịch sử, MariaDB để lưu kết quả dự đoán, Streamlit để hiển thị dashboard và Telegram Bot để gửi cảnh báo đến điện thoại.

> **Lưu ý:** Đây là prototype phục vụ mục đích học tập và trình diễn, sử dụng dữ liệu sensor mô phỏng. Hệ thống không phải hệ thống an toàn cháy nổ được chứng nhận cho nhà máy thực tế.

---

## 1. Mục tiêu

Hệ thống phân loại tình trạng của sensor thành 3 trạng thái:

| Label | Trạng thái | Ý nghĩa |
|---:|---|---|
| `0` | `NORMAL` | Điều kiện hoạt động bình thường |
| `1` | `FIRE_RISK` | Có dấu hiệu bất thường / nguy cơ cháy |
| `2` | `FIRE` | Phát hiện điều kiện mô phỏng cháy |

Các kịch bản mô phỏng tập trung vào **nhiệt độ, khói, LPG và CO**.

---

## 2. Kiến trúc tổng thể

```text
                         SMART FACTORY
                              │
                    Python Sensor Simulator
                              │
                              │ JSON
                              ▼
                    ┌────────────────────┐
                    │       Kafka        │
                    │ topic: sensor-raw  │
                    └─────────┬──────────┘
                              │
                              ▼
               ┌─────────────────────────────┐
               │ Spark Structured Streaming   │
               │                             │
               │ - Parse JSON                │
               │ - Validate / Clean          │
               │ - Process every 30 seconds  │
               └────────────┬────────────────┘
                            │
                 ┌──────────┴──────────┐
                 │                     │
                 ▼                     ▼
        ┌────────────────┐    ┌──────────────────┐
        │      HDFS      │    │     Spark ML     │
        │ Historical data│    │   Random Forest  │
        └────────────────┘    └────────┬─────────┘
                                       │
                                       ▼
                             ┌──────────────────┐
                             │    Prediction    │
                             │                  │
                             │ 0 NORMAL         │
                             │ 1 FIRE_RISK      │
                             │ 2 FIRE           │
                             └────────┬─────────┘
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                         ▼                         ▼
                  ┌──────────────┐          ┌──────────────┐
                  │   MariaDB    │          │ Telegram Bot │
                  │ Predictions  │          │   Alerts     │
                  └──────┬───────┘          └──────┬───────┘
                         │                         │
                         ▼                         ▼
                  ┌──────────────┐                 📱
                  │   Streamlit  │
                  │  Dashboard   │
                  └──────────────┘
```

---

## 3. Luồng dữ liệu

### 3.1. Giai đoạn huấn luyện

```text
generate_training_data.py
        ↓
sensor_training.csv
        ↓
HDFS
        ↓
train_random_forest.py
        ↓
Spark ML – Random Forest
        ↓
RF1 / RF2 / RF3 / RF4
        ↓
Model lưu trên HDFS
```

`generate_training_data.py` tạo dữ liệu sensor có nhãn:

```text
0 = NORMAL
1 = FIRE_RISK
2 = FIRE
```

Mỗi record training gồm các thông tin sensor và `label`.

### 3.2. Giai đoạn chạy thời gian thực

```text
Python Sensor
      ↓
    Kafka
      ↓
Spark Structured Streaming
      ↓
Spark ML Random Forest
      ↓
Prediction
      ↓
 ┌────┴──────┐
 ↓           ↓
MariaDB   Telegram
 ↓
Streamlit
```

Dữ liệu streaming **không có `label`**. Model được huấn luyện trước sẽ dự đoán trạng thái cho từng record mới.

---

## 4. Mô phỏng sensor

Hệ thống mô phỏng **50 sensor** được phân bố trên 10 khu vực trong nhà máy.

### Các khu vực

```text
1. Kho_Nguyen_Lieu
2. Kho_Vat_Lieu
3. Kho_Hoa_Chat
4. Kho_Thanh_Pham
5. Kho_Linh_Kien
6. Xuong_San_Xuat
7. Khu_Dong_Goi
8. Khu_Kiem_Tra
9. Phong_May
10. Khu_Bao_Tri
```

### Mô hình incident

Producer mô phỏng một **incident**:

```text
1 incident
    ↓
1 khu vực
    ↓
3–5 sensor trong khu vực bị ảnh hưởng
    ↓
FIRE_RISK
    ↓
có thể leo thang thành FIRE
    ↓
incident kết thúc
    ↓
trạng thái trở lại NORMAL
```

---

## 5. Dữ liệu sensor

Ví dụ một message Kafka:

```json
{
  "sensor_id": "SENSOR_013",
  "zone": "Kho_Hoa_Chat",
  "timestamp": "2026-10-02 14:30:00",
  "temperature": 48.2,
  "humidity": 50.0,
  "smoke_ppm": 260.0,
  "lpg_gas_ppm": 820.0,
  "co_gas_ppm": 95.0
}
```

### Ý nghĩa các trường

| Trường | Ý nghĩa |
|---|---|
| `sensor_id` | Mã sensor |
| `zone` | Khu vực đặt sensor |
| `timestamp` | Thời gian ghi nhận |
| `temperature` | Nhiệt độ (°C) |
| `humidity` | Độ ẩm (%) |
| `smoke_ppm` | Nồng độ khói |
| `lpg_gas_ppm` | Nồng độ LPG |
| `co_gas_ppm` | Nồng độ CO |

`label` **không được gửi trong dữ liệu streaming**.

---

## 6. Spark ML – Random Forest

Project sử dụng **Spark ML** với thuật toán Random Forest cho bài toán phân loại 3 lớp.

### Features

Model sử dụng:

```text
temperature
humidity
smoke_ppm
lpg_gas_ppm
co_gas_ppm
```

### 4 cấu hình thử nghiệm

| Model | numTrees | maxDepth |
|---|---:|---:|
| RF1 | 50 | 5 |
| RF2 | 100 | 8 |
| RF3 | 150 | 10 |
| RF4 | 200 | 12 |

Các model được đánh giá bằng Accuracy, F1, Weighted Precision, Weighted Recall, Confusion Matrix và training time.

Model sau khi train được lưu trên HDFS.

---

## 7. HDFS

### Training data

```text
/smart_factory_training/sensor_training.csv
```

### Historical streaming data

```text
/data/sensor_historical
```

### Random Forest models

```text
/smart_factory_project/models/
├── random_forest_3class_rf1
├── random_forest_3class_rf2
├── random_forest_3class_rf3
└── random_forest_3class_rf4
```

---

## 8. MariaDB

Database:

```text
smart_factory
```

Table:

```text
sensor_predictions
```

Các trường chính:

```text
id
sensor_id
zone
timestamp
temperature
humidity
smoke_ppm
lpg_gas_ppm
co_gas_ppm
prediction
prediction_label
probability_normal
probability_risk
probability_fire
created_at
```

Mapping:

```text
prediction = 0 → NORMAL
prediction = 1 → FIRE_RISK
prediction = 2 → FIRE
```

---

## 9. Telegram Alert

### Logic cảnh báo

```text
NORMAL
→ Không gửi cảnh báo

FIRE_RISK
→ Cảnh báo nguy cơ cháy

FIRE
→ Cảnh báo cháy khẩn cấp
```

Nếu trong cùng một batch 30 giây có cả `FIRE_RISK` và `FIRE`:

```text
→ Chỉ gửi 1 tin Telegram
→ FIRE được ưu tiên
→ Vẫn liệt kê FIRE_RISK
```

Nếu có nhiều sensor trong cùng khu vực, các sensor được gom vào nội dung cảnh báo.

Ví dụ:

```text
🔥 CẢNH BÁO CHÁY KHẨN CẤP 🔥

Sensor: SENSOR_013
Khu vực: Kho_Hoa_Chat
Thời gian: 2026-10-02 14:30:00

Nhiệt độ: 75.50 °C
Khói: 650.00 ppm
LPG: 850.00 ppm
CO: 180.00 ppm
Trạng thái: FIRE
Xác suất FIRE: 97.35%
```

---

## 10. Streamlit Dashboard

Dashboard đọc dữ liệu từ MariaDB và tự refresh mỗi 30 giây.

### Nội dung chính

```text
📊 Tổng quan
├── Tổng record
├── NORMAL
├── FIRE_RISK
└── FIRE

📡 Dữ liệu sensor mới nhất

🚨 Cảnh báo gần nhất

🏭 Các khu vực đang có cảnh báo
```

---

## 11. Cấu trúc thư mục

```text
smart_factory_project/
│
├── data/
│   ├── sensor_schema.json
│   └── training_data/
│       └── sensor_training.csv
│
├── simulator/
│   └── sensor_producer.py
│
├── spark/
│   ├── train_random_forest.py
│   ├── spark_streaming_core.py
│   ├── spark_streaming_mariadb.py
│   └── telegram_alert.py
│
├── jars/
│   └── mariadb-java-client-3.5.6.jar
│
├── generate_training_data.py
├── dashboard.py
├── .gitignore
└── venv/
```

---

## 12. Môi trường chính

```text
Python
Apache Kafka
Apache Spark
Spark Structured Streaming
Spark ML
HDFS
YARN
MariaDB
Streamlit
Telegram Bot
```

Kafka connector:

```text
org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5
```

MariaDB JDBC:

```text
mariadb-java-client-3.5.6.jar
```

---

## 13. Biến môi trường

Không lưu secret trực tiếp trong source code.

```bash
export MARIADB_PASSWORD='your_mariadb_password'
export TELEGRAM_BOT_TOKEN='your_telegram_bot_token'
export TELEGRAM_CHAT_ID='your_telegram_chat_id'
```

Không commit các giá trị thật lên GitHub.

---

## 14. Cách chạy

### 1. Hadoop

```bash
start-dfs.sh
start-yarn.sh
```

### 2. MariaDB

```bash
sudo systemctl start mariadb
```

### 3. Kafka

```bash
cd ~/kafka_2.12-2.8.1

bin/zookeeper-server-start.sh -daemon config/zookeeper.properties
bin/kafka-server-start.sh -daemon config/server.properties
```

### 4. Sensor

```bash
cd ~/smart_factory_project
source venv/bin/activate

python3 simulator/sensor_producer.py
```

### 5. Spark → HDFS

```bash
cd ~/smart_factory_project

$SPARK_HOME/bin/spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5 spark/spark_streaming_core.py
```

### 6. Spark ML → MariaDB → Telegram

```bash
cd ~/smart_factory_project
source venv/bin/activate

export MARIADB_PASSWORD='your_mariadb_password'
export TELEGRAM_BOT_TOKEN='your_telegram_bot_token'
export TELEGRAM_CHAT_ID='your_telegram_chat_id'

$SPARK_HOME/bin/spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5 --jars ~/smart_factory_project/jars/mariadb-java-client-3.5.6.jar spark/spark_streaming_mariadb.py
```

### 7. Streamlit

```bash
cd ~/smart_factory_project
source venv/bin/activate

export MARIADB_PASSWORD='your_mariadb_password'

streamlit run dashboard.py
```

Mở:

```text
http://localhost:8501
```

---

## 15. Kiểm tra nhanh

### Kafka

```bash
cd ~/kafka_2.12-2.8.1

bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic sensor-raw
```

### HDFS

```bash
hdfs dfs -ls /data/sensor_historical
```

### Model

```bash
hdfs dfs -ls /smart_factory_project/models
```

### MariaDB

```sql
USE smart_factory;

SELECT
    prediction,
    prediction_label,
    COUNT(*) AS total
FROM sensor_predictions
GROUP BY prediction, prediction_label
ORDER BY prediction;
```

---

## 16. Thành viên

| Thành viên | Vai trò |
|---|---|
| Nong Nhu Quynh | Team Leader & Spark Streaming Lead |
| Trieu Tien Dat | Data Engineer & Kafka Lead |
| Ha Thi Xuan | Machine Learning Engineer |
| Le Tran Thu Thao | Storage & Big Data Infrastructure Engineer |
| To Thi Ngoc Anh | Dashboard, Alert & QA Lead |

---

## 17. Trạng thái project

```text
Python Sensor                ✅
Apache Kafka                 ✅
Spark Structured Streaming  ✅
HDFS                         ✅
Spark ML / Random Forest     ✅
MariaDB                      ✅
Telegram Bot                 ✅
Streamlit                    ✅
GitHub                       ✅
```

---

## 18. Lưu ý

Project sử dụng dữ liệu được sinh tổng hợp bằng Python. Các ngưỡng và khoảng giá trị sensor phục vụ mô phỏng và trình diễn, không phải ngưỡng an toàn được chứng nhận cho nhà máy thực tế.

---

## License

Project được thực hiện cho mục đích học tập và trình diễn trong môn Big Data.
