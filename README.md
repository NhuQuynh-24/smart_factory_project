# Smart Factory – Real-Time Fire & Explosion Risk Monitoring

Hệ thống prototype giám sát và cảnh báo sớm nguy cơ cháy nổ trong nhà máy, sử dụng dữ liệu cảm biến được mô phỏng bằng Python. Dữ liệu được tiếp nhận qua Apache Kafka, xử lý bằng Spark Structured Streaming, phân loại trạng thái bằng mô hình Machine Learning và hiển thị trên dashboard; các trạng thái nguy cơ được gửi cảnh báo qua Telegram.

> **Phạm vi:** Đây là prototype học tập và trình diễn được kiểm thử trên dữ liệu mô phỏng. Dự án chưa kết nối cảm biến vật lý tại nhà máy và không thay thế hệ thống phát hiện, báo cháy được chứng nhận.

## 1. Mục tiêu

- Mô phỏng dữ liệu cảm biến môi trường tại các khu vực trong nhà máy.
- Xây dựng luồng xử lý dữ liệu streaming bằng Kafka và Spark Structured Streaming.
- Huấn luyện, so sánh các mô hình Machine Learning để phân loại trạng thái cảm biến.
- Lưu dữ liệu lịch sử và kết quả dự đoán.
- Hiển thị tình trạng nhà máy trên dashboard và gửi cảnh báo Telegram khi phát hiện nguy cơ.

Hệ thống phân loại dữ liệu thành ba trạng thái:

| Label | Trạng thái | Diễn giải trong mô phỏng |
|---:|---|---|
| `0` | `NORMAL` | Điều kiện bình thường |
| `1` | `FIRE_RISK` | Có dấu hiệu nguy cơ cháy |
| `2` | `FIRE` | Điều kiện mô phỏng cháy |

## 2. Kiến trúc hệ thống

```text
Python Sensor Simulator
        │ JSON records
        ▼
Apache Kafka (topic: sensor-raw)
        ▼
Spark Structured Streaming
  ├─ Parse JSON
  ├─ Validate / clean data
  └─ Process in 30-second microbatches
        ▼
Trained Machine Learning Model (Spark ML)
        │
        ├──────────────► HDFS: historical sensor data
        │                and trained model
        ▼
Predictions
  ├─► MariaDB: predictions and class probabilities
  │       └─► API ─► Next.js Dashboard (deployed on Vercel)
  └─► Telegram Bot: FIRE_RISK / FIRE alerts
```

Luồng huấn luyện mô hình được thực hiện trước luồng dự đoán streaming:

```text
Python-generated labeled training data
        ▼
Train and evaluate 12 candidate models
(Random Forest, Decision Tree, Multiclass Logistic Regression)
        ▼
Compare evaluation metrics
        ▼
Select RF3: Random Forest, 150 trees, max depth 10
        ▼
Save trained model to HDFS
        ▼
Load model for streaming predictions
```

## 3. Dữ liệu đầu vào

### Dữ liệu mô phỏng

- **50 sensor** được phân bố trên **10 khu vực** của nhà máy.
- Mỗi record chứa thông tin nhận diện sensor, khu vực, thời gian và 5 giá trị cảm biến.
- Tổng tốc độ sinh dữ liệu mô phỏng khoảng **100 records/second**.
- Dữ liệu được gửi dưới dạng JSON tới Kafka topic `sensor-raw`.
- Kafka được cấu hình 3 partitions; cấu hình mô phỏng sử dụng một broker và replication factor 1.

Các trường dữ liệu:

| Field | Ý nghĩa |
|---|---|
| `sensor_id` | Mã cảm biến |
| `zone` | Khu vực trong nhà máy |
| `timestamp` | Thời điểm ghi nhận |
| `temperature` | Nhiệt độ (°C) |
| `humidity` | Độ ẩm (%) |
| `smoke_ppm` | Nồng độ khói |
| `lpg_gas_ppm` | Nồng độ khí LPG |
| `co_gas_ppm` | Nồng độ khí CO |

Ví dụ message:

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

Dữ liệu streaming không chứa `label`. Nhãn chỉ có trong dữ liệu huấn luyện; mô hình đã huấn luyện sẽ dự đoán trạng thái của record mới.

## 4. Machine Learning

### Bài toán

Đây là bài toán **học có giám sát – phân loại đa lớp (3-class classification)** trên dữ liệu dạng bảng. Mô hình sử dụng 5 đặc trưng:

```text
temperature
humidity
smoke_ppm
lpg_gas_ppm
co_gas_ppm
```

### Dữ liệu huấn luyện

- 30.000 records được sinh tổng hợp bằng Python.
- 10.000 records cho mỗi lớp: `NORMAL`, `FIRE_RISK`, `FIRE`.
- Các giá trị được tạo theo phân phối mô phỏng; một phần vùng giá trị giữa các lớp có chồng lấn.
- Đây không phải dữ liệu đo đạc thực tế từ nhà máy.

### Các mô hình được so sánh

Dự án đánh giá 12 cấu hình mô hình:

| Thuật toán | Số cấu hình |
|---|---:|
| Random Forest | 4 |
| Decision Tree | 4 |
| Multiclass Logistic Regression | 4 |
| **Tổng** | **12** |

Mô hình được lựa chọn là **RF3 – Random Forest**, với `150 trees` và `max depth = 10`, dựa trên việc so sánh các chỉ số đánh giá.

### Kết quả đánh giá

| Tập đánh giá | Kết quả |
|---|---:|
| Test set của RF3 (5.968 records) | Accuracy / Precision / Recall / F1-score: **98.01%** |
| 9.000 records từ luồng mô phỏng | 8.976 dự đoán đúng (**99.73%**) |

Trong kết quả trên luồng mô phỏng, 24 record `FIRE_RISK` bị phân loại thành `FIRE`.

> Các chỉ số được tính trên dữ liệu tổng hợp/mô phỏng, không thể được xem là độ chính xác đã xác nhận trong môi trường nhà máy thực tế.

### Feature importance của RF3

| Feature | Mức độ quan trọng |
|---|---:|
| CO | 0.3981 |
| Temperature | 0.2099 |
| Smoke | 0.1881 |
| LPG | 0.1841 |
| Humidity | 0.0197 |

Trong mô hình RF3, CO có mức độ quan trọng cao nhất; độ ẩm thấp nhất theo kết quả feature importance.

## 5. Xử lý dữ liệu streaming

Spark Structured Streaming thực hiện các bước chính:

1. Đọc JSON records từ Kafka topic `sensor-raw`.
2. Parse, kiểm tra và làm sạch dữ liệu.
3. Xử lý theo microbatch 30 giây.
4. Áp dụng mô hình RF3 đã huấn luyện để dự đoán trạng thái.
5. Ghi dữ liệu lịch sử/kết quả dự đoán tới các thành phần lưu trữ tương ứng.
6. Kích hoạt logic cảnh báo Telegram đối với `FIRE_RISK` và `FIRE`.

## 6. Lưu trữ và hiển thị

### HDFS

HDFS được sử dụng để lưu dữ liệu cảm biến lịch sử và mô hình Machine Learning đã huấn luyện.

### MariaDB

MariaDB lưu kết quả dự đoán và phân phối xác suất theo lớp. Các trường kết quả bao gồm trạng thái dự đoán và xác suất của `NORMAL`, `FIRE_RISK`, `FIRE`.

### Dashboard

Dashboard được xây dựng bằng **Next.js** và triển khai trên **Vercel**. Dashboard lấy dữ liệu thông qua API và MariaDB, tự cập nhật mỗi **5 giây**.

Các khu vực chức năng chính:

- Overview
- Sensor Monitoring
- Factory Areas
- Alerts
- History
- AI

## 7. Telegram Alert

Hệ thống gửi thông báo khi mô hình dự đoán:

| Prediction | Hành động |
|---|---|
| `NORMAL` | Không gửi cảnh báo |
| `FIRE_RISK` | Gửi cảnh báo nguy cơ cháy |
| `FIRE` | Gửi cảnh báo cháy khẩn cấp |

Thông báo được tổng hợp theo dữ liệu của batch; nếu có cả `FIRE_RISK` và `FIRE`, mức `FIRE` được ưu tiên trong tiêu đề cảnh báo.

## 8. Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| Sinh dữ liệu cảm biến | Python |
| Message streaming | Apache Kafka |
| Xử lý streaming | Apache Spark Structured Streaming |
| Machine Learning | Spark ML: Random Forest, Decision Tree, Multiclass Logistic Regression |
| Lưu dữ liệu lịch sử / model | HDFS |
| Lưu dự đoán | MariaDB |
| Dashboard | Next.js, Vercel |
| API | API kết nối dashboard với dữ liệu dự đoán |
| Cảnh báo | Telegram Bot API |

## 9. Trạng thái triển khai

Prototype đã hoàn thành các phần chính:

- Mô phỏng dữ liệu sensor.
- Tiếp nhận dữ liệu qua Kafka.
- Xử lý dữ liệu bằng Spark Structured Streaming.
- Huấn luyện và so sánh mô hình Machine Learning.
- Lưu dữ liệu lịch sử, mô hình và kết quả dự đoán.
- Tích hợp dashboard và Telegram alert.
- Kiểm thử tích hợp và đánh giá trên dữ liệu mô phỏng.

**Giới hạn hiện tại:** Hệ thống chưa sử dụng sensor vật lý và chưa được xác thực bằng dữ liệu vận hành thực tế. Bước phát triển tiếp theo là kết nối thiết bị IoT, thu thập dữ liệu hiện trường và đánh giá lại mô hình trong điều kiện thực tế.

## 10. License / mục đích sử dụng

Dự án được thực hiện cho mục đích học tập, nghiên cứu và trình diễn trong môn Big Data. Các giá trị cảm biến và kịch bản cảnh báo là dữ liệu mô phỏng, không phải ngưỡng an toàn được chứng nhận.
