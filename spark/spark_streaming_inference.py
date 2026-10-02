from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType, DoubleType
from pyspark.ml import PipelineModel

# =========================
# 1. Spark
# =========================

spark = (
    SparkSession.builder
    .appName("SmartFactoryStreamingInference")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

# =========================
# 2. Schema dữ liệu Kafka
# =========================

schema = StructType([
    StructField("sensor_id", StringType(), True),
    StructField("zone", StringType(), True),
    StructField("timestamp", StringType(), True),
    StructField("temperature", DoubleType(), True),
    StructField("humidity", DoubleType(), True),
    StructField("smoke_ppm", DoubleType(), True),
    StructField("lpg_gas_ppm", DoubleType(), True),
    StructField("co_gas_ppm", DoubleType(), True)
])

# =========================
# 3. Đọc Kafka
# =========================

raw_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "localhost:9092")
    .option("subscribe", "sensor-raw")
    .option("startingOffsets", "latest")
    .load()
)

# =========================
# 4. Parse JSON
# =========================

json_df = raw_df.selectExpr(
    "CAST(value AS STRING) AS json_data"
)

sensor_df = (
    json_df
    .select(
        from_json(col("json_data"), schema).alias("data")
    )
    .select("data.*")
)

# =========================
# 5. Load Random Forest model
# =========================

model_path = (
    "hdfs://localhost:9000/"
    "smart_factory_project/models/pipeline_rf_model"
)

model = PipelineModel.load(model_path)

print("Random Forest model loaded.")

# =========================
# 6. Dự đoán realtime
# =========================

predictions = model.transform(sensor_df)

result_df = predictions.select(
    "sensor_id",
    "zone",
    "timestamp",
    "temperature",
    "humidity",
    "smoke_ppm",
    "lpg_gas_ppm",
    "co_gas_ppm",
    "prediction",
    "probability"
)

# =========================
# 7. Hiển thị kết quả
# =========================

query = (
    result_df.writeStream
    .format("console")
    .outputMode("append")
    .option("truncate", "false")
    .option("numRows", 10)
    .option(
        "checkpointLocation",
        "hdfs://localhost:9000/data/checkpoints/sensor_inference_01"
    )
    .start()
)

query.awaitTermination()
