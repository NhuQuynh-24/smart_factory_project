import { NextResponse } from "next/server";

export async function GET() {
  const apiUrl = process.env.SENSORS_API_URL;
  const apiToken = process.env.SENSORS_API_TOKEN;

  if (!apiUrl || !apiToken) {
    console.error(
      "Thiếu SENSORS_API_URL hoặc SENSORS_API_TOKEN"
    );

    return NextResponse.json(
      { error: "Server chưa được cấu hình API cảm biến" },
      { status: 500 }
    );
  }

  try {
    const response = await fetch(apiUrl, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${apiToken}`,
        Accept: "application/json",
      },
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      console.error(
        "Backend cảm biến trả về HTTP:",
        response.status
      );

      return NextResponse.json(
        {
          error: "Không thể lấy dữ liệu cảm biến",
          status: response.status,
        },
        { status: 502 }
      );
    }

    const data = await response.json();

    return NextResponse.json(data, {
      headers: {
        "Cache-Control": "no-store, max-age=0",
      },
    });
  } catch (error) {
    console.error("Lỗi kết nối backend cảm biến:", error);

    const message =
      error instanceof Error
        ? error.message
        : "Lỗi không xác định";

    return NextResponse.json(
      {
        error: "Không thể kết nối backend cảm biến",
        details: message,
      },
      { status: 502 }
    );
  }
}
