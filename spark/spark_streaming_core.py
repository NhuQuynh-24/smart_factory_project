from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    DoubleType
)

spark = (
    SparkSession.builder
    .appName("SmartFactoryStreamingTest")
    .getOrCreate()
)

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

# Đọc dữ liệu realtime từ Kafka
raw_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "localhost:9092")
    .option("subscribe", "sensor-raw")
    .option("startingOffsets", "latest")
    .load()
)

# Chuyển value từ binary sang String
json_df = raw_df.selectExpr("CAST(value AS STRING) AS json_data")

# Parse JSON
sensor_df = (
    json_df
    .select(from_json(col("json_data"), schema).alias("data"))
    .select("data.*")
)

# In ra console để test
query = (
    sensor_df.writeStream
    .format("parquet")
    .outputMode("append")
    .option(
        "path",
        "hdfs://localhost:9000/data/sensor_test_01"
    )
    .option(
        "checkpointLocation",
        "hdfs://localhost:9000/data/checkpoints/sensor_test_01"
    )
    .start()
)

query.awaitTermination()
