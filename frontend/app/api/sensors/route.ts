import { NextResponse } from "next/server";
import mysql from "mysql2/promise";


const pool = mysql.createPool({
  host: process.env.MARIADB_HOST || "127.0.0.1",
  port: Number(process.env.MARIADB_PORT || 3306),
  user: process.env.MARIADB_USER || "smart_factory_app",
  password: process.env.MARIADB_PASSWORD,
  database: process.env.MARIADB_DATABASE || "smart_factory",
  waitForConnections: true,
  connectionLimit: 5,
  queueLimit: 0,
});

export async function GET() {
  try {
    const [rows] = await pool.execute(
      `SELECT
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
      LIMIT 100`
    );

    return NextResponse.json(rows);
  } catch (error) {
    console.error("Lỗi truy vấn MariaDB:", error);

    return NextResponse.json(
      { error: "Không thể lấy dữ liệu cảm biến" },
      { status: 500 }
    );
  }
}
