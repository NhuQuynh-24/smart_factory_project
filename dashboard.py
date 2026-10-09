"""
================================================================================
SMART FACTORY | HỆ THỐNG GIÁM SÁT VÀ CẢNH BÁO NGUY CƠ CHÁY NỔ THỜI GIAN THỰC
--------------------------------------------------------------------------------
Kiến trúc luồng xử lý dữ liệu lớn (Big Data Architecture):
  1. Sensor Simulator (50 cảm biến tại 10 phân xưởng/kho) -> Apache Kafka (sensor-raw)
  2. Spark Structured Streaming đọc Kafka, tiền xử lý và trích xuất vector đặc trưng
  3. Spark ML Pipeline (Random Forest Classifier: RF3) dự đoán 3 trạng thái:
     - NORMAL (Bình thường: 0.0)
     - FIRE_RISK (Nguy cơ cháy: 1.0)
     - FIRE (Cháy khẩn cấp: 2.0)
  4. Spark Streaming ghi kết quả vào bảng `sensor_predictions` trên MariaDB
  5. Spark Streaming gửi cảnh báo Telegram tức thời khi phát hiện FIRE_RISK hoặc FIRE
  6. Dashboard Streamlit kết nối MariaDB, hiển thị trạng thái thời gian thực và lịch sử
================================================================================
"""

import os
from datetime import datetime
import pandas as pd
import pymysql
import streamlit as st

# Thử nạp streamlit_autorefresh nếu môi trường đã cài đặt
try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None


# ==============================================================================
# 1. CẤU HÌNH TRANG STREAMLIT (PAGE CONFIG)
# ==============================================================================

st.set_page_config(
    page_title="SMART FACTORY | Giám Sát Cháy Nổ Thời Gian Thực",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==============================================================================
# 2. CẤU HÌNH KẾT NỐI MARIADB & TRUY VẤN
# ==============================================================================

DB_HOST = os.getenv("MARIADB_HOST", "localhost")
DB_PORT = int(os.getenv("MARIADB_PORT", "3306"))
DB_USER = os.getenv("MARIADB_USER", "root")
DB_PASSWORD = os.getenv("MARIADB_PASSWORD", "")
DB_NAME = os.getenv("MARIADB_DATABASE", "smart_factory")
# Bản ghi quá ngưỡng này được xem là cũ, không mặc định là an toàn.
SENSOR_STALE_SECONDS = int(os.getenv("SENSOR_STALE_SECONDS", "120"))


@st.cache_resource
def db():
    """Tạo kết nối MariaDB; thông tin xác thực chỉ lấy từ biến môi trường."""
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
    )


SELECT_COLUMNS = """
    id, sensor_id, zone, timestamp, temperature, humidity,
    smoke_ppm, lpg_gas_ppm, co_gas_ppm, prediction, prediction_label,
    probability_normal, probability_risk, probability_fire, created_at
"""


def _read_query(query):
    """Đọc truy vấn MariaDB bằng DictCursor và tạo DataFrame đúng cột."""

    last_error = None

    for attempt in range(2):
        conn = db()

        try:
            conn.ping(reconnect=True)

            with conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

            return pd.DataFrame(rows)

        except Exception as exc:
            last_error = exc

            if attempt == 0:
                try:
                    db.clear()
                except Exception:
                    pass
            else:
                raise last_error

    raise last_error

def load_data():
    """Lấy 500 dòng lịch sử và bản ghi mới nhất của mỗi sensor."""

    history_query = f"""
        SELECT {SELECT_COLUMNS}
        FROM sensor_predictions
        ORDER BY id DESC
        LIMIT 500
    """

    latest_query = f"""
        SELECT
            sp.id,
            sp.sensor_id,
            sp.zone,
            sp.timestamp,
            sp.temperature,
            sp.humidity,
            sp.smoke_ppm,
            sp.lpg_gas_ppm,
            sp.co_gas_ppm,
            sp.prediction,
            sp.prediction_label,
            sp.probability_normal,
            sp.probability_risk,
            sp.probability_fire,
            sp.created_at
        FROM sensor_predictions AS sp
        INNER JOIN (
            SELECT sensor_id, MAX(id) AS max_id
            FROM sensor_predictions
            GROUP BY sensor_id
        ) AS latest_ids
            ON sp.id = latest_ids.max_id
        ORDER BY sp.id DESC
    """

    history = _read_query(history_query)
    latest = _read_query(latest_query)

    return history, latest


def safe_float(value, default=0.0):
    """Chuyển giá trị sang float; xử lý cả None, NaN và giá trị không hợp lệ."""
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def prepare_data(frame):
    frame = frame.copy()
    if frame.empty:
        return frame
    for column in [
        "temperature", "humidity", "smoke_ppm", "lpg_gas_ppm", "co_gas_ppm",
        "prediction", "probability_normal", "probability_risk", "probability_fire",
    ]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ["timestamp", "created_at"]:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
    if "prediction_label" not in frame.columns:
        frame["prediction_label"] = "UNKNOWN"
    else:
        frame["prediction_label"] = frame["prediction_label"].astype("string").str.upper().fillna("UNKNOWN")
        frame.loc[~frame["prediction_label"].isin(["NORMAL", "FIRE_RISK", "FIRE"]), "prediction_label"] = "UNKNOWN"
    if "sensor_id" in frame.columns:
        frame["sensor_id"] = frame["sensor_id"].astype("string")
    if "zone" in frame.columns:
        frame["zone"] = frame["zone"].astype("string").fillna("UNKNOWN")
    return frame


def add_freshness(frame):
    """Dùng created_at (thời điểm lưu DB) trước, timestamp là phương án dự phòng."""
    frame = frame.copy()
    if frame.empty:
        frame["data_time"] = pd.NaT
        frame["age_seconds"] = pd.Series(dtype="float64")
        frame["is_fresh"] = pd.Series(dtype="bool")
        return frame
    frame["data_time"] = frame["created_at"] if "created_at" in frame.columns else pd.NaT
    if "timestamp" in frame.columns:
        frame["data_time"] = frame["data_time"].fillna(frame["timestamp"])
    now = pd.Timestamp.now()
    if getattr(frame["data_time"].dt, "tz", None) is not None:
        now = pd.Timestamp.now(tz=frame["data_time"].dt.tz)
    frame["age_seconds"] = (now - frame["data_time"]).dt.total_seconds()
    frame["is_fresh"] = frame["age_seconds"].between(-60, SENSOR_STALE_SECONDS, inclusive="both")
    return frame


def format_datetime(value):
    if value is None or pd.isna(value):
        return "Không có thời gian"
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def format_measure(value, digits=1):
    """Giá trị thiếu hiển thị là dấu gạch, không giả làm số 0."""
    if value is None or pd.isna(value):
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


# Từ điển ánh xạ tên phân xưởng/kho sang tên tiếng Việt dễ đọc
ZONE_DISPLAY_NAMES = {
    "Kho_Nguyen_Lieu": "Kho Nguyên Liệu",
    "Kho_Vat_Lieu": "Kho Vật Liệu",
    "Kho_Hoa_Chat": "Kho Hóa Chất",
    "Kho_Thanh_Pham": "Kho Thành Phẩm",
    "Kho_Linh_Kien": "Kho Linh Kiện",
    "Xuong_San_Xuat": "Xưởng Sản Xuất",
    "Khu_Dong_Goi": "Khu Đóng Gói",
    "Khu_Kiem_Tra": "Khu Kiểm Tra",
    "Phong_May": "Phòng Máy",
    "Khu_Bao_Tri": "Khu Bảo Trì"
}

ALL_FACTORY_ZONES = list(ZONE_DISPLAY_NAMES.keys())


# ==============================================================================
# 3. SIDEBAR: THÔNG TIN HỆ THỐNG & ĐIỀU KHIỂN
# ==============================================================================

with st.sidebar:
    st.markdown("### 🏭 Quản Trị Hệ Thống")
    st.caption("SCADA Control Center • Smart Factory")

    st.divider()

    # Nút bấm làm mới thủ công
    if st.button("🔄 Làm mới dữ liệu", use_container_width=True, type="primary"):
        st.rerun()

    # Tùy chọn chu kỳ tự động làm mới
    refresh_options = {
        "10 giây": 10000,
        "30 giây (Khuyên dùng)": 30000,
        "60 giây": 60000,
        "Tắt tự động làm mới": None
    }
    selected_refresh = st.selectbox(
        "Chu kỳ tự động cập nhật:",
        options=list(refresh_options.keys()),
        index=1
    )
    refresh_ms = refresh_options[selected_refresh]

    if st_autorefresh and refresh_ms:
        st_autorefresh(interval=refresh_ms, key="smart_factory_auto_refresh")
    elif refresh_ms and not st_autorefresh:
        st.caption("ℹ️ *Cài đặt streamlit-autorefresh để tự động làm mới.*")

    st.divider()

    # Thông tin kết nối MariaDB
    st.markdown("#### 🗄️ Trạng Thái Kết Nối")
    st.write(f"• **Máy chủ**: `{DB_HOST}:{DB_PORT}`")
    st.write(f"• **Cơ sở dữ liệu**: `{DB_NAME}`")
    st.write(f"• **Bảng**: `sensor_predictions`")

    st.divider()

    # Luồng kiến trúc công nghệ
    st.markdown("#### ⚙️ Hạ Tầng Xử Lý")
    st.markdown("""
    1. **Sensors**: 50 thiết bị IoT (10 khu vực)
    2. **Message Broker**: Apache Kafka 2.8.1
    3. **Streaming**: Spark 3.5.5 Structured Streaming
    4. **AI Core**: Spark ML Random Forest (RF3)
    5. **Database**: MariaDB 10.6.23
    6. **Cảnh báo**: Telegram Bot Real-time
    """)


# ==============================================================================
# 4. ĐỌC VÀ TIỀN XỬ LÝ DỮ LIỆU
# ==============================================================================

try:
    df, latest = load_data()
except Exception as e:
    st.error("### ❌ Không thể đọc dữ liệu từ MariaDB")
    st.info(
        "Kiểm tra dịch vụ MariaDB, database `smart_factory`, bảng `sensor_predictions` "
        "và biến môi trường kết nối trên Ubuntu."
    )
    with st.expander("Chi tiết lỗi kỹ thuật"):
        st.code(str(e))
    st.stop()

if df.empty and latest.empty:
    st.info("### 📡 MariaDB chưa có bản ghi sensor nào")
    st.write(
        "Kiểm tra luồng Python Sensor → Kafka → Spark Structured Streaming / Spark ML → MariaDB. "
        "Khi có dữ liệu, dashboard sẽ tự hiển thị trạng thái."
    )
    st.stop()

df = prepare_data(df)
latest = prepare_data(latest)
df = add_freshness(df)
latest = add_freshness(latest)
df = df.sort_values("id", ascending=False).reset_index(drop=True)
latest = latest.sort_values("id", ascending=False).reset_index(drop=True)

# Tổng quan lấy từ bản ghi mới nhất của từng sensor trên toàn bảng, không chỉ 500 dòng lịch sử.
fresh_latest = latest[latest["is_fresh"]].copy()
stale_latest = latest[~latest["is_fresh"]].copy()

# DEBUG: Kiểm tra dữ liệu dashboard thực sự đọc được
with st.expander("🔍 DEBUG - Kiểm tra dữ liệu cảm biến", expanded=True):
    st.write("Số bản ghi mới nhất theo sensor:", len(latest))
    st.write("Số sensor có dữ liệu mới:", latest["is_fresh"].sum())
    st.write("Số sensor có dữ liệu cũ:", (~latest["is_fresh"]).sum())
    st.write("Thời gian hiện tại của Python:", pd.Timestamp.now())
    st.write("Thời gian bản ghi mới nhất trong dashboard:")

    debug_cols = [
        c for c in [
            "sensor_id",
            "prediction_label",
            "created_at",
            "timestamp",
            "age_seconds",
            "is_fresh"
        ]
        if c in latest.columns
    ]

    st.dataframe(
        latest[debug_cols].head(60),
        use_container_width=True,
        hide_index=True
    )
total_sensors = int(latest["sensor_id"].nunique())
fresh_count = int(fresh_latest["sensor_id"].nunique())
stale_count = int(stale_latest["sensor_id"].nunique())
unknown_count = int((fresh_latest["prediction_label"] == "UNKNOWN").sum())
normal_count = int((fresh_latest["prediction_label"] == "NORMAL").sum())
risk_count = int((fresh_latest["prediction_label"] == "FIRE_RISK").sum())
fire_count = int((fresh_latest["prediction_label"] == "FIRE").sum())

pct_normal = (normal_count / fresh_count * 100) if fresh_count else 0.0
pct_risk = (risk_count / fresh_count * 100) if fresh_count else 0.0
pct_fire = (fire_count / fresh_count * 100) if fresh_count else 0.0

# Cảnh báo hiện tại lấy trạng thái mới nhất từng sensor; cảnh báo cũ vẫn hiện nhưng được đánh dấu dữ liệu cũ.
active_abnormal = latest[latest["prediction_label"].isin(["FIRE", "FIRE_RISK"])].copy()
active_abnormal["status_priority"] = active_abnormal["prediction_label"].map({"FIRE": 0, "FIRE_RISK": 1})
active_abnormal = active_abnormal.sort_values(
    by=["status_priority", "is_fresh", "id"], ascending=[True, False, False]
)

# Đây chỉ là nhật ký trong 500 bản ghi gần nhất, không phải toàn bộ lịch sử vĩnh viễn.
historical_alerts = df[df["prediction_label"].isin(["FIRE", "FIRE_RISK"])].sort_values(
    "id", ascending=False
)

latest_record = latest.sort_values("id", ascending=False).iloc[0] if not latest.empty else None
sync_time_str = datetime.now().strftime("%H:%M:%S")
latest_time_value = None if latest_record is None else latest_record.get("created_at")
if latest_record is not None and (latest_time_value is None or pd.isna(latest_time_value)):
    latest_time_value = latest_record.get("timestamp")
latest_ts_str = format_datetime(latest_time_value) if latest_record is not None else "Không có dữ liệu"


# ==============================================================================
# 6. HEADER TRANG CHÍNH & BANNER AN TOÀN TỔNG QUAN
# ==============================================================================

header_col, meta_col = st.columns([2.5, 1.0], gap="medium")

with header_col:
    st.markdown("## 🏭 SMART FACTORY | GIÁM SÁT CHÁY NỔ THỜI GIAN THỰC")
    st.caption("Trung tâm điều hành SCADA • Xử lý dữ liệu lớn Apache Spark & Phân loại an toàn Spark ML")

with meta_col:
    st.write(f"⏱️ **Đồng bộ lúc**: `{sync_time_str}`")
    st.write(f"📡 **Bản ghi mới nhất**: `{latest_ts_str}`")

# Banner chỉ khẳng định những gì dữ liệu hiện có hỗ trợ.
if fire_count > 0:
    st.error(
        f"🚨 **BÁO ĐỘNG CHÁY**: {fire_count} sensor có bản ghi mới nhất được phân loại FIRE. "
        "Kiểm tra hiện trường và thực hiện quy trình PCCC của nhà máy."
    )
elif risk_count > 0:
    st.warning(
        f"⚠️ **NGUY CƠ CHÁY**: {risk_count} sensor có bản ghi mới nhất được phân loại FIRE_RISK. "
        "Đề nghị kiểm tra khu vực tương ứng."
    )
elif fresh_count == 0 or stale_count > 0 or unknown_count > 0:
    st.warning(
        f"⚠️ Chưa đủ dữ liệu mới để xác nhận tình trạng an toàn: {stale_count} sensor có dữ liệu cũ, "
        f"{unknown_count} sensor có trạng thái chưa rõ, {fresh_count}/{total_sensors} sensor có dữ liệu mới "
        f"(ngưỡng {SENSOR_STALE_SECONDS} giây)."
    )
else:
    st.success(
        f"✅ Không ghi nhận FIRE/FIRE_RISK trong dữ liệu mới nhất của {fresh_count} sensor. "
        "Đây không thay thế hệ thống báo cháy và kiểm tra an toàn thực tế."
    )


# ==============================================================================
# 7. 4 THẺ CHỈ SỐ KPI CHÍNH (NATIVE STREAMLIT METRICS)
# ==============================================================================

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    with st.container(border=True):
        st.metric(
            label="🟢 Bình Thường (Normal)",
            value=f"{normal_count} sensor",
            delta=f"{pct_normal:.1f}% toàn nhà máy",
            delta_color="normal"
        )
        st.caption("Cảm biến trong giới hạn an toàn")

with kpi2:
    with st.container(border=True):
        st.metric(
            label="🟡 Nguy Cơ Cháy (Fire Risk)",
            value=f"{risk_count} sensor",
            delta=f"{pct_risk:.1f}%" if risk_count > 0 else "0.0%",
            delta_color="inverse"
        )
        st.caption("Chỉ số nhiệt hoặc khí gas tăng cao")

with kpi3:
    with st.container(border=True):
        st.metric(
            label="🔴 Báo Động Cháy (Fire)",
            value=f"{fire_count} sensor",
            delta=f"{pct_fire:.1f}%" if fire_count > 0 else "0.0%",
            delta_color="inverse"
        )
        st.caption("Cảnh báo khẩn cấp cấp độ cao nhất")

with kpi4:
    with st.container(border=True):
        st.metric(
            label="📡 Cảm Biến Trực Tuyến",
            value=f"{fresh_count} / {total_sensors}",
            delta=f"Dữ liệu mới trong {SENSOR_STALE_SECONDS}s"
        )
        st.caption("Sensor có bản ghi mới trong ngưỡng thời gian quy định")

st.write("")


# ==============================================================================
# 8. CÁC TAB CHỨC NĂNG CHÍNH
# ==============================================================================

tab_overview, tab_comparison, tab_spark_ml, tab_explorer = st.tabs([
    "📊 Giám Sát Thời Gian Thực",
    "🚨 Đối Chiếu: Hiện Tại vs Lịch Sử",
    "🤖 Phân Tích Mô Hình Spark ML",
    "📋 Tra Cứu Cảm Biến Chi Tiết"
])


# ------------------------------------------------------------------------------
# TAB 1: GIÁM SÁT THỜI GIAN THỰC (BIỂU ĐỒ XU HƯỚNG & ACTIVE ALERTS & 10 ZONES)
# ------------------------------------------------------------------------------
with tab_overview:
    left_col, right_col = st.columns([1.6, 1.0], gap="medium")

    with left_col:
        with st.container(border=True):
            st.markdown("#### 📈 Diễn Biến Thông Số Môi Trường")
            st.caption("Trung bình các bản ghi có cùng timestamp trong 200 bản ghi gần nhất; không đại diện toàn bộ sensor ở mọi thời điểm.")

            metric_choice = st.selectbox(
                "Chọn thông số hiển thị trên biểu đồ:",
                options=["temperature", "smoke_ppm", "lpg_gas_ppm", "co_gas_ppm", "humidity"],
                format_func=lambda x: {
                    "temperature": "🌡️ Nhiệt độ (°C)",
                    "smoke_ppm": "💨 Khói (ppm)",
                    "lpg_gas_ppm": "🔥 Khí LPG (ppm)",
                    "co_gas_ppm": "☠️ Khí CO (ppm)",
                    "humidity": "💧 Độ ẩm (%)"
                }[x],
                index=0
            )

            chart_data = (
                df.sort_values("timestamp")
                .dropna(subset=["timestamp", metric_choice])
                .tail(200)
            )

            if not chart_data.empty:
                trend = (
                    chart_data.groupby("timestamp")[metric_choice]
                    .mean()
                    .tail(100)
                    .to_frame()
                )

                metric_labels = {
                    "temperature": "Nhiệt độ (°C)",
                    "smoke_ppm": "Nồng độ khói (ppm)",
                    "lpg_gas_ppm": "Nồng độ LPG (ppm)",
                    "co_gas_ppm": "Nồng độ CO (ppm)",
                    "humidity": "Độ ẩm (%)"
                }
                trend.columns = [metric_labels[metric_choice]]
                st.line_chart(trend, height=300, use_container_width=True)

                # Các chỉ số tham chiếu nhanh
                c_now = float(trend.iloc[-1, 0]) if not trend.empty else 0.0
                c_avg = float(trend.mean().iloc[0]) if not trend.empty else 0.0
                c_max = float(trend.max().iloc[0]) if not trend.empty else 0.0

                ref_col1, ref_col2, ref_col3 = st.columns(3)
                ref_col1.metric("Hiện tại", f"{c_now:.2f}")
                ref_col2.metric("Trung bình", f"{c_avg:.2f}")
                ref_col3.metric("Đỉnh điểm", f"{c_max:.2f}")
            else:
                st.info("Chưa có đủ điểm dữ liệu theo mốc thời gian để vẽ biểu đồ.")

    with right_col:
        with st.container(border=True):
            st.markdown("#### 🚨 Cảnh Báo Hiện Tại")
            st.caption("Các cảm biến có trạng thái bất thường tại bản ghi mới nhất")

            if active_abnormal.empty:
                if fresh_count == 0 or stale_count > 0 or unknown_count > 0:
                    st.warning("Chưa ghi nhận FIRE/FIRE_RISK trong dữ liệu mới, nhưng có sensor cũ hoặc chưa rõ trạng thái. Không thể kết luận toàn bộ nhà máy an toàn.")
                else:
                    st.success("Không ghi nhận FIRE/FIRE_RISK trong dữ liệu mới nhất của các sensor.")
            else:
                for _, row in active_abnormal.head(4).iterrows():
                    is_fire = row["prediction_label"] == "FIRE"
                    alert_type = "🔴 BÁO ĐỘNG CHÁY" if is_fire else "🟡 NGUY CƠ CHÁY"
                    zone_name = ZONE_DISPLAY_NAMES.get(row["zone"], row["zone"])
                    time_value = row.get("created_at")
                    if time_value is None or pd.isna(time_value):
                        time_value = row.get("timestamp")
                    ts = format_datetime(time_value)
                    freshness_label = "DỮ LIỆU MỚI" if bool(row.get("is_fresh", False)) else "DỮ LIỆU CŨ — kiểm tra sensor"

                    with st.container(border=True):
                        st.markdown(f"**{alert_type}** | ⏱️ `{ts}` | **{freshness_label}**")
                        st.write(f"• **Cảm biến:** `{row['sensor_id']}` | **Khu vực:** `{zone_name}`")
                        m1, m2, m3, m4 = st.columns(4)
                        m1.write(f"🌡️ {format_measure(row.get('temperature'), 1)}°C")
                        m2.write(f"💨 {format_measure(row.get('smoke_ppm'), 0)} ppm")
                        m3.write(f"🔥 {format_measure(row.get('lpg_gas_ppm'), 0)} ppm")
                        m4.write(f"☠️ {format_measure(row.get('co_gas_ppm'), 0)} ppm")

    st.write("")

    # --- GIÁM SÁT 10 KHU VỰC NHÀ MÁY ---
    with st.container(border=True):
        st.markdown("#### 🏭 Bản Đồ An Toàn 10 Khu Vực Phân Xưởng & Kho Bãi")
        st.caption("Tổng hợp trạng thái tức thời theo vị trí địa lý của toàn bộ 10 khu vực sản xuất")

        zone_stats = (
            fresh_latest.groupby("zone")
            .agg(
                total_sensors=("sensor_id", "nunique"),
                fire_sensors=("prediction_label", lambda x: int((x == "FIRE").sum())),
                risk_sensors=("prediction_label", lambda x: int((x == "FIRE_RISK").sum())),
                avg_temp=("temperature", "mean"),
                avg_smoke=("smoke_ppm", "mean")
            )
            .to_dict(orient="index")
        )

        zone_cols = st.columns(5)
        for idx, zone_key in enumerate(ALL_FACTORY_ZONES):
            col = zone_cols[idx % 5]
            stats = zone_stats.get(zone_key, {
                "total_sensors": 0, "fire_sensors": 0, "risk_sensors": 0, "avg_temp": 0.0, "avg_smoke": 0.0
            })
            z_total = stats["total_sensors"]
            z_fire = stats["fire_sensors"]
            z_risk = stats["risk_sensors"]
            z_title = ZONE_DISPLAY_NAMES.get(zone_key, zone_key)

            with col:
                with st.container(border=True):
                    st.markdown(f"**{z_title}**")
                    st.caption(f"{z_total} sensor có dữ liệu mới")
                    if z_total == 0:
                        historical_zone = latest[latest["zone"] == zone_key]
                        if historical_zone.empty:
                            st.info("Chưa có dữ liệu")
                        else:
                            st.warning("Dữ liệu cũ — kiểm tra sensor")
                        st.caption("Không đủ dữ liệu mới để đánh giá khu vực")
                    elif z_fire > 0:
                        st.error(f"🔴 {z_fire} Báo Cháy")
                        st.caption(f"TB dữ liệu mới: {format_measure(stats['avg_temp'], 1)}°C | {format_measure(stats['avg_smoke'], 0)} ppm khói")
                    elif z_risk > 0:
                        st.warning(f"🟡 {z_risk} Nguy Cơ")
                        st.caption(f"TB dữ liệu mới: {format_measure(stats['avg_temp'], 1)}°C | {format_measure(stats['avg_smoke'], 0)} ppm khói")
                    else:
                        st.success("🟢 Không ghi nhận nguy cơ")
                        st.caption(f"TB dữ liệu mới: {format_measure(stats['avg_temp'], 1)}°C | {format_measure(stats['avg_smoke'], 0)} ppm khói")


# ------------------------------------------------------------------------------
# TAB 2: ĐỐI CHIẾU: HIỆN TẠI VS LỊCH SỬ CẢNH BÁO (REQUIREMENT 8)
# ------------------------------------------------------------------------------
with tab_comparison:
    st.markdown("### 🚨 Đối Chiếu Trạng Thái Hiện Tại & Lịch Sử Cảnh Báo")
    st.info(
        "💡 **Nguyên lý phân biệt dữ liệu:**\n\n"
        "• **Trạng thái hiện tại**: Được tính toán từ **bản ghi mới nhất** của từng cảm biến (trong số 50 cảm biến). "
        "Phản ánh trực tiếp hiện trạng an toàn vật lý của nhà máy ngay lúc này.\n\n"
        "• **Lịch sử cảnh báo**: Các sự kiện FIRE/FIRE_RISK nằm trong **500 bản ghi mới nhất** được tải từ MariaDB; "
        "đây không nhất thiết là toàn bộ lịch sử của database."
    )

    comp_kpi1, comp_kpi2, comp_kpi3, comp_kpi4 = st.columns(4)
    comp_kpi1.metric("Sensor có FIRE/FIRE_RISK ở bản ghi mới nhất", f"{len(active_abnormal)} / {total_sensors}")
    comp_kpi2.metric("Sự kiện trong 500 bản ghi mới nhất", f"{len(historical_alerts)} sự kiện")
    comp_kpi3.metric("Số lần báo CHÁY lịch sử", f"{int((historical_alerts['prediction_label'] == 'FIRE').sum())} lần")
    comp_kpi4.metric("Số lần NGUY CƠ lịch sử", f"{int((historical_alerts['prediction_label'] == 'FIRE_RISK').sum())} lần")

    st.write("")

    subtab_current, subtab_history = st.tabs([
        "⚡ Trạng Thái Tức Thời Của 50 Cảm Biến (Bản ghi mới nhất)",
        "📜 Toàn Bộ Nhật Ký Cảnh Báo Lịch Sử (Incident Log)"
    ])

    with subtab_current:
        st.markdown("#### Bảng Trạng Thái Mới Nhất Từng Cảm Biến")
        st.caption("Mỗi cảm biến hiển thị đúng 1 dòng đại diện cho giá trị đo mới nhất")

        current_table = latest[[
            "sensor_id", "zone", "timestamp", "created_at", "is_fresh", "temperature", "humidity",
            "smoke_ppm", "lpg_gas_ppm", "co_gas_ppm", "prediction_label"
        ]].copy()

        current_table["zone_vn"] = current_table["zone"].map(ZONE_DISPLAY_NAMES).fillna(current_table["zone"])
        current_table["time_value"] = current_table["created_at"].fillna(current_table["timestamp"])
        current_table["timestamp_str"] = current_table["time_value"].apply(format_datetime)
        current_table["freshness"] = current_table["is_fresh"].map({True: "🟢 Dữ liệu mới", False: "⚠️ Dữ liệu cũ"})
        current_table["status_priority"] = current_table["prediction_label"].map({"FIRE": 0, "FIRE_RISK": 1, "UNKNOWN": 2, "NORMAL": 3}).fillna(2)

        current_table["status_visual"] = current_table["prediction_label"].map({
            "NORMAL": "🟢 Bình thường",
            "FIRE_RISK": "🟡 Nguy cơ cháy",
            "FIRE": "🔴 Cháy"
        }).fillna(current_table["prediction_label"])

        current_display = current_table[[
            "sensor_id", "zone_vn", "timestamp_str", "freshness",
            "temperature", "humidity", "smoke_ppm", "lpg_gas_ppm", "co_gas_ppm",
            "status_visual", "status_priority"
        ]].sort_values(by=["status_priority", "sensor_id"], ascending=[True, True]).drop(columns=["status_priority"])

        current_display.columns = [
            "Mã Sensor", "Khu Vực", "Thời Gian Ghi Nhận", "Độ Mới Dữ Liệu",
            "Nhiệt Độ (°C)", "Độ Ẩm (%)", "Khói (ppm)", "LPG (ppm)", "CO (ppm)",
            "Trạng Thái Hiện Tại"
        ]

        st.dataframe(
            current_display,
            use_container_width=True,
            hide_index=True,
            height=400
        )

    with subtab_history:
        st.markdown("#### Nhật Ký Tất Cả Cảnh Báo Đã Ghi Nhận Trong Cơ Sở Dữ Liệu")
        st.caption("Chỉ gồm cảnh báo trong 500 bản ghi mới nhất đã tải; xác suất được hiển thị theo phần trăm.")

        if historical_alerts.empty:
            st.success("Hệ thống chưa ghi nhận bất kỳ sự kiện nguy cơ hoặc cháy nào trong các bản ghi lưu trữ.")
        else:
            hist_filter_col1, hist_filter_col2 = st.columns(2)
            with hist_filter_col1:
                hist_type_filter = st.selectbox(
                    "Lọc loại cảnh báo lịch sử:",
                    options=["Tất cả", "FIRE (Cháy)", "FIRE_RISK (Nguy cơ)"],
                    key="hist_type_filter"
                )
            with hist_filter_col2:
                hist_zone_filter = st.selectbox(
                    "Lọc theo khu vực lịch sử:",
                    options=["Tất cả"] + ALL_FACTORY_ZONES,
                    format_func=lambda z: ZONE_DISPLAY_NAMES.get(z, z) if z != "Tất cả" else "Tất cả khu vực",
                    key="hist_zone_filter"
                )

            filtered_hist = historical_alerts.copy()
            if hist_type_filter == "FIRE (Cháy)":
                filtered_hist = filtered_hist[filtered_hist["prediction_label"] == "FIRE"]
            elif hist_type_filter == "FIRE_RISK (Nguy cơ)":
                filtered_hist = filtered_hist[filtered_hist["prediction_label"] == "FIRE_RISK"]

            if hist_zone_filter != "Tất cả":
                filtered_hist = filtered_hist[filtered_hist["zone"] == hist_zone_filter]

            filtered_hist_table = filtered_hist[[
                "id", "sensor_id", "zone", "timestamp", "temperature",
                "smoke_ppm", "lpg_gas_ppm", "co_gas_ppm", "prediction_label",
                "probability_risk", "probability_fire"
            ]].copy()

            filtered_hist_table["zone_vn"] = filtered_hist_table["zone"].map(ZONE_DISPLAY_NAMES).fillna(filtered_hist_table["zone"])
            filtered_hist_table["timestamp_str"] = filtered_hist_table["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
            filtered_hist_table["status_visual"] = filtered_hist_table["prediction_label"].map({
                "FIRE_RISK": "🟡 Nguy cơ cháy",
                "FIRE": "🔴 Báo động cháy"
            }).fillna(filtered_hist_table["prediction_label"])

            disp_hist = filtered_hist_table[[
                "id", "sensor_id", "zone_vn", "timestamp_str",
                "temperature", "smoke_ppm", "lpg_gas_ppm", "co_gas_ppm",
                "probability_risk", "probability_fire", "status_visual"
            ]].copy()

            disp_hist["probability_risk"] = pd.to_numeric(disp_hist["probability_risk"], errors="coerce") * 100
            disp_hist["probability_fire"] = pd.to_numeric(disp_hist["probability_fire"], errors="coerce") * 100
            disp_hist["probability_risk"] = disp_hist["probability_risk"].round(1)
            disp_hist["probability_fire"] = disp_hist["probability_fire"].round(1)
            disp_hist.columns = [
                "ID", "Sensor", "Khu Vực", "Thời Gian Ghi Nhận",
                "Nhiệt Độ (°C)", "Khói (ppm)", "LPG (ppm)", "CO (ppm)",
                "Xác Suất Nguy Cơ (%)", "Xác Suất Cháy (%)", "Cấp Cảnh Báo"
            ]

            st.dataframe(
                disp_hist,
                use_container_width=True,
                hide_index=True,
                height=380
            )

            # Nút tải CSV xuất báo cáo sự cố
            csv_data = disp_hist.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 Xuất báo cáo nhật ký sự cố (CSV)",
                data=csv_data,
                file_name=f"smart_factory_alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )


# ------------------------------------------------------------------------------
# TAB 3: PHÂN TÍCH MÔ HÌNH AI - SPARK ML
# ------------------------------------------------------------------------------
with tab_spark_ml:
    st.markdown("### 🤖 Phân Tích Mô Hình Phân Loại AI (Spark ML)")
    st.caption("Mô hình Random Forest Classifier (RF3) dự đoán 3 trạng thái từ luồng dữ liệu thời gian thực")

    if latest_record is None:
        st.info("Chưa có bản ghi để hiển thị kết quả Spark ML.")
        st.stop()

    p_values = [
        safe_float(latest_record.get("probability_normal"), float("nan")),
        safe_float(latest_record.get("probability_risk"), float("nan")),
        safe_float(latest_record.get("probability_fire"), float("nan")),
    ]
    valid_probabilities = all(pd.notna(value) and value >= 0 for value in p_values)
    total_p = sum(p_values) if valid_probabilities else 0.0
    probabilities_available = valid_probabilities and total_p > 0
    if probabilities_available:
        pct_n, pct_r, pct_f = [(value / total_p) * 100 for value in p_values]
    else:
        pct_n = pct_r = pct_f = None

    pred_lbl = latest_record.get("prediction_label", "UNKNOWN")

    ml_left, ml_right = st.columns([1.2, 1.0], gap="large")

    with ml_left:
        with st.container(border=True):
            st.markdown("#### Xác Suất Dự Đoán Bản Ghi Mới Nhất")
            st.write(
                f"• **Cảm biến:** `{latest_record['sensor_id']}` | "
                f"**Khu vực:** `{ZONE_DISPLAY_NAMES.get(latest_record['zone'], latest_record['zone'])}` | "
                f"**Thời gian:** `{latest_ts_str}`"
            )

            if pred_lbl == "FIRE":
                st.error("🔴 **Kết luận mô hình: BÁO ĐỘNG CHÁY (FIRE - Mã 2.0)**")
            elif pred_lbl == "FIRE_RISK":
                st.warning("🟡 **Kết luận mô hình: NGUY CƠ CHÁY (FIRE_RISK - Mã 1.0)**")
            elif pred_lbl == "NORMAL":
                st.success("🟢 **Kết luận mô hình: BÌNH THƯỜNG (NORMAL - Mã 0.0)**")
            else:
                st.info("⚪ **Kết luận mô hình: CHƯA RÕ TRẠNG THÁI**")

            st.write("")
            if probabilities_available:
                st.write(f"**Bình thường (NORMAL):** `{pct_n:.2f}%`")
                st.progress(min(max(pct_n / 100.0, 0.0), 1.0))
                st.write(f"**Nguy cơ cháy (FIRE_RISK):** `{pct_r:.2f}%`")
                st.progress(min(max(pct_r / 100.0, 0.0), 1.0))
                st.write(f"**Báo động cháy (FIRE):** `{pct_f:.2f}%`")
                st.progress(min(max(pct_f / 100.0, 0.0), 1.0))
            else:
                st.warning("Không có xác suất dự đoán hợp lệ trong bản ghi này; không thể vẽ tỷ lệ xác suất.")

    with ml_right:
        with st.container(border=True):
            st.markdown("#### Kiến Trúc Mô Hình Học Máy")
            st.write("• **Thuật toán**: `RandomForestClassifier` (Spark ML)")
            st.write("• **Phân lớp (3 Classes)**:")
            st.write("  - `0.0`: NORMAL (An toàn)")
            st.write("  - `1.0`: FIRE_RISK (Nguy cơ cháy)")
            st.write("  - `2.0`: FIRE (Cháy khẩn cấp)")
            st.write("• **Số cây quyết định (Num Trees)**: `150`")
            st.write("• **Độ sâu tối đa (Max Depth)**: `10`")
            st.write("• **Các đặc trưng đầu vào (Features)**:")
            st.markdown("""
            1. `temperature`: Nhiệt độ (°C)
            2. `humidity`: Độ ẩm (%)
            3. `smoke_ppm`: Nồng độ khói
            4. `lpg_gas_ppm`: Khí gas LPG
            5. `co_gas_ppm`: Khí CO
            """)
            st.write("• **Pipeline tiền xử lý**: `VectorAssembler` ➔ `StandardScaler` ➔ `RF3`")


# ------------------------------------------------------------------------------
# TAB 4: TRA CỨU CẢM BIẾN CHI TIẾT
# ------------------------------------------------------------------------------
with tab_explorer:
    st.markdown("### 📋 Tra Cứu Dữ Liệu Cảm Biến")
    st.caption("Xem danh sách chi tiết các bản ghi đo đạc mới nhất từ hệ cơ sở dữ liệu")

    f1, f2, f3 = st.columns(3)

    with f1:
        selected_zone = st.selectbox(
            "Lọc theo Khu vực:",
            options=["Tất cả"] + ALL_FACTORY_ZONES,
            format_func=lambda z: ZONE_DISPLAY_NAMES.get(z, z) if z != "Tất cả" else "Tất cả khu vực",
            key="explorer_zone"
        )

    with f2:
        selected_status = st.selectbox(
            "Lọc theo Trạng thái:",
            options=["Tất cả", "NORMAL", "FIRE_RISK", "FIRE"],
            format_func=lambda s: {
                "Tất cả": "Tất cả trạng thái",
                "NORMAL": "🟢 Bình thường",
                "FIRE_RISK": "🟡 Nguy cơ cháy",
                "FIRE": "🔴 Cháy"
            }[s],
            key="explorer_status"
        )

    with f3:
        search_sensor = st.text_input("Tìm kiếm theo mã sensor (VD: S001):", "").strip()

    filtered_df = df.copy()

    if selected_zone != "Tất cả":
        filtered_df = filtered_df[filtered_df["zone"] == selected_zone]

    if selected_status != "Tất cả":
        filtered_df = filtered_df[filtered_df["prediction_label"] == selected_status]

    if search_sensor:
        filtered_df = filtered_df[filtered_df["sensor_id"].astype("string").str.contains(search_sensor, case=False, na=False)]

    display_df = (
        filtered_df.sort_values("id", ascending=False)
        .head(100)[[
            "id", "sensor_id", "zone", "timestamp", "created_at", "is_fresh", "temperature", "humidity",
            "smoke_ppm", "lpg_gas_ppm", "co_gas_ppm", "prediction_label"
        ]].copy()
    )

    display_df["zone"] = display_df["zone"].map(ZONE_DISPLAY_NAMES).fillna(display_df["zone"])
    display_df["timestamp"] = display_df["timestamp"].apply(format_datetime)
    display_df["created_at"] = display_df["created_at"].apply(format_datetime)
    display_df["is_fresh"] = display_df["is_fresh"].map({True: "🟢 Dữ liệu mới", False: "⚠️ Dữ liệu cũ"})

    display_df["prediction_label"] = display_df["prediction_label"].map({
        "NORMAL": "🟢 Bình thường",
        "FIRE_RISK": "🟡 Nguy cơ cháy",
        "FIRE": "🔴 Cháy"
    }).fillna(display_df["prediction_label"])

    display_df.columns = [
        "ID", "Mã Sensor", "Khu Vực", "Thời Gian Sensor", "Thời Điểm Ghi DB", "Độ Mới Dữ Liệu",
        "Nhiệt Độ (°C)", "Độ Ẩm (%)", "Khói (ppm)", "LPG (ppm)", "CO (ppm)",
        "Trạng Thái"
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=450
    )


# ==============================================================================
# 9. FOOTER CHUẨN CÔNG NGHIỆP
# ==============================================================================

st.divider()
st.caption(
    "🏭 **SMART FACTORY INDUSTRIAL SAFETY SYSTEM** | "
    "Kiến trúc: Python Sensor ➔ Apache Kafka ➔ Apache Spark Structured Streaming ➔ Spark ML (Random Forest RF3) ➔ MariaDB ➔ Telegram Bot & Streamlit | "
    f"Dashboard tự động cập nhật theo chu kỳ đã chọn; dữ liệu quá {SENSOR_STALE_SECONDS} giây được đánh dấu cũ."
)

