import math
import os
import time

import requests


# ============================================================
# Telegram configuration
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MAX_MESSAGE_LENGTH = 3500
REQUEST_TIMEOUT = 15


# ============================================================
# Helpers
# ============================================================

def is_missing(value):
    """
    Kiểm tra giá trị bị thiếu, None hoặc NaN.
    """

    if value is None:
        return True

    if isinstance(value, str):

        return value.strip().lower() in (
            "",
            "none",
            "null",
            "nan"
        )

    try:

        return math.isnan(float(value))

    except (TypeError, ValueError):

        return False


def safe_float(value):
    """
    Chuyển giá trị thành float.
    Trả về None nếu dữ liệu không hợp lệ.
    """

    if is_missing(value):
        return None

    try:

        result = float(value)

        if math.isnan(result) or math.isinf(result):
            return None

        return result

    except (TypeError, ValueError):

        return None


def display_value(value, suffix=""):
    """
    Hiển thị dữ liệu cảm biến.
    Không tự biến dữ liệu thiếu thành 0.
    """

    if is_missing(value):
        return "N/A"

    number = safe_float(value)

    if number is not None:
        return f"{number:g}{suffix}"

    return f"{value}{suffix}"


# ============================================================
# Resolve prediction label
# ============================================================

def resolve_status(row):
    """
    Ưu tiên prediction_label.
    Nếu nhãn thiếu, thử ánh xạ từ prediction.

    Quy ước đang sử dụng:
        0 = NORMAL
        1 = FIRE_RISK
        2 = FIRE
    """

    label = row.get("prediction_label")

    if not is_missing(label):

        normalized = str(label).strip().upper()

        if normalized in (
            "NORMAL",
            "FIRE_RISK",
            "FIRE"
        ):

            return normalized

    # Fallback nếu prediction_label bị thiếu
    prediction = safe_float(
        row.get("prediction")
    )

    if prediction is not None:

        prediction_int = int(prediction)

        mapping = {
            0: "NORMAL",
            1: "FIRE_RISK",
            2: "FIRE"
        }

        return mapping.get(
            prediction_int,
            "UNKNOWN"
        )

    return "UNKNOWN"


# ============================================================
# Probability formatting
# ============================================================

def format_probability(value):
    """
    Nếu giá trị thuộc khoảng 0..1 thì chuyển thành %.
    Nếu đã là phần trăm thì giữ nguyên.
    """

    number = safe_float(value)

    if number is None:
        return "N/A"

    if 0 <= number <= 1:
        number *= 100

    return f"{number:.1f}%"


# ============================================================
# Send one Telegram message
# ============================================================

def send_message(text):
    """
    Gửi một tin nhắn Telegram.

    Trả về:
        True  nếu Telegram xác nhận gửi thành công
        False nếu gửi thất bại
    """

    if not TELEGRAM_BOT_TOKEN:

        print(
            "Telegram lỗi: "
            "TELEGRAM_BOT_TOKEN chưa được thiết lập"
        )

        return False

    if not TELEGRAM_CHAT_ID:

        print(
            "Telegram lỗi: "
            "TELEGRAM_CHAT_ID chưa được thiết lập"
        )

        return False

    url = (
        "https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    for attempt in range(1, 3):

        try:

            response = requests.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text
                },
                timeout=REQUEST_TIMEOUT
            )

            try:

                payload = response.json()

            except ValueError:

                payload = {}

            # HTTP thành công và Telegram API xác nhận ok=True
            if response.ok and payload.get("ok") is True:

                print(
                    "Telegram: gửi cảnh báo thành công"
                )

                return True

            description = payload.get(
                "description",
                response.text
            )

            print(
                f"Telegram lỗi: HTTP {response.status_code}; "
                f"API: {description}"
            )

            # Lỗi thường không thể khắc phục bằng retry
            if response.status_code in (
                400,
                401,
                403,
                404
            ):

                return False

        except requests.RequestException as exc:

            print(
                f"Telegram lỗi kết nối "
                f"(lần {attempt}/2): {exc}"
            )

        if attempt < 2:
            time.sleep(1)

    return False


# ============================================================
# Split long messages
# ============================================================

def split_message(
    text,
    max_length=MAX_MESSAGE_LENGTH
):
    """
    Chia tin nhắn dài thành các phần nhỏ.
    Có xử lý cả trường hợp một dòng riêng lẻ quá dài.
    """

    if not text:
        return [""]

    max_length = max(
        100,
        int(max_length)
    )

    parts = []
    current = ""

    for original_line in text.splitlines() or [text]:

        # Chia dòng dài thành những đoạn nhỏ
        line_chunks = [
            original_line[i:i + max_length]
            for i in range(
                0,
                len(original_line),
                max_length
            )
        ] or [""]

        for line in line_chunks:

            if current:

                candidate = current + "\n" + line

            else:

                candidate = line

            if len(candidate) <= max_length:

                current = candidate

            else:

                if current:
                    parts.append(current)

                current = line

    if current:
        parts.append(current)

    return parts or [""]


def send_long_message(text):
    """
    Gửi tin nhắn dài thành nhiều phần.

    Trả về True khi tất cả các phần gửi thành công.
    """

    messages = split_message(
        text,
        MAX_MESSAGE_LENGTH - 60
    )

    total = len(messages)
    all_sent = True

    for index, message in enumerate(
        messages,
        start=1
    ):

        if total > 1:

            message = (
                f"📨 CẢNH BÁO PHẦN {index}/{total}\n\n"
                + message
            )

        if not send_message(message):
            all_sent = False

    return all_sent


# ============================================================
# Format sensor
# ============================================================

def format_sensor(row):
    """
    Định dạng thông tin của một sensor.
    """

    sensor_id = row.get(
        "sensor_id",
        "N/A"
    )

    zone = row.get(
        "zone",
        "N/A"
    )

    timestamp = row.get(
        "timestamp",
        "N/A"
    )

    status = resolve_status(row)

    temperature = display_value(
        row.get("temperature"),
        " °C"
    )

    smoke = display_value(
        row.get("smoke_ppm"),
        " ppm"
    )

    lpg = display_value(
        row.get("lpg_gas_ppm"),
        " ppm"
    )

    co = display_value(
        row.get("co_gas_ppm"),
        " ppm"
    )

    probability_fire = format_probability(
        row.get("probability_fire")
    )

    probability_risk = format_probability(
        row.get("probability_risk")
    )

    return (
        f"Sensor: {sensor_id}\n"
        f"Khu vực: {zone}\n"
        f"Thời gian: {timestamp}\n"
        f"Nhiệt độ: {temperature}\n"
        f"Khói: {smoke}\n"
        f"LPG: {lpg}\n"
        f"CO: {co}\n"
        f"Trạng thái: {status}\n"
        f"Xác suất FIRE: {probability_fire}\n"
        f"Xác suất FIRE_RISK: {probability_risk}"
    )


# ============================================================
# Send fire alerts
# ============================================================

def send_telegram_alert(
    fire_rows,
    risk_rows
):
    """
    Gửi cảnh báo FIRE và FIRE_RISK.

    fire_rows:
        Danh sách sensor được dự đoán là FIRE.

    risk_rows:
        Danh sách sensor được dự đoán là FIRE_RISK.
    """

    fire_rows = list(
        fire_rows
        if fire_rows is not None
        else []
    )

    risk_rows = list(
        risk_rows
        if risk_rows is not None
        else []
    )

    all_sent = True

    # ========================================================
    # FIRE
    # ========================================================

    if fire_rows:

        lines = [
            "🚨🚨🚨 CẢNH BÁO CHÁY KHẨN CẤP 🚨🚨🚨",
            "",
            (
                f"Phát hiện {len(fire_rows)} sensor "
                "có trạng thái FIRE."
            ),
            (
                "Hãy kiểm tra và xử lý theo "
                "quy trình an toàn của nhà máy."
            ),
            ""
        ]

        for index, row in enumerate(
            fire_rows,
            start=1
        ):

            lines.append(
                f"🔴 SENSOR FIRE #{index}"
            )

            lines.append(
                format_sensor(row)
            )

            lines.append("")

        text = "\n".join(lines)

        if not send_long_message(text):
            all_sent = False

    # ========================================================
    # FIRE_RISK
    # ========================================================

    if risk_rows:

        lines = [
            "⚠️⚠️⚠️ CẢNH BÁO NGUY CƠ CHÁY ⚠️⚠️⚠️",
            "",
            (
                f"Phát hiện {len(risk_rows)} sensor "
                "có trạng thái FIRE_RISK."
            ),
            (
                "Cần kiểm tra khu vực có dấu hiệu "
                "bất thường."
            ),
            ""
        ]

        for index, row in enumerate(
            risk_rows,
            start=1
        ):

            lines.append(
                f"🟡 SENSOR FIRE_RISK #{index}"
            )

            lines.append(
                format_sensor(row)
            )

            lines.append("")

        text = "\n".join(lines)

        if not send_long_message(text):
            all_sent = False

    return all_sent
