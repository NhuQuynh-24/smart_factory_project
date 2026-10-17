import time
from pyspark.ml import Pipeline
from pyspark.ml.classification import (
    DecisionTreeClassifier,
    LogisticRegression,
)
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.feature import StandardScaler, VectorAssembler
from pyspark.sql import SparkSession

# ============================================================
# SPARK SESSION
# ============================================================

spark = (
    SparkSession.builder.appName(
        "SmartFactory-Other-ML-Models-3Class"
    ).getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")


# ============================================================
# 1. ĐỌC DỮ LIỆU TRAINING TỪ HDFS
# ============================================================

TRAINING_PATH = "hdfs://localhost:9000/smart_factory_training/sensor_training.csv"

print("\n" + "=" * 80)
print("READING TRAINING DATA")
print("=" * 80)

df = (
    spark.read.option("header", "true")
    .option("inferSchema", "true")
    .csv(TRAINING_PATH)
)

df.printSchema()
df.show(10, truncate=False)

print("\n========== CLASS DISTRIBUTION ==========")
df.groupBy("label").count().orderBy("label").show()


# ============================================================
# 2. FEATURE ENGINEERING
# ============================================================

feature_columns = [
    "temperature",
    "humidity",
    "smoke_ppm",
    "lpg_gas_ppm",
    "co_gas_ppm",
]

# VectorAssembler cho Decision Tree (và bước đầu của Logistic Regression)
assembler = VectorAssembler(inputCols=feature_columns, outputCol="raw_features")

# StandardScaler chuẩn hóa thang đo cho Logistic Regression
scaler = StandardScaler(
    inputCol="raw_features", outputCol="features", withStd=True, withMean=True
)


# ============================================================
# 3. CHIA TRAIN / TEST (80% - 20%, CÙNG SEED=42 VỚI RANDOM FOREST)
# ============================================================

train_df, test_df = df.randomSplit([0.8, 0.2], seed=42)

train_df.cache()
test_df.cache()

print("\n" + "=" * 80)
print("DATASET SPLIT")
print("=" * 80)
print("Training records:", train_df.count())
print("Testing records :", test_df.count())


# ============================================================
# 4. EVALUATORS CHO BÀI TOÁN 3 CLASS
# ============================================================

accuracy_evaluator = MulticlassClassificationEvaluator(
    labelCol="label", predictionCol="prediction", metricName="accuracy"
)

f1_evaluator = MulticlassClassificationEvaluator(
    labelCol="label", predictionCol="prediction", metricName="f1"
)

precision_evaluator = MulticlassClassificationEvaluator(
    labelCol="label", predictionCol="prediction", metricName="weightedPrecision"
)

recall_evaluator = MulticlassClassificationEvaluator(
    labelCol="label", predictionCol="prediction", metricName="weightedRecall"
)


# ============================================================
# 5. HUẤN LUYỆN 4 CẤU HÌNH DECISION TREE (DT1 -> DT4)
# ============================================================
# Đồng bộ maxDepth (5, 8, 10, 12) với RF1, RF2, RF3, RF4 để đối chiếu công bằng

dt_configs = [
    ("DT1", 5, 10),
    ("DT2", 8, 5),
    ("DT3", 10, 2),
    ("DT4", 12, 1),
]

dt_results = []

for name, max_depth, min_instances in dt_configs:
  print("\n" + "=" * 80)
  print(
      f"{name} | maxDepth={max_depth} | minInstancesPerNode={min_instances}"
  )
  print("=" * 80)

  dt = DecisionTreeClassifier(
      labelCol="label",
      featuresCol="raw_features",
      predictionCol="prediction",
      maxDepth=max_depth,
      minInstancesPerNode=min_instances,
      seed=42,
  )

  dt_pipeline = Pipeline(stages=[assembler, dt])

  # Training
  start_time = time.time()
  dt_model = dt_pipeline.fit(train_df)
  training_time = time.time() - start_time

  # Prediction
  dt_predictions = dt_model.transform(test_df)

  # Metrics
  accuracy = accuracy_evaluator.evaluate(dt_predictions)
  f1 = f1_evaluator.evaluate(dt_predictions)
  precision = precision_evaluator.evaluate(dt_predictions)
  recall = recall_evaluator.evaluate(dt_predictions)

  print(f"Training time : {training_time:.2f} seconds")
  print(f"Accuracy      : {accuracy:.4f}")
  print(f"F1            : {f1:.4f}")
  print(f"Precision     : {precision:.4f}")
  print(f"Recall        : {recall:.4f}")

  # Confusion Matrix
  print("\nConfusion Matrix:")
  (
      dt_predictions.groupBy("label", "prediction")
      .count()
      .orderBy("label", "prediction")
      .show()
  )

  # Feature Importance
  tree_stage = dt_model.stages[-1]
  print("Feature Importance:")
  for feature, importance in zip(
      feature_columns, tree_stage.featureImportances
  ):
    print(f"{feature:20s} : {importance:.4f}")

  # Save model
  model_path = (
      "hdfs://localhost:9000/"
      "smart_factory_project/models/"
      f"decision_tree_3class_{name.lower()}"
  )
  dt_model.write().overwrite().save(model_path)

  print("\nModel saved:")
  print(model_path)

  dt_results.append({
      "model": name,
      "maxDepth": max_depth,
      "minInstances": min_instances,
      "accuracy": accuracy,
      "f1": f1,
      "precision": precision,
      "recall": recall,
      "training_time": training_time,
  })


# ============================================================
# 6. HUẤN LUYỆN 4 CẤU HÌNH MULTINOMIAL LOGISTIC REGRESSION (LR1 -> LR4)
# ============================================================
# Cấu hình (Tên, maxIter, regParam, elasticNetParam)

lr_configs = [
    ("LR1", 50, 0.1, 0.0),  # L2 Regularization mạnh, ít vòng lặp
    ("LR2", 100, 0.05, 0.0),  # L2 Regularization vừa
    ("LR3", 150, 0.01, 0.5),  # ElasticNet (kết hợp L1 + L2)
    ("LR4", 200, 0.0, 0.0),  # Không Regularization, tối đa vòng lặp
]

lr_results = []

for name, max_iter, reg_param, elastic_net in lr_configs:
  print("\n" + "=" * 80)
  print(
      f"{name} | maxIter={max_iter} | "
      f"regParam={reg_param} | elasticNetParam={elastic_net}"
  )
  print("=" * 80)

  lr = LogisticRegression(
      labelCol="label",
      featuresCol="features",
      predictionCol="prediction",
      family="multinomial",
      maxIter=max_iter,
      regParam=reg_param,
      elasticNetParam=elastic_net,
  )

  lr_pipeline = Pipeline(stages=[assembler, scaler, lr])

  # Training
  start_time = time.time()
  lr_model = lr_pipeline.fit(train_df)
  training_time = time.time() - start_time

  # Prediction
  lr_predictions = lr_model.transform(test_df)

  # Metrics
  accuracy = accuracy_evaluator.evaluate(lr_predictions)
  f1 = f1_evaluator.evaluate(lr_predictions)
  precision = precision_evaluator.evaluate(lr_predictions)
  recall = recall_evaluator.evaluate(lr_predictions)

  print(f"Training time : {training_time:.2f} seconds")
  print(f"Accuracy      : {accuracy:.4f}")
  print(f"F1            : {f1:.4f}")
  print(f"Precision     : {precision:.4f}")
  print(f"Recall        : {recall:.4f}")

  # Confusion Matrix
  print("\nConfusion Matrix:")
  (
      lr_predictions.groupBy("label", "prediction")
      .count()
      .orderBy("label", "prediction")
      .show()
  )

  # Save model
  model_path = (
      "hdfs://localhost:9000/"
      "smart_factory_project/models/"
      f"multinomial_logistic_regression_3class_{name.lower()}"
  )
  lr_model.write().overwrite().save(model_path)

  print("\nModel saved:")
  print(model_path)

  lr_results.append({
      "model": name,
      "maxIter": max_iter,
      "regParam": reg_param,
      "elasticNet": elastic_net,
      "accuracy": accuracy,
      "f1": f1,
      "precision": precision,
      "recall": recall,
      "training_time": training_time,
  })


# ============================================================
# 7. BẢNG TỔNG HỢP KẾT QUẢ (SUMMARY TABLES)
# ============================================================

print("\n")
print("=" * 110)
print("DECISION TREE SUMMARY (DT1 - DT4)")
print("=" * 110)
print(
    f"{'Model':<8}"
    f"{'Depth':<8}"
    f"{'MinInst':<10}"
    f"{'Accuracy':<12}"
    f"{'F1':<12}"
    f"{'Precision':<12}"
    f"{'Recall':<12}"
    f"{'Time(s)':<10}"
)

for r in dt_results:
  print(
      f"{r['model']:<8}"
      f"{r['maxDepth']:<8}"
      f"{r['minInstances']:<10}"
      f"{r['accuracy']:<12.4f}"
      f"{r['f1']:<12.4f}"
      f"{r['precision']:<12.4f}"
      f"{r['recall']:<12.4f}"
      f"{r['training_time']:<10.2f}"
  )
print("=" * 110)

print("\n")
print("=" * 110)
print("MULTINOMIAL LOGISTIC REGRESSION SUMMARY (LR1 - LR4)")
print("=" * 110)
print(
    f"{'Model':<8}"
    f"{'MaxIter':<10}"
    f"{'RegParam':<10}"
    f"{'Elastic':<10}"
    f"{'Accuracy':<12}"
    f"{'F1':<12}"
    f"{'Precision':<12}"
    f"{'Recall':<12}"
    f"{'Time(s)':<10}"
)

for r in lr_results:
  print(
      f"{r['model']:<8}"
      f"{r['maxIter']:<10}"
      f"{r['regParam']:<10.2f}"
      f"{r['elasticNet']:<10.2f}"
      f"{r['accuracy']:<12.4f}"
      f"{r['f1']:<12.4f}"
      f"{r['precision']:<12.4f}"
      f"{r['recall']:<12.4f}"
      f"{r['training_time']:<10.2f}"
  )
print("=" * 110)

print("\nAll training and testing completed successfully.")

spark.stop()
