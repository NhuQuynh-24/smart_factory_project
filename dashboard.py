import os
import pymysql
import pandas as pd
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None


# =========================================================
# CẤU HÌNH TRANG
# =========================================================

st.set_page_config(
    page_title="NHÀ MÁY THÔNG MINH",
    page_icon="🔥",
    layout="wide"
)


# =========================================================
# CSS GIAO DIỆN
# =========================================================

st.markdown("""
<style>

.stApp {
    background: #0b1220;
    color: #e5e7eb;
}

.block-container {
    max-width: 1500px;
    padding-top: 1.4rem;
}


/* ================= HEADER ================= */

.hero {
    background: linear-gradient(
        135deg,
        #111827,
        #172554,
        #0f172a
    );

    border: 1px solid #26344d;
    border-radius: 20px;

    padding: 24px 28px;
    margin-bottom: 18px;

    box-shadow: 0 10px 35px #0004;
}

.hero-title {
    font-size: 32px;
    font-weight: 800;
    color: #f8fafc;
}

.hero-sub {
    color: #94a3b8;
    font-size: 14px;
    margin-top: 5px;
}

.online {
    display: inline-block;

    background: #22c55e18;
    color: #4ade80;

    border: 1px solid #22c55e55;

    padding: 7px 13px;
    border-radius: 999px;

    font-weight: 700;
    font-size: 13px;
}


/* ================= THẺ THỐNG KÊ ================= */

.card {
    background: #111827;

    border: 1px solid #26344d;
    border-radius: 16px;

    padding: 18px 20px;

    min-height: 120px;

    box-shadow: 0 8px 25px #0003;
}

.green {
    border-top: 3px solid #22c55e;
}

.yellow {
    border-top: 3px solid #f59e0b;
}

.red {
    border-top: 3px solid #ef4444;
}

.blue {
    border-top: 3px solid #38bdf8;
}

.label {
    color: #94a3b8;

    font-size: 12px;
    font-weight: 700;

    text-transform: uppercase;
    letter-spacing: .7px;
}

.value {
    font-size: 34px;
    font-weight: 800;

    margin-top: 8px;

    color: #f8fafc;
}

.note {
    color: #64748b;

    font-size: 12px;

    margin-top: 3px;
}


/* ================= TIÊU ĐỀ SECTION ================= */

.title {
    font-size: 20px;
    font-weight: 800;

    color: #f8fafc;

    margin: 20px 0 10px;
}

.sub {
    color: #64748b;

    font-size: 12px;

    margin-top: -6px;
    margin-bottom: 12px;
}


/* ================= CẢNH BÁO ================= */

.alert {
    border-radius: 16px;

    padding: 16px;
    margin-bottom: 10px;

    border: 1px solid;
}

.fire {
    background: #ef444412;
    border-color: #ef444466;
}

.risk {
    background: #f59e0b12;
    border-color: #f59e0b66;
}

.alert-title {
    font-size: 17px;
    font-weight: 800;

    margin-bottom: 7px;
}

.meta {
    color: #cbd5e1;

    font-size: 13px;

    line-height: 1.65;
}


/* ================= KHÔNG CÓ CẢNH BÁO ================= */

.ok {
    background: #22c55e0d;

    border: 1px solid #22c55e44;

    border-radius: 16px;

    padding: 24px;

    text-align: center;

    color: #86efac;

    font-weight: 700;
}


/* ================= KHU VỰC ================= */

.zone {
    background: #111827;

    border: 1px solid #26344d;

    border-radius: 14px;

    padding: 13px;

    min-height: 90px;

    margin-bottom: 10px;
}

.zone-name {
    font-size: 13px;

    font-weight: 700;

    color: #e2e8f0;
}

.zone-count {
    font-size: 11px;

    color: #64748b;

    margin-top: 5px;
}

.pill {
    display: inline-block;

    margin-top: 8px;

    padding: 4px 8px;

    border-radius: 999px;

    font-size: 10px;

    font-weight: 800;
}

.pn {
    background: #22c55e18;
    color: #4ade80;
}

.pr {
    background: #f59e0b18;
    color: #fbbf24;
}

.pf {
    background: #ef444418;
    color: #f87171;
}


/* ================= ẨN STREAMLIT ================= */

#MainMenu,
footer,
header {
    visibility: hidden;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# CẤU HÌNH MARIADB
# =========================================================

DB_HOST = os.getenv(
    "MARIADB_HOST",
    "localhost"
)

DB_PORT = int(
    os.getenv(
        "MARIADB_PORT",
        "3306"
    )
)

DB_USER = os.getenv(
    "MARIADB_USER",
    "root"
)

DB_PASSWORD = os.getenv(
    "MARIADB_PASSWORD",
    ""
)

DB_NAME = os.getenv(
    "MARIADB_DATABASE",
    "smart_factory"
)


# =========================================================
# KẾT NỐI MARIADB
# =========================================================

@st.cache_resource
def db():

    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,

        cursorclass=pymysql.cursors.DictCursor,

        autocommit=True
    )


# =========================================================
# ĐỌC DỮ LIỆU
# =========================================================

def load_data():

    query = """
    SELECT
        id,
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
        probability_fire,
        created_at

    FROM sensor_predictions

    ORDER BY id DESC

    LIMIT 500
    """

    return pd.read_sql(
        query,
        db()
    )


# =========================================================
# HÀM CHUYỂN FLOAT AN TOÀN
# =========================================================

def safe_float(value):

    try:

        if value is None:
            return 0.0

        return float(value)

    except (TypeError, ValueError):

        return 0.0


# =========================================================
# TỰ ĐỘNG REFRESH 30 GIÂY
# =========================================================

if st_autorefresh:

    st_autorefresh(
        interval=30000,
        key="smart_factory_refresh"
    )


# =========================================================
# ĐỌC DATABASE
# =========================================================

try:

    df = load_data()

except Exception as e:

    st.error(
        f"❌ Không thể kết nối MariaDB: {e}"
    )

    st.stop()


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div class="hero">

        <div style="
            display:flex;
            justify-content:space-between;
            align-items:center;
            gap:20px;
        ">

            <div>

                <div class="hero-title">
                    🔥 NHÀ MÁY THÔNG MINH
                </div>

                <div class="hero-sub">
                    Hệ thống giám sát và cảnh báo nguy cơ cháy nổ
                    theo thời gian thực
                </div>

            </div>

            <div class="online">
                ● HỆ THỐNG ĐANG HOẠT ĐỘNG
            </div>

        </div>

    </div>
    """,
    unsafe_allow_html=True
)


# =========================================================
# CHƯA CÓ DỮ LIỆU
# =========================================================

if df.empty:

    st.markdown(
        """
        <div class="ok">

            📡

            <br><br>

            ĐANG CHỜ DỮ LIỆU SENSOR

            <br><br>

            <span style="
                font-size:12px;
                color:#64748b;
            ">

                Python Sensor
                →
                Kafka
                →
                Spark Structured Streaming
                →
                Spark ML
                →
                MariaDB

            </span>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.stop()


# =========================================================
# CHUẨN HÓA DỮ LIỆU
# =========================================================

df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce"
)

df["prediction_label"] = (
    df["prediction_label"]
    .fillna("NORMAL")
)


# =========================================================
# LẤY TRẠNG THÁI MỚI NHẤT CỦA MỖI SENSOR
# =========================================================

latest = (
    df
    .sort_values("id")
    .drop_duplicates(
        "sensor_id",
        keep="last"
    )
)


status = (
    latest["prediction_label"]
    .fillna("NORMAL")
)


normal = int(
    (status == "NORMAL").sum()
)

risk = int(
    (status == "FIRE_RISK").sum()
)

fire = int(
    (status == "FIRE").sum()
)

sensors = int(
    latest["sensor_id"].nunique()
)


# =========================================================
# 4 THẺ THỐNG KÊ
# =========================================================

cols = st.columns(4)


cards = [

    (
        "green",
        "🟢 BÌNH THƯỜNG",
        normal,
        "Sensor đang hoạt động bình thường"
    ),

    (
        "yellow",
        "🟡 NGUY CƠ CHÁY",
        risk,
        "Phát hiện điều kiện bất thường"
    ),

    (
        "red",
        "🔴 CHÁY",
        fire,
        "Phát hiện tình trạng cháy"
    ),

    (
        "blue",
        "📡 SENSOR",
        sensors,
        "Số sensor đang được giám sát"
    )
]


for column, data in zip(
    cols,
    cards
):

    css_class, label, value, note = data

    with column:

        st.markdown(
            f"""
            <div class="card {css_class}">

                <div class="label">
                    {label}
                </div>

                <div class="value">
                    {value}
                </div>

                <div class="note">
                    {note}
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )


# =========================================================
# TRẠNG THÁI GIÁM SÁT
# =========================================================

st.markdown(
    """
    <div class="title">
        🚨 TRẠNG THÁI GIÁM SÁT HIỆN TẠI
    </div>
    """,
    unsafe_allow_html=True
)


left, right = st.columns(
    [1.55, 1],
    gap="large"
)


# =========================================================
# BIỂU ĐỒ SENSOR
# =========================================================

with left:

    st.markdown(
        "**📈 Biểu đồ thông số sensor theo thời gian**"
    )


    metric = st.selectbox(

        "Chọn thông số",

        [
            "temperature",
            "smoke_ppm",
            "lpg_gas_ppm",
            "co_gas_ppm"
        ],

        format_func=lambda x: {

            "temperature":
                "🌡 Nhiệt độ (°C)",

            "smoke_ppm":
                "💨 Khói (ppm)",

            "lpg_gas_ppm":
                "🔥 Khí LPG (ppm)",

            "co_gas_ppm":
                "☠ Khí CO (ppm)"

        }[x],

        label_visibility="collapsed"
    )


    chart_data = (

        df

        .sort_values("timestamp")

        .dropna(
            subset=["timestamp"]
        )

        .tail(200)
    )


    if not chart_data.empty:

        trend = (

            chart_data

            .groupby("timestamp")[metric]

            .mean()

            .tail(100)

            .to_frame()
        )


        st.line_chart(

            trend,

            height=300,

            use_container_width=True

        )


# =========================================================
# CẢNH BÁO ĐANG HOẠT ĐỘNG
# =========================================================

with right:

    st.markdown(
        "**🚨 Cảnh báo đang hoạt động**"
    )


    alerts = (

        latest[

            latest["prediction_label"]

            .isin(
                [
                    "FIRE",
                    "FIRE_RISK"
                ]
            )

        ]

        .sort_values(
            "id",
            ascending=False
        )
    )


    if alerts.empty:

        st.markdown(
            """
            <div class="ok">

                🟢

                <br><br>

                KHÔNG CÓ CẢNH BÁO

                <br><br>

                <span style="
                    font-size:12px;
                    color:#64748b;
                ">

                    Tất cả sensor đang hoạt động
                    bình thường.

                </span>

            </div>
            """,
            unsafe_allow_html=True
        )


    else:

        for _, r in alerts.head(4).iterrows():

            is_fire = (
                r["prediction_label"]
                == "FIRE"
            )


            css_class = (
                "fire"
                if is_fire
                else "risk"
            )


            icon = (
                "🔴"
                if is_fire
                else "🟡"
            )


            title = (

                "PHÁT HIỆN CHÁY"

                if is_fire

                else

                "PHÁT HIỆN NGUY CƠ CHÁY"

            )


            st.markdown(
                f"""
                <div class="alert {css_class}">

                    <div class="alert-title">

                        {icon}
                        {title}

                    </div>


                    <div class="meta">

                        <b>Sensor:</b>
                        {r["sensor_id"]}

                        <br>

                        <b>Khu vực:</b>
                        {r["zone"]}

                        <br>

                        <b>Nhiệt độ:</b>
                        {safe_float(r["temperature"]):.1f}
                        °C

                        <br>

                        <b>Khói:</b>
                        {safe_float(r["smoke_ppm"]):.1f}
                        ppm

                        <br>

                        <b>Khí LPG:</b>
                        {safe_float(r["lpg_gas_ppm"]):.1f}
                        ppm

                        <br>

                        <b>Khí CO:</b>
                        {safe_float(r["co_gas_ppm"]):.1f}
                        ppm

                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )


# =========================================================
# TRẠNG THÁI CÁC KHU VỰC
# =========================================================

st.markdown(
    """
    <div class="title">
        🏭 TRẠNG THÁI CÁC KHU VỰC
    </div>
    """,
    unsafe_allow_html=True
)


st.markdown(
    """
    <div class="sub">
        Trạng thái mới nhất của từng khu vực trong nhà máy
    </div>
    """,
    unsafe_allow_html=True
)


zones = (

    latest

    .groupby("zone")

    .agg(

        sensors=(
            "sensor_id",
            "nunique"
        ),

        fire=(
            "prediction_label",
            lambda x:
                (x == "FIRE").sum()
        ),

        risk=(
            "prediction_label",
            lambda x:
                (x == "FIRE_RISK").sum()
        )

    )

    .reset_index()
)


zone_columns = st.columns(5)


for i, (_, r) in enumerate(
    zones.iterrows()
):

    if r["fire"] > 0:

        icon = "🔴"
        label = "CHÁY"
        pill = "pf"


    elif r["risk"] > 0:

        icon = "🟡"
        label = "NGUY CƠ CHÁY"
        pill = "pr"


    else:

        icon = "🟢"
        label = "BÌNH THƯỜNG"
        pill = "pn"


    with zone_columns[i % 5]:

        st.markdown(
            f"""
            <div class="zone">

                <div class="zone-name">

                    {icon}
                    {r["zone"]}

                </div>


                <div class="zone-count">

                    {int(r["sensors"])}
                    sensor đang giám sát

                </div>


                <span class="pill {pill}">

                    {label}

                </span>

            </div>
            """,
            unsafe_allow_html=True
        )


# =========================================================
# KẾT QUẢ DỰ ĐOÁN SPARK ML
# =========================================================

st.markdown(
    """
    <div class="title">
        🤖 KẾT QUẢ DỰ ĐOÁN CỦA SPARK ML
    </div>
    """,
    unsafe_allow_html=True
)


# Lấy bản ghi mới nhất
latest_row = (

    df

    .sort_values(
        "id",
        ascending=False
    )

    .iloc[0]
)


# ---------------------------------------------------------
# LẤY XÁC SUẤT AN TOÀN
# ---------------------------------------------------------

p_normal = safe_float(
    latest_row.get(
        "probability_normal",
        0
    )
)


p_risk = safe_float(
    latest_row.get(
        "probability_risk",
        0
    )
)


p_fire = safe_float(
    latest_row.get(
        "probability_fire",
        0
    )
)


a, b, c = st.columns(3)


with a:

    st.metric(
        "🟢 BÌNH THƯỜNG",
        f"{p_normal * 100:.1f}%"
    )


with b:

    st.metric(
        "🟡 NGUY CƠ CHÁY",
        f"{p_risk * 100:.1f}%"
    )


with c:

    st.metric(
        "🔴 CHÁY",
        f"{p_fire * 100:.1f}%"
    )


# =========================================================
# DỮ LIỆU SENSOR MỚI NHẤT
# =========================================================

st.markdown(
    """
    <div class="title">
        📋 DỮ LIỆU SENSOR MỚI NHẤT
    </div>
    """,
    unsafe_allow_html=True
)


filter1, filter2 = st.columns(2)


# ---------------------------------------------------------
# LỌC KHU VỰC
# ---------------------------------------------------------

with filter1:

    zone_filter = st.selectbox(

        "Lọc theo khu vực",

        [
            "Tất cả"
        ]
        +
        sorted(
            df["zone"]
            .dropna()
            .unique()
            .tolist()
        )

    )


# ---------------------------------------------------------
# LỌC TRẠNG THÁI
# ---------------------------------------------------------

with filter2:

    status_filter = st.selectbox(

        "Lọc theo trạng thái",

        [
            "Tất cả",
            "NORMAL",
            "FIRE_RISK",
            "FIRE"
        ],

        format_func=lambda x: {

            "Tất cả":
                "Tất cả",

            "NORMAL":
                "🟢 Bình thường",

            "FIRE_RISK":
                "🟡 Nguy cơ cháy",

            "FIRE":
                "🔴 Cháy"

        }[x]

    )


# =========================================================
# ÁP DỤNG BỘ LỌC
# =========================================================

table = df.copy()


if zone_filter != "Tất cả":

    table = table[
        table["zone"]
        == zone_filter
    ]


if status_filter != "Tất cả":

    table = table[
        table["prediction_label"]
        == status_filter
    ]


table = (

    table

    .sort_values(
        "id",
        ascending=False
    )

    .head(50)
)


# =========================================================
# CHỌN CỘT HIỂN THỊ
# =========================================================

table = table[
    [
        "sensor_id",
        "zone",
        "timestamp",
        "temperature",
        "humidity",
        "smoke_ppm",
        "lpg_gas_ppm",
        "co_gas_ppm",
        "prediction_label"
    ]
].copy()


# =========================================================
# ĐỔI TÊN CỘT SANG TIẾNG VIỆT
# =========================================================

table.columns = [

    "Sensor",

    "Khu vực",

    "Thời gian",

    "Nhiệt độ (°C)",

    "Độ ẩm (%)",

    "Khói (ppm)",

    "LPG (ppm)",

    "CO (ppm)",

    "Trạng thái"

]


# =========================================================
# ĐỔI TRẠNG THÁI SANG TIẾNG VIỆT
# =========================================================

table["Trạng thái"] = (

    table["Trạng thái"]

    .map({

        "NORMAL":
            "🟢 Bình thường",

        "FIRE_RISK":
            "🟡 Nguy cơ cháy",

        "FIRE":
            "🔴 Cháy"

    })

    .fillna(
        table["Trạng thái"]
    )

)


# =========================================================
# HIỂN THỊ BẢNG
# =========================================================

st.dataframe(

    table,

    use_container_width=True,

    hide_index=True,

    height=430

)


# =========================================================
# CHÂN TRANG
# =========================================================

st.markdown(
    """
    <div style="
        text-align:center;
        color:#475569;
        font-size:12px;
        padding:20px 0
    ">

        NHÀ MÁY THÔNG MINH

        • Python Sensor
        →
        Kafka
        →
        Spark Structured Streaming
        →
        Spark ML
        →
        MariaDB
        →
        Streamlit

        <br>

        Tự động cập nhật dữ liệu sau mỗi 30 giây

    </div>
    """,
    unsafe_allow_html=True
)
