import os
import pandas as pd
import pymysql
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Smart Factory Monitoring",
    page_icon="🔥",
    layout="wide"
)


# ============================================================
# AUTO REFRESH - 30 seconds
# ============================================================

st_autorefresh(
    interval=30000,
    key="smart_factory_refresh"
)


# ============================================================
# DATABASE
# ============================================================

DB_PASSWORD = os.getenv("MARIADB_PASSWORD", "")

if not DB_PASSWORD:
    st.error("Chưa có MARIADB_PASSWORD.")
    st.stop()


def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password=DB_PASSWORD,
        database="smart_factory",
        cursorclass=pymysql.cursors.DictCursor
    )


# ============================================================
# HEADER
# ============================================================

st.title("🔥 SMART FACTORY")
st.subheader("Hệ thống giám sát và cảnh báo cháy theo thời gian thực")
st.caption(
    "Spark Structured Streaming → Spark ML → MariaDB → Streamlit"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

try:
    conn = get_connection()
except Exception as e:
    st.error(f"Không kết nối được MariaDB: {e}")
    st.stop()


# ============================================================
# SUMMARY
# ============================================================

with conn.cursor() as cursor:

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM sensor_predictions
    """)
    total = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM sensor_predictions
        WHERE prediction = 0
    """)
    normal = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM sensor_predictions
        WHERE prediction = 1
    """)
    risk = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM sensor_predictions
        WHERE prediction = 2
    """)
    fire = cursor.fetchone()["total"]


# ============================================================
# KPI
# ============================================================

st.markdown("### 📊 Tổng quan")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "TỔNG RECORD",
    f"{total:,}"
)

col2.metric(
    "🟢 NORMAL",
    f"{normal:,}"
)

col3.metric(
    "🟡 FIRE_RISK",
    f"{risk:,}"
)

col4.metric(
    "🔴 FIRE",
    f"{fire:,}"
)


# ============================================================
# STATUS SUMMARY
# ============================================================

st.markdown("---")
st.markdown("### 🚦 Tình trạng hệ thống")

if fire > 0:

    st.error(
        f"🔥 Đang có {fire:,} record được dự đoán là FIRE."
    )

elif risk > 0:

    st.warning(
        f"⚠️ Đang có {risk:,} record được dự đoán là FIRE_RISK."
    )

else:

    st.success(
        "✅ Hệ thống hiện đang ở trạng thái NORMAL."
    )


# ============================================================
# LATEST DATA
# ============================================================

st.markdown("---")
st.markdown("### 📡 Dữ liệu sensor mới nhất")

with conn.cursor() as cursor:

    cursor.execute("""
        SELECT
            sensor_id,
            zone,
            timestamp,
            temperature,
            humidity,
            smoke_ppm,
            lpg_gas_ppm,
            co_gas_ppm,
            prediction,
            prediction_label,
            probability_normal,
            probability_risk,
            probability_fire
        FROM sensor_predictions
        ORDER BY id DESC
        LIMIT 50
    """)

    latest_rows = cursor.fetchall()


latest_df = pd.DataFrame(latest_rows)


if latest_df.empty:

    st.info("Chưa có dữ liệu.")

else:

    latest_df["prediction_label"] = latest_df[
        "prediction_label"
    ].map({
        "NORMAL": "🟢 NORMAL",
        "FIRE_RISK": "🟡 FIRE_RISK",
        "FIRE": "🔴 FIRE"
    }).fillna(latest_df["prediction_label"])

    latest_df["probability_normal"] = (
        latest_df["probability_normal"] * 100
    ).round(2)

    latest_df["probability_risk"] = (
        latest_df["probability_risk"] * 100
    ).round(2)

    latest_df["probability_fire"] = (
        latest_df["probability_fire"] * 100
    ).round(2)

    latest_df = latest_df.rename(columns={
        "sensor_id": "Sensor",
        "zone": "Khu vực",
        "timestamp": "Thời gian",
        "temperature": "Nhiệt độ (°C)",
        "humidity": "Độ ẩm (%)",
        "smoke_ppm": "Khói (ppm)",
        "lpg_gas_ppm": "LPG (ppm)",
        "co_gas_ppm": "CO (ppm)",
        "prediction": "Prediction",
        "prediction_label": "Trạng thái",
        "probability_normal": "Xác suất NORMAL (%)",
        "probability_risk": "Xác suất FIRE_RISK (%)",
        "probability_fire": "Xác suất FIRE (%)"
    })

    st.dataframe(
        latest_df,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# ABNORMAL ALERTS
# ============================================================

st.markdown("---")
st.markdown("### 🚨 Cảnh báo gần nhất")

with conn.cursor() as cursor:

    cursor.execute("""
        SELECT
            sensor_id,
            zone,
            timestamp,
            temperature,
            smoke_ppm,
            lpg_gas_ppm,
            co_gas_ppm,
            prediction_label,
            probability_risk,
            probability_fire
        FROM sensor_predictions
        WHERE prediction IN (1, 2)
        ORDER BY id DESC
        LIMIT 30
    """)

    alert_rows = cursor.fetchall()


alert_df = pd.DataFrame(alert_rows)


if alert_df.empty:

    st.success("✅ Chưa phát hiện cảnh báo.")

else:

    alert_df["probability_risk"] = (
        alert_df["probability_risk"] * 100
    ).round(2)

    alert_df["probability_fire"] = (
        alert_df["probability_fire"] * 100
    ).round(2)

    alert_df = alert_df.rename(columns={
        "sensor_id": "Sensor",
        "zone": "Khu vực",
        "timestamp": "Thời gian",
        "temperature": "Nhiệt độ (°C)",
        "smoke_ppm": "Khói (ppm)",
        "lpg_gas_ppm": "LPG (ppm)",
        "co_gas_ppm": "CO (ppm)",
        "prediction_label": "Trạng thái",
        "probability_risk": "Xác suất FIRE_RISK (%)",
        "probability_fire": "Xác suất FIRE (%)"
    })

    st.dataframe(
        alert_df,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# ZONE SUMMARY
# ============================================================

st.markdown("---")
st.markdown("### 🏭 Các khu vực đang có cảnh báo")

with conn.cursor() as cursor:

    cursor.execute("""
        SELECT
            zone,
            prediction_label,
            COUNT(*) AS total
        FROM sensor_predictions
        WHERE prediction IN (1, 2)
        GROUP BY zone, prediction_label
        ORDER BY zone, prediction_label
    """)

    zone_rows = cursor.fetchall()


zone_df = pd.DataFrame(zone_rows)


if zone_df.empty:

    st.success("✅ Hiện chưa có khu vực bất thường.")

else:

    zone_df = zone_df.rename(columns={
        "zone": "Khu vực",
        "prediction_label": "Trạng thái",
        "total": "Số record"
    })

    st.dataframe(
        zone_df,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "Dữ liệu được cập nhật tự động mỗi 30 giây."
)

conn.close()
