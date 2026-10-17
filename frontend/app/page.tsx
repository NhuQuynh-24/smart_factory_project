"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type Status = "NORMAL" | "FIRE_RISK" | "FIRE";

type Sensor = {
  id: number;
  sensor_id: string | null;
  zone: string | null;
  timestamp: string | null;
  temperature: number | null;
  humidity: number | null;
  smoke_ppm: number | null;
  lpg_gas_ppm: number | null;
  co_gas_ppm: number | null;
  prediction: number | null;
  prediction_label: string | null;
  probability_normal: number | null;
  probability_risk: number | null;
  probability_fire: number | null;
  created_at: string | null;
};

const statusLabels: Record<Status, string> = {
  NORMAL: "Bình thường",
  FIRE_RISK: "Nguy cơ cháy",
  FIRE: "Phát hiện cháy",
};

const statusStyles: Record<Status, string> = {
  NORMAL: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  FIRE_RISK: "bg-amber-50 text-amber-700 ring-amber-600/20",
  FIRE: "bg-red-50 text-red-700 ring-red-600/20",
};

function getStatus(sensor: Sensor): Status {
  const label = sensor.prediction_label?.toUpperCase();

  if (label === "FIRE") return "FIRE";
  if (label === "FIRE_RISK") return "FIRE_RISK";
  if (label === "NORMAL") return "NORMAL";

  if (sensor.prediction === 2) return "FIRE";
  if (sensor.prediction === 1) return "FIRE_RISK";

  return "NORMAL";
}

function formatNumber(value: number | null, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("vi-VN", {
    maximumFractionDigits: digits,
  });
}

function formatTime(value: string | null) {
  if (!value) return "—";

  const date = new Date(value.replace(" ", "T"));

  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function Home() {
  const [sensors, setSensors] = useState<Sensor[]>([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"ALL" | Status>("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const loadSensors = useCallback(async (firstLoad = false) => {
    if (firstLoad) setLoading(true);

    try {
      const response = await fetch("/api/sensors", {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`API trả về mã lỗi ${response.status}`);
      }

      const data: unknown = await response.json();

      if (!Array.isArray(data)) {
        throw new Error("Dữ liệu API không đúng định dạng");
      }

      setSensors(data as Sensor[]);
      setUpdatedAt(new Date());
      setError("");
    } catch (err) {
      console.error("Không thể tải dữ liệu cảm biến:", err);
      setError(
        err instanceof Error
          ? err.message
          : "Không thể kết nối đến API",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSensors(true);

    const timer = window.setInterval(() => {
      void loadSensors(false);
    }, 5000);

    return () => window.clearInterval(timer);
  }, [loadSensors]);

  const latestSensors = useMemo(() => {
    const latestBySensor = new Map<string, Sensor>();

    for (const sensor of sensors) {
      const key = sensor.sensor_id || `unknown-${sensor.id}`;
      const existing = latestBySensor.get(key);

      if (!existing || sensor.id > existing.id) {
        latestBySensor.set(key, sensor);
      }
    }

    return Array.from(latestBySensor.values()).sort((a, b) =>
      (a.sensor_id || "").localeCompare(b.sensor_id || ""),
    );
  }, [sensors]);

  const counts = useMemo(() => {
    const result = {
      total: latestSensors.length,
      normal: 0,
      risk: 0,
      fire: 0,
    };

    for (const sensor of latestSensors) {
      const status = getStatus(sensor);

      if (status === "NORMAL") result.normal++;
      if (status === "FIRE_RISK") result.risk++;
      if (status === "FIRE") result.fire++;
    }

    return result;
  }, [latestSensors]);

  const filteredSensors = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("vi-VN");

    return latestSensors.filter((sensor) => {
      const matchesSearch =
        (sensor.sensor_id || "").toLocaleLowerCase("vi-VN").includes(query) ||
        (sensor.zone || "").toLocaleLowerCase("vi-VN").includes(query);

      const matchesFilter =
        filter === "ALL" || getStatus(sensor) === filter;

      return matchesSearch && matchesFilter;
    });
  }, [latestSensors, search, filter]);

  const cards = [
    {
      title: "Tổng cảm biến",
      value: counts.total,
      icon: "◉",
      style: "bg-blue-50 text-blue-700",
    },
    {
      title: "Bình thường",
      value: counts.normal,
      icon: "✓",
      style: "bg-emerald-50 text-emerald-700",
    },
    {
      title: "Nguy cơ cháy",
      value: counts.risk,
      icon: "⚠",
      style: "bg-amber-50 text-amber-700",
    },
    {
      title: "Phát hiện cháy",
      value: counts.fire,
      icon: "!",
      style: "bg-red-50 text-red-700",
    },
  ];

  return (
    <main className="min-h-screen bg-slate-100 text-slate-800">
      <div className="flex min-h-screen">
        <aside className="hidden w-60 shrink-0 border-r border-slate-200 bg-white p-6 lg:block">
          <div className="mb-10 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-600 text-xl font-bold text-white">
              S
            </div>

            <div>
              <h1 className="font-bold text-slate-900">Smart Factory</h1>
              <p className="text-xs text-slate-500">Monitoring System</p>
            </div>
          </div>

          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Hệ thống
          </p>

          <div className="rounded-xl bg-blue-50 px-4 py-3 font-semibold text-blue-700">
            ▦ &nbsp; Tổng quan
          </div>

          <div className="mt-2 rounded-xl px-4 py-3 text-slate-600">
            ◉ &nbsp; Cảm biến
          </div>

          <div className="mt-2 rounded-xl px-4 py-3 text-slate-600">
            ⚠ &nbsp; Cảnh báo
          </div>

          <div className="mt-10 border-t border-slate-200 pt-5 text-xs">
            <p className="font-semibold text-slate-700">KẾT NỐI DỮ LIỆU</p>

            <p className={`mt-2 ${error ? "text-red-600" : "text-emerald-600"}`}>
              ● {error ? "Có lỗi kết nối" : "Đang nhận dữ liệu API"}
            </p>

            <p className="mt-2 text-slate-500">
              Tự động cập nhật mỗi 5 giây
            </p>
          </div>
        </aside>

        <section className="min-w-0 flex-1">
          <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-white px-5 py-5 md:px-8">
            <div>
              <h2 className="text-2xl font-bold text-slate-900">
                Tổng quan nhà máy
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                Giám sát nhiệt độ, khí và cảnh báo cháy theo dữ liệu thực tế
              </p>
            </div>

            <div className="flex flex-col items-start gap-1 sm:items-end">
              <span
                className={`rounded-full px-4 py-2 text-sm font-medium ${
                  error
                    ? "bg-red-50 text-red-700"
                    : "bg-emerald-50 text-emerald-700"
                }`}
              >
                ● {error ? "Lỗi kết nối" : "API đang hoạt động"}
              </span>

              <span className="text-xs text-slate-500">
                Cập nhật:{" "}
                {updatedAt
                  ? updatedAt.toLocaleTimeString("vi-VN")
                  : "Chưa có dữ liệu"}
              </span>
            </div>
          </header>

          <div className="space-y-6 p-5 md:p-8">
            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                <p className="font-semibold">Không thể tải dữ liệu cảm biến</p>
                <p className="mt-1">{error}</p>
                <p className="mt-2">
                  Kiểm tra API tại /api/sensors và kết nối MariaDB.
                </p>
              </div>
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {cards.map((card) => (
                <div
                  key={card.title}
                  className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-slate-500">{card.title}</p>

                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-xl text-lg font-bold ${card.style}`}
                    >
                      {card.icon}
                    </div>
                  </div>

                  <p className="mt-4 text-3xl font-bold text-slate-900">
                    {loading ? "…" : card.value}
                  </p>

                  <p className="mt-2 text-xs text-slate-500">
                    {card.title === "Tổng cảm biến"
                      ? "Số cảm biến có dữ liệu"
                      : "Theo bản ghi mới nhất của mỗi cảm biến"}
                  </p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm xl:col-span-2">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="font-bold text-slate-900">
                      Tình trạng cảm biến
                    </h3>
                    <p className="mt-1 text-sm text-slate-500">
                      Phân loại theo kết quả dự đoán mới nhất
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={() => void loadSensors(false)}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    ↻ Làm mới
                  </button>
                </div>

                <div className="mt-6 space-y-5">
                  {(
                    [
                      ["Bình thường", counts.normal, "bg-emerald-500"],
                      ["Nguy cơ cháy", counts.risk, "bg-amber-500"],
                      ["Phát hiện cháy", counts.fire, "bg-red-500"],
                    ] as const
                  ).map(([label, value, color]) => {
                    const percent =
                      counts.total > 0 ? (value / counts.total) * 100 : 0;

                    return (
                      <div key={label}>
                        <div className="mb-2 flex justify-between text-sm">
                          <span className="text-slate-600">{label}</span>
                          <span className="font-semibold text-slate-900">
                            {value} ({percent.toFixed(1)}%)
                          </span>
                        </div>

                        <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className={`h-full rounded-full ${color}`}
                            style={{ width: `${percent}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>

                <p className="mt-6 text-xs text-slate-400">
                  Tỷ lệ được tính từ số cảm biến có bản ghi mới nhất, không phải
                  tổng số bản ghi trong cơ sở dữ liệu.
                </p>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h3 className="font-bold text-slate-900">Nhiệt độ cao nhất</h3>

                <p className="mt-1 text-sm text-slate-500">
                  Trong dữ liệu cảm biến mới nhất
                </p>

                {(() => {
                  const hottest = latestSensors
                    .filter((sensor) => sensor.temperature !== null)
                    .sort(
                      (a, b) =>
                        Number(b.temperature) - Number(a.temperature),
                    )[0];

                  return hottest ? (
                    <div className="mt-6">
                      <p className="text-4xl font-bold text-slate-900">
                        {formatNumber(hottest.temperature)}°C
                      </p>

                      <p className="mt-2 font-medium text-slate-700">
                        {hottest.sensor_id || "Không rõ mã cảm biến"}
                      </p>

                      <p className="mt-1 text-sm text-slate-500">
                        {hottest.zone || "Chưa xác định khu vực"}
                      </p>

                      <span
                        className={`mt-4 inline-flex rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset ${
                          statusStyles[getStatus(hottest)]
                        }`}
                      >
                        {statusLabels[getStatus(hottest)]}
                      </span>
                    </div>
                  ) : (
                    <p className="mt-6 text-sm text-slate-400">
                      Chưa có dữ liệu nhiệt độ
                    </p>
                  );
                })()}
              </div>
            </div>

            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 p-5 md:p-6">
                <div>
                  <h3 className="font-bold text-slate-900">
                    Danh sách cảm biến
                  </h3>

                  <p className="mt-1 text-sm text-slate-500">
                    Hiển thị trạng thái mới nhất của từng cảm biến
                  </p>
                </div>

                <span className="rounded-full bg-slate-100 px-3 py-1.5 text-sm text-slate-600">
                  {filteredSensors.length} cảm biến
                </span>
              </div>

              <div className="grid grid-cols-1 gap-3 p-5 md:grid-cols-2">
                <input
                  type="text"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Tìm mã cảm biến hoặc khu vực..."
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />

                <select
                  value={filter}
                  onChange={(event) =>
                    setFilter(event.target.value as "ALL" | Status)
                  }
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-blue-500"
                >
                  <option value="ALL">Tất cả trạng thái</option>
                  <option value="NORMAL">Bình thường</option>
                  <option value="FIRE_RISK">Nguy cơ cháy</option>
                  <option value="FIRE">Phát hiện cháy</option>
                </select>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[1000px] text-left text-sm">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-5 py-4 font-semibold">Cảm biến</th>
                      <th className="px-5 py-4 font-semibold">Khu vực</th>
                      <th className="px-5 py-4 font-semibold">Nhiệt độ</th>
                      <th className="px-5 py-4 font-semibold">Độ ẩm</th>
                      <th className="px-5 py-4 font-semibold">Khói</th>
                      <th className="px-5 py-4 font-semibold">LPG</th>
                      <th className="px-5 py-4 font-semibold">CO</th>
                      <th className="px-5 py-4 font-semibold">Trạng thái</th>
                      <th className="px-5 py-4 font-semibold">Thời gian</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-slate-100">
                    {loading && sensors.length === 0 ? (
                      <tr>
                        <td
                          colSpan={9}
                          className="px-5 py-12 text-center text-slate-500"
                        >
                          Đang tải dữ liệu cảm biến...
                        </td>
                      </tr>
                    ) : filteredSensors.length === 0 ? (
                      <tr>
                        <td
                          colSpan={9}
                          className="px-5 py-12 text-center text-slate-500"
                        >
                          {error
                            ? "Chưa thể tải dữ liệu. Hãy kiểm tra kết nối API."
                            : "Không tìm thấy cảm biến phù hợp."}
                        </td>
                      </tr>
                    ) : (
                      filteredSensors.map((sensor) => {
                        const status = getStatus(sensor);

                        return (
                          <tr
                            key={sensor.sensor_id || sensor.id}
                            className="transition hover:bg-slate-50"
                          >
                            <td className="px-5 py-4 font-semibold text-slate-900">
                              {sensor.sensor_id || "—"}
                            </td>

                            <td className="px-5 py-4 text-slate-600">
                              {(sensor.zone || "—").replaceAll("_", " ")}
                            </td>

                            <td className="px-5 py-4 font-medium">
                              {formatNumber(sensor.temperature)}°C
                            </td>

                            <td className="px-5 py-4">
                              {formatNumber(sensor.humidity)}%
                            </td>

                            <td className="px-5 py-4">
                              {formatNumber(sensor.smoke_ppm)}
                            </td>

                            <td className="px-5 py-4">
                              {formatNumber(sensor.lpg_gas_ppm)}
                            </td>

                            <td className="px-5 py-4">
                              {formatNumber(sensor.co_gas_ppm)}
                            </td>

                            <td className="px-5 py-4">
                              <span
                                className={`inline-flex whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium ring-1 ring-inset ${statusStyles[status]}`}
                              >
                                {statusLabels[status]}
                              </span>
                            </td>

                            <td className="whitespace-nowrap px-5 py-4 text-slate-500">
                              {formatTime(sensor.timestamp)}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              <div className="border-t border-slate-200 px-5 py-4 text-xs text-slate-500">
                Dữ liệu được đọc từ API của Smart Factory. Giao diện tự tải lại
                sau mỗi 5 giây.
              </div>
            </div>

            <footer className="pb-4 text-center text-xs text-slate-400">
              Smart Factory Monitoring System · Dự án cảnh báo cháy nhà máy
            </footer>
          </div>
        </section>
      </div>
    </main>
  );
}
