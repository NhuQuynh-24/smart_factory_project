import os
import sys
from pyspark.sql import SparkSession

# Thêm đường dẫn để import telegram_alert
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from telegram_alert import send_telegram_alert

print("=" * 60)
print("KIỂM THỬ TÍCH HỢP HỆ THỐNG (INTEGRATION TEST)")
print("=" * 60)

# 1. Khởi tạo Spark Session tích hợp Kafka và MariaDB JDBC
spark = (
    SparkSession.builder.appName("SmartFactory-IntegrationTest")
    .config(
        "spark.jars.packages",
        "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5,"
        "org.mariadb.jdbc:mariadb-java-client:3.3.3",
    )
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

# 2. Kiểm tra đọc dữ liệu từ Kafka (Test 1 micro-batch hoặc đọc offset)
try:
  kafka_df = (
      spark.read.format("kafka")
      .option("kafka.bootstrap.servers", "localhost:9092")
      .option("subscribe", "sensor-raw")
      .option("startingOffsets", "earliest")
      .load()
  )
  print(
      "✅ [OK] Kết nối Apache Kafka thành công! Số phân vùng dữ liệu đọc được:"
      f" {kafka_df.count() if not kafka_df.isEmpty() else 'Topic trống hoặc sẵn sàng'}"
  )
except Exception as e:
  print(f"❌ [LỖI] Không kết nối được Kafka: {e}")

# 3. Kiểm thử bắn tin nhắn Telegram khẩn cấp
print("Đang gửi tin nhắn test tích hợp tới Telegram...")
test_fire_row = [{
    "sensor_id": "TEST_SENSOR_999",
    "zone": "Phong_May",
    "timestamp": "2026-10-17 11:00:00",
    "temperature": 85.5,
    "smoke_ppm": 750.0,
    "lpg_gas_ppm": 900.0,
    "co_gas_ppm": 200.0,
    "prediction": 2.0,
    "prediction_label": "FIRE",
    "probability_fire": 0.99,
    "probability_risk": 0.01,
}]

success = send_telegram_alert(test_fire_row, [])
if success:
  print("✅ [OK] Gửi cảnh báo Telegram tích hợp thành công!")
else:
  print("❌ [LỖI] Gửi Telegram thất bại, kiểm tra lại Token và Chat ID.")

spark.stop()
print("=" * 60)
print("HOÀN TẤT KIỂM THỬ TÍCH HỢP")
print("=" * 60)
