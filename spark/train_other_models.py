from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.classification import (
    DecisionTreeClassifier,
    LogisticRegression
)
from pyspark.ml.evaluation import MulticlassClassificationEvaluator


# ============================================================
# SPARK SESSION
# ============================================================

spark = (
    SparkSession.builder
    .appName("SmartFactory-Other-ML-Models")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")


# ============================================================
# PATHS
# ============================================================

# Training dataset trên HDFS
TRAINING_PATH = (
    "hdfs://localhost:9000/"
    "smart_factory_training/"
    "sensor_training.csv"
)

# Nơi lưu model Decision Tree
DT_MODEL_PATH = (
    "hdfs://localhost:9000/"
    "smart_factory_project/models/"
    "decision_tree_3class"
)

# Nơi lưu model Multinomial Logistic Regression
LR_MODEL_PATH = (
    "hdfs://localhost:9000/"
    "smart_factory_project/models/"
    "multinomial_logistic_regression_3class"
)


# ============================================================
# 1. READ TRAINING DATA
# ============================================================

print("\n" + "=" * 80)
print("READING TRAINING DATA")
print("=" * 80)

df = (
    spark.read
    .option("header", True)
    .option("inferSchema", True)
    .csv(TRAINING_PATH)
)

print("Total records:", df.count())


# ============================================================
# 2. FEATURE ENGINEERING
# ============================================================

# 5 đặc trưng cảm biến sử dụng cho Machine Learning
feature_columns = [
    "temperature",
    "humidity",
    "smoke_ppm",
    "lpg_gas_ppm",
    "co_gas_ppm"
]

# Chuyển 5 cột thành một vector features
assembler = VectorAssembler(
    inputCols=feature_columns,
    outputCol="features"
)


# ============================================================
# 3. SPLIT DATASET
# ============================================================

# Chia dữ liệu:
# 80% -> TRAINING DATA
# 20% -> TEST DATA

train_df, test_df = df.randomSplit(
    [0.8, 0.2],
    seed=42
)

print("\n" + "=" * 80)
print("DATASET SPLIT")
print("=" * 80)

print("Training records:", train_df.count())
print("Testing records :", test_df.count())


# ============================================================
# 4. EVALUATION METRICS
# ============================================================

accuracy_evaluator = MulticlassClassificationEvaluator(
    labelCol="label",
    predictionCol="prediction",
    metricName="accuracy"
)

f1_evaluator = MulticlassClassificationEvaluator(
    labelCol="label",
    predictionCol="prediction",
    metricName="f1"
)

precision_evaluator = MulticlassClassificationEvaluator(
    labelCol="label",
    predictionCol="prediction",
    metricName="weightedPrecision"
)

recall_evaluator = MulticlassClassificationEvaluator(
    labelCol="label",
    predictionCol="prediction",
    metricName="weightedRecall"
)


# ============================================================
# 5. DECISION TREE
# ============================================================

print("\n" + "=" * 80)
print("DECISION TREE")
print("=" * 80)


# ------------------------------------------------------------
# 5.1 CREATE MODEL
# ------------------------------------------------------------

dt = DecisionTreeClassifier(
    labelCol="label",
    featuresCol="features",
    maxDepth=5,
    seed=42
)

dt_pipeline = Pipeline(
    stages=[
        assembler,
        dt
    ]
)


# ------------------------------------------------------------
# 5.2 TRAIN - HUẤN LUYỆN MÔ HÌNH
# ------------------------------------------------------------

print("\n[TRAIN] Decision Tree training...")

dt_model = dt_pipeline.fit(train_df)

print("[TRAIN] Decision Tree training completed.")


# ------------------------------------------------------------
# 5.3 TEST - KIỂM TRA MÔ HÌNH
# ------------------------------------------------------------

print("\n[TEST] Applying Decision Tree to test data...")

dt_predictions = dt_model.transform(test_df)

print("[TEST] Prediction completed.")


# ------------------------------------------------------------
# 5.4 EVALUATION - ĐÁNH GIÁ MÔ HÌNH
# ------------------------------------------------------------

print("\n[EVALUATION] Decision Tree")

dt_accuracy = accuracy_evaluator.evaluate(dt_predictions)
dt_f1 = f1_evaluator.evaluate(dt_predictions)
dt_precision = precision_evaluator.evaluate(dt_predictions)
dt_recall = recall_evaluator.evaluate(dt_predictions)

print(f"Accuracy : {dt_accuracy:.4f}")
print(f"F1       : {dt_f1:.4f}")
print(f"Precision: {dt_precision:.4f}")
print(f"Recall   : {dt_recall:.4f}")


# ------------------------------------------------------------
# 5.5 CONFUSION MATRIX
# ------------------------------------------------------------

print("\nConfusion Matrix:")

(
    dt_predictions
    .groupBy("label", "prediction")
    .count()
    .orderBy("label", "prediction")
    .show()
)


# ------------------------------------------------------------
# 5.6 SAVE MODEL
# ------------------------------------------------------------

print("\nSaving Decision Tree model...")

dt_model.write().overwrite().save(
    DT_MODEL_PATH
)

print("Decision Tree model saved:")
print(DT_MODEL_PATH)


# ============================================================
# 6. MULTINOMIAL LOGISTIC REGRESSION
# ============================================================

print("\n" + "=" * 80)
print("MULTINOMIAL LOGISTIC REGRESSION")
print("=" * 80)


# ------------------------------------------------------------
# 6.1 CREATE MODEL
# ------------------------------------------------------------

lr = LogisticRegression(
    labelCol="label",
    featuresCol="features",
    family="multinomial",
    maxIter=100,
    regParam=0.0
)

lr_pipeline = Pipeline(
    stages=[
        assembler,
        lr
    ]
)


# ------------------------------------------------------------
# 6.2 TRAIN - HUẤN LUYỆN MÔ HÌNH
# ------------------------------------------------------------

print("\n[TRAIN] Multinomial Logistic Regression training...")

lr_model = lr_pipeline.fit(train_df)

print(
    "[TRAIN] Multinomial Logistic Regression "
    "training completed."
)


# ------------------------------------------------------------
# 6.3 TEST - KIỂM TRA MÔ HÌNH
# ------------------------------------------------------------

print(
    "\n[TEST] Applying Multinomial Logistic Regression "
    "to test data..."
)

lr_predictions = lr_model.transform(test_df)

print("[TEST] Prediction completed.")


# ------------------------------------------------------------
# 6.4 EVALUATION - ĐÁNH GIÁ MÔ HÌNH
# ------------------------------------------------------------

print(
    "\n[EVALUATION] "
    "Multinomial Logistic Regression"
)

lr_accuracy = accuracy_evaluator.evaluate(
    lr_predictions
)

lr_f1 = f1_evaluator.evaluate(
    lr_predictions
)

lr_precision = precision_evaluator.evaluate(
    lr_predictions
)

lr_recall = recall_evaluator.evaluate(
    lr_predictions
)

print(f"Accuracy : {lr_accuracy:.4f}")
print(f"F1       : {lr_f1:.4f}")
print(f"Precision: {lr_precision:.4f}")
print(f"Recall   : {lr_recall:.4f}")


# ------------------------------------------------------------
# 6.5 CONFUSION MATRIX
# ------------------------------------------------------------

print("\nConfusion Matrix:")

(
    lr_predictions
    .groupBy("label", "prediction")
    .count()
    .orderBy("label", "prediction")
    .show()
)


# ------------------------------------------------------------
# 6.6 SAVE MODEL
# ------------------------------------------------------------

print(
    "\nSaving Multinomial Logistic Regression model..."
)

lr_model.write().overwrite().save(
    LR_MODEL_PATH
)

print("Multinomial Logistic Regression model saved:")
print(LR_MODEL_PATH)


# ============================================================
# 7. FINAL MODEL COMPARISON
# ============================================================

print("\n" + "=" * 80)
print("MODEL COMPARISON")
print("=" * 80)

print(
    f"Decision Tree                  | "
    f"Accuracy={dt_accuracy:.4f} | "
    f"F1={dt_f1:.4f} | "
    f"Precision={dt_precision:.4f} | "
    f"Recall={dt_recall:.4f}"
)

print(
    f"Multinomial Logistic Regression | "
    f"Accuracy={lr_accuracy:.4f} | "
    f"F1={lr_f1:.4f} | "
    f"Precision={lr_precision:.4f} | "
    f"Recall={lr_recall:.4f}"
)

print("\nAll training and testing completed successfully.")


# ============================================================
# 8. STOP SPARK
# ============================================================

spark.stop()
