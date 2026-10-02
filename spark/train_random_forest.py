from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
import time

# ============================================================
# Spark session
# ============================================================

spark = (
    SparkSession.builder
    .appName("SmartFactory-RandomForest-3Class")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

# ============================================================
# 1. Đọc dữ liệu training từ HDFS
# ============================================================

INPUT_PATH = (
    "hdfs://localhost:9000/"
    "smart_factory_training/sensor_training.csv"
)

df = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "true")
    .csv(INPUT_PATH)
)

print("\n========== DATA ==========")

df.printSchema()
df.show(10, truncate=False)

# ============================================================
# 2. Kiểm tra 3 class
# ============================================================

print("\n========== CLASS DISTRIBUTION ==========")

df.groupBy("label").count().orderBy("label").show()

# ============================================================
# 3. Feature columns
# ============================================================

feature_cols = [
    "temperature",
    "humidity",
    "smoke_ppm",
    "lpg_gas_ppm",
    "co_gas_ppm"
]

assembler = VectorAssembler(
    inputCols=feature_cols,
    outputCol="features"
)

# ============================================================
# 4. Chia train/test
# ============================================================

train_df, test_df = df.randomSplit(
    [0.8, 0.2],
    seed=42
)

train_df.cache()
test_df.cache()

print("Train count:", train_df.count())
print("Test count :", test_df.count())

# ============================================================
# 5. Evaluators cho bài toán 3 class
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
# 6. 4 cấu hình Random Forest
# ============================================================

configs = [
    ("RF1", 50, 5),
    ("RF2", 100, 8),
    ("RF3", 150, 10),
    ("RF4", 200, 12)
]

results = []

# ============================================================
# 7. Train từng model
# ============================================================

for name, num_trees, max_depth in configs:

    print("\n" + "=" * 80)
    print(
        f"{name} | "
        f"numTrees={num_trees} | "
        f"maxDepth={max_depth}"
    )
    print("=" * 80)

    rf = RandomForestClassifier(
        labelCol="label",
        featuresCol="features",
        predictionCol="prediction",
        numTrees=num_trees,
        maxDepth=max_depth,
        seed=42
    )

    pipeline = Pipeline(
        stages=[
            assembler,
            rf
        ]
    )

    # --------------------------------------------------------
    # Training
    # --------------------------------------------------------

    start_time = time.time()

    model = pipeline.fit(train_df)

    training_time = time.time() - start_time

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    predictions = model.transform(test_df)

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    accuracy = accuracy_evaluator.evaluate(predictions)
    f1 = f1_evaluator.evaluate(predictions)
    precision = precision_evaluator.evaluate(predictions)
    recall = recall_evaluator.evaluate(predictions)

    print(f"Training time : {training_time:.2f} seconds")
    print(f"Accuracy      : {accuracy:.4f}")
    print(f"F1            : {f1:.4f}")
    print(f"Precision     : {precision:.4f}")
    print(f"Recall        : {recall:.4f}")

    # --------------------------------------------------------
    # Confusion matrix
    # --------------------------------------------------------

    print("\nConfusion Matrix:")

    (
        predictions
        .groupBy("label", "prediction")
        .count()
        .orderBy("label", "prediction")
        .show()
    )

    # --------------------------------------------------------
    # Feature importance
    # --------------------------------------------------------

    rf_model = model.stages[-1]

    print("Feature Importance:")

    for feature, importance in zip(
        feature_cols,
        rf_model.featureImportances
    ):
        print(
            f"{feature:20s} : {importance:.4f}"
        )

    # --------------------------------------------------------
    # Save model
    # --------------------------------------------------------

    model_path = (
        "hdfs://localhost:9000/"
        "smart_factory_project/models/"
        f"random_forest_3class_{name.lower()}"
    )

    model.write().overwrite().save(model_path)

    print("\nModel saved:")
    print(model_path)

    # --------------------------------------------------------
    # Store results
    # --------------------------------------------------------

    results.append({
        "model": name,
        "numTrees": num_trees,
        "maxDepth": max_depth,
        "accuracy": accuracy,
        "f1": f1,
        "precision": precision,
        "recall": recall,
        "training_time": training_time
    })

# ============================================================
# 8. Summary
# ============================================================

print("\n")
print("=" * 110)
print("RANDOM FOREST SUMMARY")
print("=" * 110)

print(
    f"{'Model':<8}"
    f"{'Trees':<8}"
    f"{'Depth':<8}"
    f"{'Accuracy':<12}"
    f"{'F1':<12}"
    f"{'Precision':<12}"
    f"{'Recall':<12}"
    f"{'Time(s)':<10}"
)

for r in results:

    print(
        f"{r['model']:<8}"
        f"{r['numTrees']:<8}"
        f"{r['maxDepth']:<8}"
        f"{r['accuracy']:<12.4f}"
        f"{r['f1']:<12.4f}"
        f"{r['precision']:<12.4f}"
        f"{r['recall']:<12.4f}"
        f"{r['training_time']:<10.2f}"
    )

print("=" * 110)

spark.stop()
