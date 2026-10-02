import os
import requests


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_message(message):
    if not TELEGRAM_BOT_TOKEN:
        print("Thiếu TELEGRAM_BOT_TOKEN")
        return

    if not TELEGRAM_CHAT_ID:
        print("Thiếu TELEGRAM_CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(
            url,
            data=data,
            timeout=10
        )

        if response.ok:
            print("Telegram: đã gửi cảnh báo.")
        else:
            print(
                f"Telegram lỗi: "
                f"{response.status_code} - "
                f"{response.text}"
            )

    except Exception as e:
        print(f"Telegram exception: {e}")


def format_fire_alert(row):
    return (
        f"🔥 CẢNH BÁO CHÁY KHẨN CẤP 🔥\n\n"
        f"Sensor: {row['sensor_id']}\n"
        f"Khu vực: {row['zone']}\n"
        f"Thời gian: {row['timestamp']}\n\n"
        f"Nhiệt độ: {row['temperature']:.2f} °C\n"
        f"Khói: {row['smoke_ppm']:.2f} ppm\n"
        f"LPG: {row['lpg_gas_ppm']:.2f} ppm\n"
        f"CO: {row['co_gas_ppm']:.2f} ppm\n"
        f"Trạng thái: FIRE\n"
        f"Xác suất FIRE: {row['probability_fire'] * 100:.2f}%"
    )


def format_risk_alert(row):
    return (
        f"⚠️ CẢNH BÁO NGUY CƠ CHÁY ⚠️\n\n"
        f"Sensor: {row['sensor_id']}\n"
        f"Khu vực: {row['zone']}\n"
        f"Thời gian: {row['timestamp']}\n\n"
        f"Nhiệt độ: {row['temperature']:.2f} °C\n"
        f"Khói: {row['smoke_ppm']:.2f} ppm\n"
        f"LPG: {row['lpg_gas_ppm']:.2f} ppm\n"
        f"CO: {row['co_gas_ppm']:.2f} ppm\n"
        f"Trạng thái: FIRE_RISK\n"
        f"Xác suất FIRE_RISK: {row['probability_risk'] * 100:.2f}%"
    )


def send_telegram_alert(fire_rows, risk_rows):

    # ========================================================
    # Có FIRE
    # ========================================================

    if fire_rows:

        sections = []

        for row in fire_rows:
            sections.append(
                format_fire_alert(row)
            )

        # Nếu cùng batch có FIRE_RISK
        for row in risk_rows:
            sections.append(
                format_risk_alert(row)
            )

        message = "\n\n" + ("\n\n" + "=" * 30 + "\n\n").join(sections)

        send_message(message)
        return


    # ========================================================
    # Chỉ FIRE_RISK
    # ========================================================

    if risk_rows:

        sections = []

        for row in risk_rows:
            sections.append(
                format_risk_alert(row)
            )

        message = "\n\n" + ("\n\n" + "=" * 30 + "\n\n").join(sections)

        send_message(message)


if __name__ == "__main__":
    print("telegram_alert.py OK")
