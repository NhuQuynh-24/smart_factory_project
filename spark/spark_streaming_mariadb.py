from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    DoubleType
)
from pyspark.sql.functions import (
    from_json,
    col,
    when,
    udf,
    row_number,
    desc
)
from pyspark.sql.window import Window
from pyspark.ml import PipelineModel
from pyspark.ml.linalg import Vector

from pyspark.sql.types import DoubleType

import os
import sys

sys.path.append(
    os.path.dirname(os.path.abspath(__file__))
)

from telegram_alert import send_telegram_alert


# ============================================================
# Spark
# ============================================================

spark = (
    SparkSession.builder
    .appName("SmartFactory-3Class-Streaming")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")


# ============================================================
# Model
# ============================================================

MODEL_PATH = (
    "hdfs://localhost:9000/"
    "smart_factory_project/models/"
    "random_forest_3class_rf1"
)

print("Loading model...")

model = PipelineModel.load(MODEL_PATH)

print("Model loaded:")
print(MODEL_PATH)


# ============================================================
# MariaDB
# ============================================================

JDBC_URL = (
    "jdbc:mysql://localhost:3306/"
    "smart_factory?permitMysqlScheme=true"
)

JDBC_TABLE = "sensor_predictions"

JDBC_PROPERTIES = {
    "user": "root",
    "password": os.getenv("MARIADB_PASSWORD", ""),
    "driver": "org.mariadb.jdbc.Driver"
}


# ============================================================
# Kafka schema
# ============================================================

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


# ============================================================
# Kafka source
# ============================================================

raw_stream = (
    spark.readStream
    .format("kafka")
    .option(
        "kafka.bootstrap.servers",
        "localhost:9092"
    )
    .option(
        "subscribe",
        "sensor-raw"
    )
    .option(
        "startingOffsets",
        "latest"
    )
    .load()
)


# ============================================================
# Parse JSON
# ============================================================

sensor_stream = (
    raw_stream
    .selectExpr(
        "CAST(value AS STRING) AS json_value"
    )
    .select(
        from_json(
            col("json_value"),
            schema
        ).alias("data")
    )
    .select("data.*")
)


# ============================================================
# Validate
# ============================================================

clean_stream = (
    sensor_stream
    .filter(col("sensor_id").isNotNull())
    .filter(col("zone").isNotNull())
    .filter(col("timestamp").isNotNull())
    .filter(col("temperature").isNotNull())
    .filter(col("humidity").isNotNull())
    .filter(col("smoke_ppm").isNotNull())
    .filter(col("lpg_gas_ppm").isNotNull())
    .filter(col("co_gas_ppm").isNotNull())
)


# ============================================================
# Extract probability
# ============================================================

def extract_probability(index):

    def get_value(vector):

        if vector is None:
            return 0.0

        return float(vector[index])

    return udf(
        get_value,
        DoubleType()
    )


prob_normal = extract_probability(0)
prob_risk = extract_probability(1)
prob_fire = extract_probability(2)


# ============================================================
# Process every 30-second micro-batch
# ============================================================

def write_to_mariadb(batch_df, batch_id):

    print("\n" + "=" * 80)
    print(f"PROCESSING BATCH ID: {batch_id}")
    print("=" * 80)

    if batch_df.rdd.isEmpty():

        print("Batch rỗng.")

        return


    # ========================================================
    # Spark ML prediction
    # ========================================================

    predictions = model.transform(batch_df)


    # ========================================================
    # 3-class prediction
    # ========================================================

    predictions = (
        predictions

        .withColumn(
            "prediction_int",
            col("prediction").cast("int")
        )

        .withColumn(
            "prediction_label",
            when(
                col("prediction_int") == 0,
                "NORMAL"
            )
            .when(
                col("prediction_int") == 1,
                "FIRE_RISK"
            )
            .when(
                col("prediction_int") == 2,
                "FIRE"
            )
            .otherwise("UNKNOWN")
        )

        .withColumn(
            "probability_normal",
            prob_normal(col("probability"))
        )

        .withColumn(
            "probability_risk",
            prob_risk(col("probability"))
        )

        .withColumn(
            "probability_fire",
            prob_fire(col("probability"))
        )
    )


    # ========================================================
    # Ghi toàn bộ batch vào MariaDB
    # ========================================================

    mariadb_df = predictions.select(
        "sensor_id",
        "zone",
        "timestamp",
        "temperature",
        "humidity",
        "smoke_ppm",
        "lpg_gas_ppm",
        "co_gas_ppm",
        col("prediction_int").alias("prediction"),
        "prediction_label",
        "probability_normal",
        "probability_risk",
        "probability_fire"
    )


    mariadb_df.write.jdbc(
        url=JDBC_URL,
        table=JDBC_TABLE,
        mode="append",
        properties=JDBC_PROPERTIES
    )


    print("Đã ghi batch vào MariaDB.")


    # ========================================================
    # Chỉ lấy FIRE_RISK và FIRE
    # ========================================================

    abnormal_df = (
        predictions
        .filter(
            col("prediction_int").isin(1, 2)
        )
    )


    if abnormal_df.rdd.isEmpty():

        print("Batch chỉ có NORMAL.")
        print("Không gửi Telegram.")

        return


    # ========================================================
    # Lấy record mới nhất của từng sensor + zone
    # ========================================================

    window_spec = (
        Window
        .partitionBy(
            "sensor_id",
            "zone"
        )
        .orderBy(
            desc("timestamp")
        )
    )


    abnormal_latest = (
        abnormal_df
        .withColumn(
            "rn",
            row_number().over(window_spec)
        )
        .filter(
            col("rn") == 1
        )
        .drop("rn")
    )


    # ========================================================
    # FIRE
    # ========================================================

    fire_rows = (
    abnormal_latest
    .filter(
        col("prediction_int") == 2
    )
    .select(
        "sensor_id",
        "zone",
        "timestamp",
        "temperature",
        "smoke_ppm",
        "lpg_gas_ppm",
        "co_gas_ppm",
        "probability_fire"
    )
    .collect()
)

    # ========================================================
    # FIRE_RISK
    # ========================================================

    risk_rows = (
    abnormal_latest
    .filter(
        col("prediction_int") == 1
    )
    .select(
        "sensor_id",
        "zone",
        "timestamp",
        "temperature",
        "smoke_ppm",
        "lpg_gas_ppm",
        "co_gas_ppm",
        "probability_risk"
    )
    .collect()
)


    fire_rows = [
        row.asDict()
        for row in fire_rows
    ]


    risk_rows = [
        row.asDict()
        for row in risk_rows
    ]


    print(
        f"FIRE sensors      : {len(fire_rows)}"
    )

    print(
        f"FIRE_RISK sensors : {len(risk_rows)}"
    )


    # ========================================================
    # Telegram
    # ========================================================

    send_telegram_alert(
        fire_rows,
        risk_rows
    )


# ============================================================
# Start streaming
# ============================================================

query = (
    clean_stream
    .writeStream
    .foreachBatch(write_to_mariadb)
    .outputMode("append")
    .option(
        "checkpointLocation",
        "hdfs://localhost:9000/"
        "smart_factory_project/checkpoints/"
        "sensor_mariadb_telegram_3class"
    )
    .trigger(
        processingTime="30 seconds"
    )
    .start()
)


print(
    "Spark Streaming -> "
    "Spark ML -> MariaDB -> Telegram đang chạy..."
)

query.awaitTermination()
