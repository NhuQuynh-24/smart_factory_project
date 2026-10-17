import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const apiUrl = process.env.SENSORS_API_URL;
  const apiToken = process.env.SENSORS_API_TOKEN;

  if (!apiUrl || !apiToken) {
    console.error("Thiếu SENSORS_API_URL hoặc SENSORS_API_TOKEN");

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
      },
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      console.error("Backend cảm biến trả về HTTP:", response.status);

      return NextResponse.json(
        { error: "Không thể lấy dữ liệu cảm biến" },
        { status: 502 }
      );
    }

    const data = await response.json();

    return NextResponse.json(data, {
      headers: {
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    console.error("Lỗi kết nối backend cảm biến:", error);

    return NextResponse.json(
      { error: "Không thể kết nối backend cảm biến" },
      { status: 502 }
    );
  }
}
