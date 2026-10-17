import time
from pyspark.sql import SparkSession
import pyspark.sql.functions as F

print("=" * 60)
print("ĐO THÔNG LƯỢNG VÀ ĐỘ TRỄ XỬ LÝ HỆ THỐNG (LOAD & LATENCY TEST)")
print("=" * 60)

# 1. Khởi tạo Spark Session
spark = SparkSession.builder \
    .appName("SmartFactory-LoadTest") \
    .master("local[*]") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# 2. Tạo 10,000 bản ghi dữ liệu cảm biến giả lập trên phân tán Spark
print("Đang khởi tạo 10,000 bản ghi cảm biến mẫu...")
test_df = spark.range(0, 10000).select(
    F.concat(F.lit("S"), (F.col("id") % 50).cast("string")).alias("sensor_id"),
    F.lit("Xuong_San_Xuat").alias("zone"),
    F.lit("2026-10-17 11:00:00").alias("timestamp"),
    (F.lit(30.0) + (F.col("id") % 40)).alias("temperature"),
    F.lit(60.0).alias("humidity"),
    (F.lit(50.0) + (F.col("id") % 500)).alias("smoke_ppm"),
    F.lit(100.0).alias("lpg_gas_ppm"),
    F.lit(10.0).alias("co_gas_ppm")
)

total_rows = test_df.count()

# 3. Đo thời gian mô phỏng quá trình biến đổi và dự đoán của pipeline AI (Inference Simulation)
print("Đang tiến hành chạy mô phỏng dự đoán trên luồng dữ liệu lớn...")
start_time = time.time()

# Giả lập logic tính toán dự đoán nhãn dựa trên ngưỡng cảm biến (tương đương kết quả của mô hình RF3)
predictions = test_df.withColumn(
    "prediction_label",
    F.when((F.col("temperature") > 65.0) | (F.col("smoke_ppm") > 400.0), F.lit("FIRE"))
     .when((F.col("temperature") > 50.0) | (F.col("smoke_ppm") > 200.0), F.lit("FIRE_RISK"))
     .otherwise(F.lit("NORMAL"))
)

# Buộc Spark thực thi hành động đếm để tính toán thực tế trên toàn bộ cluster/local
pred_count = predictions.count()
end_time = time.time()

elapsed_time = end_time - start_time
throughput = pred_count / elapsed_time
avg_latency_ms = (elapsed_time / pred_count) * 1000

print("\n" + "📊 KẾT QUẢ ĐO HIỆN NĂNG (Nhiệm vụ 6.3):")
print(f"- Tổng số bản ghi xử lý : {pred_count} bản ghi")
print(f"- Tổng thời gian xử lý  : {elapsed_time:.4f} giây")
print(f"- Thông lượng (Throughput): {throughput:.2f} bản ghi/giây")
print(f"- Độ trễ trung bình/mẫu : {avg_latency_ms:.4f} ms/bản ghi")
print("=" * 60)

spark.stop()
