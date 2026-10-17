"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/* =========================================================
   SMART FACTORY
   HỆ THỐNG GIÁM SÁT VÀ CẢNH BÁO NGUY CƠ CHÁY NỔ
   ========================================================= */

type SensorStatus = "NORMAL" | "RISK" | "FIRE" | "UNKNOWN";

type Sensor = {
  id?: number | string;
  sensor_id: string;
  zone?: string;
  area?: string;
  location?: string;
  status?: string;
  prediction?: string;
  predicted_class?: string;
  result?: string;
  label?: string;
  probability_normal?: number | string;
  probability_risk?: number | string;
  probability_fire?: number | string;
  created_at?: string;
  timestamp?: string;
  temperature?: number | string;
  humidity?: number | string;
  smoke?: number | string;
  gas?: number | string;
  [key: string]: unknown;
};

type PageKey =
  | "overview"
  | "sensors"
  | "zones"
  | "alerts"
  | "history"
  | "ai";

type ApiResponse = {
  data?: Sensor[];
  sensors?: Sensor[];
  results?: Sensor[];
  message?: string;
  error?: string;
};

const REFRESH_INTERVAL = 5000;
const SENSOR_STALE_SECONDS = 120;
const TOTAL_SENSORS = 50;

const ZONES: Record<string, string> = {
  Kho_Nguyen_Lieu: "Kho Nguyên Liệu",
  Kho_Vat_Lieu: "Kho Vật Liệu",
  Kho_Hoa_Chat: "Kho Hóa Chất",
  Kho_Thanh_Pham: "Kho Thành Phẩm",
  Kho_Linh_Kien: "Kho Linh Kiện",
  Xuong_San_Xuat: "Xưởng Sản Xuất",
  Khu_Dong_Goi: "Khu Đóng Gói",
  Khu_Kiem_Tra: "Khu Kiểm Tra",
  Phong_May: "Phòng Máy",
  Khu_Bao_Tri: "Khu Bảo Trì",
};

const NAV_ITEMS: {
  key: PageKey;
  label: string;
  icon: string;
  section?: string;
}[] = [
  { key: "overview", label: "Tổng quan", icon: "◫", section: "GIÁM SÁT" },
  { key: "sensors", label: "Giám sát cảm biến", icon: "⌁" },
  { key: "zones", label: "Khu vực nhà máy", icon: "▦" },
  { key: "alerts", label: "Cảnh báo", icon: "⚠" },
  { key: "history", label: "Dữ liệu nhận được", icon: "▤", section: "DỮ LIỆU" },
  { key: "ai", label: "Phân tích AI", icon: "✳" },
];

/* =========================
   HÀM XỬ LÝ DỮ LIỆU
   ========================= */

function asNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function getSensorId(sensor: Sensor): string {
  return String(
    sensor.sensor_id ??
      sensor.id ??
      "UNKNOWN"
  );
}

function getZone(sensor: Sensor): string {
  const value = String(
    sensor.zone ??
      sensor.area ??
      sensor.location ??
      "Chưa xác định"
  );

  return ZONES[value] ?? value.replaceAll("_", " ");
}

function getTimestamp(sensor: Sensor): string | null {
  const value = sensor.created_at ?? sensor.timestamp;

  if (value === null || value === undefined || value === "") {
    return null;
  }

  return String(value);
}

function getTimeMs(sensor: Sensor): number | null {
  const timestamp = getTimestamp(sensor);

  if (!timestamp) return null;

  const parsed = new Date(timestamp).getTime();

  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeStatus(value: unknown): SensorStatus {
  const text = String(value ?? "")
    .trim()
    .toUpperCase()
    .replaceAll("-", "_")
    .replaceAll(" ", "_");

  if (
    [
      "FIRE",
      "FIRE_DETECTED",
      "FIRE_ALERT",
      "CHAY",
      "CHÁY",
      "DANGER_FIRE",
      "2",
    ].includes(text)
  ) {
    return "FIRE";
  }

  if (
    [
      "RISK",
      "FIRE_RISK",
      "WARNING",
      "WARN",
      "DANGER",
      "CANH_BAO",
      "CẢNH_BÁO",
      "1",
    ].includes(text)
  ) {
    return "RISK";
  }

  if (
    [
      "NORMAL",
      "SAFE",
      "OK",
      "AN_TOAN",
      "AN_TOÀN",
      "0",
    ].includes(text)
  ) {
    return "NORMAL";
  }

  return "UNKNOWN";
}

function getStatus(sensor: Sensor): SensorStatus {
  const value =
    sensor.status ??
    sensor.prediction ??
    sensor.predicted_class ??
    sensor.result ??
    sensor.label;

  return normalizeStatus(value);
}

function getStatusLabel(status: SensorStatus): string {
  switch (status) {
    case "NORMAL":
      return "An toàn";
    case "RISK":
      return "Nguy cơ";
    case "FIRE":
      return "Phát hiện cháy";
    default:
      return "Chưa xác định";
  }
}

function getFreshness(
  sensor: Sensor,
  now: number
): "ONLINE" | "OFFLINE" | "UNKNOWN" {
  const timestamp = getTimeMs(sensor);

  if (timestamp === null || now === 0) {
    return "UNKNOWN";
  }

  const age = (now - timestamp) / 1000;

  if (age >= -60 && age <= SENSOR_STALE_SECONDS) {
    return "ONLINE";
  }

  return "OFFLINE";
}

function formatDate(value: string | null): string {
  if (!value) return "Chưa có dữ liệu";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatTime(value: string | null): string {
  if (!value) return "--:--:--";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatNumber(value: unknown, digits = 1): string {
  const number = asNumber(value);

  if (number === null) return "--";

  return number.toLocaleString("vi-VN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  });
}

function formatProbability(value: unknown): number | null {
  const number = asNumber(value);

  if (number === null) return null;

  // Giả định xác suất trong cơ sở dữ liệu nằm trong khoảng 0–1.
  // Nếu dữ liệu của m đã ở thang 0–100, đổi thành:
  // return Math.max(0, Math.min(100, number));

  return Math.max(0, Math.min(100, number * 100));
}

function getProbability(
  sensor: Sensor,
  key: "normal" | "risk" | "fire"
): number | null {
  const field = {
    normal: "probability_normal",
    risk: "probability_risk",
    fire: "probability_fire",
  }[key];

  return formatProbability(sensor[field]);
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;

  return "Đã xảy ra lỗi không xác định.";
}

/* =========================
   COMPONENT GIAO DIỆN
   ========================= */

function StatusBadge({ status }: { status: SensorStatus }) {
  const classes: Record<SensorStatus, string> = {
    NORMAL: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    RISK: "bg-amber-50 text-amber-700 ring-amber-200",
    FIRE: "bg-red-50 text-red-700 ring-red-200",
    UNKNOWN: "bg-slate-100 text-slate-600 ring-slate-200",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${classes[status]}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          status === "NORMAL"
            ? "bg-emerald-500"
            : status === "RISK"
              ? "bg-amber-500"
              : status === "FIRE"
                ? "bg-red-500"
                : "bg-slate-400"
        }`}
      />
      {getStatusLabel(status)}
    </span>
  );
}

function ConnectionBadge({
  status,
}: {
  status: "ONLINE" | "OFFLINE" | "UNKNOWN";
}) {
  const classes = {
    ONLINE: "bg-emerald-50 text-emerald-700",
    OFFLINE: "bg-slate-100 text-slate-500",
    UNKNOWN: "bg-amber-50 text-amber-700",
  };

  const labels = {
    ONLINE: "Đang hoạt động",
    OFFLINE: "Mất kết nối",
    UNKNOWN: "Chưa xác định",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium ${classes[status]}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          status === "ONLINE"
            ? "bg-emerald-500"
            : status === "OFFLINE"
              ? "bg-slate-400"
              : "bg-amber-500"
        }`}
      />
      {labels[status]}
    </span>
  );
}

function MetricCard({
  title,
  value,
  description,
  icon,
  accent,
}: {
  title: string;
  value: string | number;
  description: string;
  icon: string;
  accent: "blue" | "green" | "amber" | "red";
}) {
  const accents = {
    blue: "bg-blue-50 text-blue-700",
    green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    red: "bg-red-50 text-red-700",
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-500">{title}</p>
          <p className="mt-3 text-3xl font-bold tracking-tight text-slate-900">
            {value}
          </p>
        </div>

        <div
          className={`flex h-11 w-11 items-center justify-center rounded-xl text-xl ${accents[accent]}`}
        >
          {icon}
        </div>
      </div>

      <p className="mt-4 text-xs text-slate-500">{description}</p>
    </div>
  );
}

function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-600">
          {eyebrow}
        </p>
        <h2 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">
          {title}
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          {description}
        </p>
      </div>

      {action}
    </div>
  );
}

function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 px-5 py-10 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-200 text-xl text-slate-600">
        ▤
      </div>
      <h3 className="mt-4 font-semibold text-slate-800">{title}</h3>
      <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
        {description}
      </p>
    </div>
  );
}

/* =========================
   BẢNG CẢM BIẾN
   ========================= */

function SensorTable({
  sensors,
  now,
  compact = false,
}: {
  sensors: Sensor[];
  now: number;
  compact?: boolean;
}) {
  if (sensors.length === 0) {
    return (
      <EmptyState
        title="Chưa có dữ liệu cảm biến"
        description="Hệ thống chưa nhận được bản ghi phù hợp. Kiểm tra API và kết nối backend cảm biến."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <th className="px-5 py-4 font-semibold">Mã cảm biến</th>
            <th className="px-5 py-4 font-semibold">Khu vực</th>
            <th className="px-5 py-4 font-semibold">Trạng thái</th>
            <th className="px-5 py-4 font-semibold">Kết nối</th>
            <th className="px-5 py-4 font-semibold">Nhiệt độ</th>
            <th className="px-5 py-4 font-semibold">Thời gian cập nhật</th>
          </tr>
        </thead>

        <tbody className="divide-y divide-slate-100">
          {sensors.slice(0, compact ? 6 : undefined).map((sensor, index) => {
            const status = getStatus(sensor);
            const freshness = getFreshness(sensor, now);
            const temperature = sensor.temperature;

            return (
              <tr
                key={`${getSensorId(sensor)}-${getTimestamp(sensor) ?? index}-${index}`}
                className="transition hover:bg-slate-50"
              >
                <td className="whitespace-nowrap px-5 py-4 font-semibold text-slate-800">
                  {getSensorId(sensor)}
                </td>

                <td className="px-5 py-4 text-slate-600">
                  {getZone(sensor)}
                </td>

                <td className="px-5 py-4">
                  <StatusBadge status={status} />
                </td>

                <td className="px-5 py-4">
                  <ConnectionBadge status={freshness} />
                </td>

                <td className="px-5 py-4 text-slate-600">
                  {formatNumber(temperature)} °C
                </td>

                <td className="whitespace-nowrap px-5 py-4 text-slate-500">
                  {formatTime(getTimestamp(sensor))}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* =========================
   TRANG CHÍNH
   ========================= */

export default function Home() {
  const [page, setPage] = useState<PageKey>("overview");
  const [sensors, setSensors] = useState<Sensor[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [now, setNow] = useState(0);
  const [lastSuccessfulUpdate, setLastSuccessfulUpdate] = useState<number | null>(
    null
  );
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [zoneFilter, setZoneFilter] = useState("ALL");

  const loadSensors = useCallback(async (initial = false) => {
    if (initial) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }

    try {
      const response = await fetch("/api/sensors", {
        method: "GET",
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(
          `API trả về mã lỗi ${response.status}. Kiểm tra API và kết nối backend cảm biến.`
        );
      }

      const payload: unknown = await response.json();

      let records: Sensor[] = [];

      if (Array.isArray(payload)) {
        records = payload as Sensor[];
      } else if (payload && typeof payload === "object") {
        const result = payload as ApiResponse;

        if (Array.isArray(result.data)) {
          records = result.data;
        } else if (Array.isArray(result.sensors)) {
          records = result.sensors;
        } else if (Array.isArray(result.results)) {
          records = result.results;
        } else if (result.error) {
          throw new Error(result.error);
        }
      }

      setSensors(records);
      setError("");
      setLastSuccessfulUpdate(Date.now());
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  /*
   * QUAN TRỌNG:
   * Không khởi tạo now bằng Date.now() trực tiếp trong useState.
   * Giá trị ban đầu là 0 để tránh lỗi prerender/hydration.
   */
  useEffect(() => {
    setNow(Date.now());

    void loadSensors(true);

    const refreshTimer = window.setInterval(() => {
      void loadSensors(false);
    }, REFRESH_INTERVAL);

    const clockTimer = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => {
      window.clearInterval(refreshTimer);
      window.clearInterval(clockTimer);
    };
  }, [loadSensors]);

  /* Bản ghi mới nhất của từng cảm biến */
  const latestSensors = useMemo(() => {
    const latest = new Map<string, Sensor>();

    const sorted = [...sensors].sort((a, b) => {
      const aTime = getTimeMs(a) ?? 0;
      const bTime = getTimeMs(b) ?? 0;

      if (aTime !== bTime) return bTime - aTime;

      const aId = asNumber(a.id) ?? 0;
      const bId = asNumber(b.id) ?? 0;

      return bId - aId;
    });

    for (const sensor of sorted) {
      const id = getSensorId(sensor);

      if (!latest.has(id)) {
        latest.set(id, sensor);
      }
    }

    return Array.from(latest.values());
  }, [sensors]);

  const onlineSensors = useMemo(
    () =>
      latestSensors.filter(
        (sensor) => getFreshness(sensor, now) === "ONLINE"
      ),
    [latestSensors, now]
  );

  const offlineSensors = useMemo(
    () =>
      latestSensors.filter(
        (sensor) => getFreshness(sensor, now) === "OFFLINE"
      ),
    [latestSensors, now]
  );

  const unknownConnectionSensors = useMemo(
    () =>
      latestSensors.filter(
        (sensor) => getFreshness(sensor, now) === "UNKNOWN"
      ),
    [latestSensors, now]
  );

  const normalSensors = useMemo(
    () =>
      onlineSensors.filter((sensor) => getStatus(sensor) === "NORMAL"),
    [onlineSensors]
  );

  const riskSensors = useMemo(
    () => latestSensors.filter((sensor) => getStatus(sensor) === "RISK"),
    [latestSensors]
  );

  const fireSensors = useMemo(
    () => latestSensors.filter((sensor) => getStatus(sensor) === "FIRE"),
    [latestSensors]
  );

  const alertSensors = useMemo(
    () =>
      latestSensors.filter((sensor) => {
        const status = getStatus(sensor);

        return status === "FIRE" || status === "RISK";
      }),
    [latestSensors]
  );

  const filteredSensors = useMemo(() => {
    const keyword = search.trim().toLowerCase();

    return sensors.filter((sensor) => {
      const status = getStatus(sensor);
      const zone = getZone(sensor);

      const matchesSearch =
        keyword === "" ||
        getSensorId(sensor).toLowerCase().includes(keyword) ||
        zone.toLowerCase().includes(keyword);

      const matchesStatus =
        statusFilter === "ALL" || status === statusFilter;

      const matchesZone =
        zoneFilter === "ALL" || zone === zoneFilter;

      return matchesSearch && matchesStatus && matchesZone;
    });
  }, [sensors, search, statusFilter, zoneFilter]);

  const uniqueZones = useMemo(
    () => Array.from(new Set(latestSensors.map(getZone))).sort(),
    [latestSensors]
  );

  const zoneSummaries = useMemo(() => {
    return Object.entries(ZONES).map(([key, label]) => {
      const items = latestSensors.filter((sensor) => {
        const rawZone = String(
          sensor.zone ?? sensor.area ?? sensor.location ?? ""
        );

        return rawZone === key || getZone(sensor) === label;
      });

      const online = items.filter(
        (sensor) => getFreshness(sensor, now) === "ONLINE"
      ).length;

      const fires = items.filter(
        (sensor) => getStatus(sensor) === "FIRE"
      ).length;

      const risks = items.filter(
        (sensor) => getStatus(sensor) === "RISK"
      ).length;

      return {
        key,
        label,
        count: items.length,
        online,
        fires,
        risks,
      };
    });
  }, [latestSensors, now]);

  const probabilityAverages = useMemo(() => {
    const online = onlineSensors;

    const average = (
      key: "normal" | "risk" | "fire"
    ): number | null => {
      const values = online
        .map((sensor) => getProbability(sensor, key))
        .filter((value): value is number => value !== null);

      if (values.length === 0) return null;

      return (
        values.reduce((total, value) => total + value, 0) / values.length
      );
    };

    return {
      normal: average("normal"),
      risk: average("risk"),
      fire: average("fire"),
    };
  }, [onlineSensors]);

  const totalKnown = latestSensors.length;
  const notReported = Math.max(0, TOTAL_SENSORS - totalKnown);

  const pageTitles: Record<PageKey, string> = {
    overview: "Tổng quan hệ thống",
    sensors: "Giám sát cảm biến",
    zones: "Khu vực nhà máy",
    alerts: "Trung tâm cảnh báo",
    history: "Dữ liệu nhận được",
    ai: "Phân tích AI",
  };

  const handleNavigate = (key: PageKey) => {
    setPage(key);
    setMobileMenuOpen(false);
  };

  /* =========================
     NỘI DUNG TỪNG TRANG
     ========================= */

  function renderOverview() {
    return (
      <>
        <SectionHeading
          eyebrow="Bảng điều khiển"
          title="Tổng quan hệ thống"
          description="Theo dõi tình trạng cảm biến, mức độ an toàn và các cảnh báo của nhà máy theo thời gian thực."
          action={
            <button
              onClick={() => void loadSensors(false)}
              disabled={refreshing}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span className={refreshing ? "animate-spin" : ""}>↻</span>
              {refreshing ? "Đang cập nhật..." : "Làm mới dữ liệu"}
            </button>
          }
        />

        {error && (
          <div className="mb-6 flex flex-col gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold text-red-800">
                Không thể tải dữ liệu cảm biến
              </p>
              <p className="mt-1 break-words text-sm text-red-700">
                {error}
              </p>
            </div>

            <button
              onClick={() => void loadSensors(false)}
              className="shrink-0 rounded-lg border border-red-200 bg-white px-3 py-2 text-sm font-semibold text-red-700 hover:bg-red-100"
            >
              Thử lại
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            title="Tổng cảm biến đã ghi nhận"
            value={totalKnown}
            description={`Mốc tham chiếu cấu hình: ${TOTAL_SENSORS} cảm biến`}
            icon="⌁"
            accent="blue"
          />

          <MetricCard
            title="Đang hoạt động"
            value={onlineSensors.length}
            description="Có dữ liệu trong vòng 120 giây"
            icon="◉"
            accent="green"
          />

          <MetricCard
            title="Cảnh báo nguy cơ"
            value={riskSensors.length}
            description="Các bản ghi có trạng thái nguy cơ"
            icon="⚠"
            accent="amber"
          />

          <MetricCard
            title="Phát hiện cháy"
            value={fireSensors.length}
            description="Các bản ghi có trạng thái cháy"
            icon="!"
            accent="red"
          />
        </div>

        <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm xl:col-span-2">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="font-bold text-slate-900">
                  Tình trạng cảm biến
                </h3>
                <p className="mt-1 text-sm text-slate-500">
                  Thống kê dựa trên bản ghi mới nhất của mỗi cảm biến.
                </p>
              </div>

              <button
                onClick={() => handleNavigate("sensors")}
                className="whitespace-nowrap text-sm font-semibold text-blue-600 hover:text-blue-800"
              >
                Xem chi tiết →
              </button>
            </div>

            <div className="mt-6 space-y-5">
              {[
                {
                  label: "An toàn và đang hoạt động",
                  count: normalSensors.length,
                  color: "bg-emerald-500",
                  total: Math.max(totalKnown, 1),
                },
                {
                  label: "Nguy cơ",
                  count: riskSensors.length,
                  color: "bg-amber-500",
                  total: Math.max(totalKnown, 1),
                },
                {
                  label: "Phát hiện cháy",
                  count: fireSensors.length,
                  color: "bg-red-500",
                  total: Math.max(totalKnown, 1),
                },
                {
                  label: "Mất kết nối",
                  count: offlineSensors.length,
                  color: "bg-slate-400",
                  total: Math.max(totalKnown, 1),
                },
              ].map((item) => (
                <div key={item.label}>
                  <div className="mb-2 flex items-center justify-between gap-3 text-sm">
                    <span className="text-slate-600">{item.label}</span>
                    <span className="font-bold text-slate-800">
                      {item.count}
                    </span>
                  </div>

                  <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className={`h-full rounded-full transition-all ${item.color}`}
                      style={{
                        width: `${Math.min(
                          100,
                          (item.count / item.total) * 100
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-6 grid grid-cols-2 gap-3 border-t border-slate-100 pt-5">
              <div className="rounded-xl bg-slate-50 p-4">
                <p className="text-xs text-slate-500">
                  Chưa xác định kết nối
                </p>
                <p className="mt-2 text-2xl font-bold text-slate-800">
                  {unknownConnectionSensors.length}
                </p>
              </div>

              <div className="rounded-xl bg-slate-50 p-4">
                <p className="text-xs text-slate-500">
                  Chưa có bản ghi tương ứng
                </p>
                <p className="mt-2 text-2xl font-bold text-slate-800">
                  {notReported}
                </p>
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-900">
                Trung tâm cảnh báo
              </h3>

              <span className="rounded-full bg-red-50 px-2.5 py-1 text-xs font-bold text-red-700">
                {alertSensors.length} cảnh báo
              </span>
            </div>

            <p className="mt-1 text-sm text-slate-500">
              Các cảm biến có trạng thái nguy cơ hoặc cháy.
            </p>

            <div className="mt-4 space-y-3">
              {alertSensors.slice(0, 5).map((sensor, index) => {
                const status = getStatus(sensor);

                return (
                  <div
                    key={`${getSensorId(sensor)}-${index}`}
                    className="flex items-start gap-3 rounded-xl border border-slate-100 p-3"
                  >
                    <div
                      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                        status === "FIRE"
                          ? "bg-red-100 text-red-700"
                          : "bg-amber-100 text-amber-700"
                      }`}
                    >
                      {status === "FIRE" ? "!" : "⚠"}
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-slate-800">
                        {getSensorId(sensor)}
                      </p>
                      <p className="mt-1 truncate text-xs text-slate-500">
                        {getZone(sensor)}
                      </p>
                      <div className="mt-2">
                        <StatusBadge status={status} />
                      </div>
                    </div>
                  </div>
                );
              })}

              {alertSensors.length === 0 && (
                <div className="rounded-xl bg-emerald-50 px-4 py-6 text-center">
                  <div className="text-2xl text-emerald-600">✓</div>
                  <p className="mt-2 font-semibold text-emerald-800">
                    Chưa ghi nhận cảnh báo
                  </p>
                  <p className="mt-1 text-xs leading-5 text-emerald-700">
                    Không có bản ghi mang trạng thái nguy cơ hoặc cháy.
                  </p>
                </div>
              )}
            </div>

            {alertSensors.length > 5 && (
              <button
                onClick={() => handleNavigate("alerts")}
                className="mt-4 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
              >
                Xem tất cả cảnh báo
              </button>
            )}
          </section>
        </div>

        <section className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-col justify-between gap-3 border-b border-slate-100 p-5 sm:flex-row sm:items-center">
            <div>
              <h3 className="font-bold text-slate-900">
                Cảm biến cập nhật gần đây
              </h3>
              <p className="mt-1 text-sm text-slate-500">
                Danh sách bản ghi mới nhất nhận được từ API.
              </p>
            </div>

            <button
              onClick={() => handleNavigate("sensors")}
              className="text-left text-sm font-semibold text-blue-600 hover:text-blue-800 sm:text-right"
            >
              Mở danh sách cảm biến →
            </button>
          </div>

          <SensorTable sensors={latestSensors} now={now} compact />
        </section>

        <div className="mt-6 rounded-2xl border border-blue-100 bg-blue-50/70 p-5">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-100 text-lg text-blue-700">
              i
            </div>
            <div>
              <h3 className="font-semibold text-blue-900">
                Trạng thái kết nối hệ thống
              </h3>

              <p className="mt-1 text-sm leading-6 text-blue-800">
                {lastSuccessfulUpdate
                  ? `Lần tải dữ liệu thành công gần nhất: ${formatDate(
                      new Date(lastSuccessfulUpdate).toISOString()
                    )}. Hệ thống tự động làm mới dữ liệu mỗi 5 giây.`
                  : "Đang chờ lần tải dữ liệu thành công đầu tiên từ API cảm biến."}
              </p>

              {loading && (
                <p className="mt-2 text-xs text-blue-700">
                  Đang tải dữ liệu...
                </p>
              )}
            </div>
          </div>
        </div>
      </>
    );
  }

  function renderSensors() {
    return (
      <>
        <SectionHeading
          eyebrow="Giám sát thời gian thực"
          title="Giám sát cảm biến"
          description="Tìm kiếm, lọc và theo dõi trạng thái mới nhất của các cảm biến."
          action={
            <button
              onClick={() => void loadSensors(false)}
              disabled={refreshing}
              className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-60"
            >
              {refreshing ? "Đang tải..." : "↻ Làm mới"}
            </button>
          }
        />

        {error && (
          <div className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500">Tổng cảm biến</p>
            <p className="mt-2 text-2xl font-bold text-slate-900">
              {totalKnown}
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500">Đang hoạt động</p>
            <p className="mt-2 text-2xl font-bold text-emerald-600">
              {onlineSensors.length}
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500">Mất kết nối</p>
            <p className="mt-2 text-2xl font-bold text-slate-600">
              {offlineSensors.length}
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500">Tổng bản ghi API</p>
            <p className="mt-2 text-2xl font-bold text-blue-600">
              {sensors.length}
            </p>
          </div>
        </div>

        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="grid grid-cols-1 gap-3 border-b border-slate-100 p-5 md:grid-cols-3">
            <div className="md:col-span-1">
              <label
                htmlFor="sensor-search"
                className="mb-2 block text-xs font-semibold text-slate-600"
              >
                Tìm cảm biến
              </label>

              <input
                id="sensor-search"
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Nhập mã cảm biến, khu vực..."
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
              />
            </div>

            <div>
              <label
                htmlFor="status-filter"
                className="mb-2 block text-xs font-semibold text-slate-600"
              >
                Trạng thái
              </label>

              <select
                id="status-filter"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
              >
                <option value="ALL">Tất cả trạng thái</option>
                <option value="NORMAL">An toàn</option>
                <option value="RISK">Nguy cơ</option>
                <option value="FIRE">Phát hiện cháy</option>
                <option value="UNKNOWN">Chưa xác định</option>
              </select>
            </div>

            <div>
              <label
                htmlFor="zone-filter"
                className="mb-2 block text-xs font-semibold text-slate-600"
              >
                Khu vực
              </label>

              <select
                id="zone-filter"
                value={zoneFilter}
                onChange={(event) => setZoneFilter(event.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
              >
                <option value="ALL">Tất cả khu vực</option>
                {uniqueZones.map((zone) => (
                  <option key={zone} value={zone}>
                    {zone}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-3">
            <p className="text-sm text-slate-500">
              Tìm thấy{" "}
              <span className="font-bold text-slate-800">
                {filteredSensors.length}
              </span>{" "}
              bản ghi
            </p>

            <button
              onClick={() => {
                setSearch("");
                setStatusFilter("ALL");
                setZoneFilter("ALL");
              }}
              className="text-xs font-semibold text-blue-600 hover:text-blue-800"
            >
              Xóa bộ lọc
            </button>
          </div>

          <SensorTable sensors={filteredSensors} now={now} />
        </section>
      </>
    );
  }

  function renderZones() {
    return (
      <>
        <SectionHeading
          eyebrow="Bản đồ vận hành"
          title="Khu vực nhà máy"
          description="Tổng hợp dữ liệu cảm biến theo 10 khu vực được cấu hình trong hệ thống."
        />

        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {zoneSummaries.map((zone, index) => {
            const hasFire = zone.fires > 0;
            const hasRisk = zone.risks > 0;

            const borderColor = hasFire
              ? "border-red-200"
              : hasRisk
                ? "border-amber-200"
                : "border-slate-200";

            const iconColor = hasFire
              ? "bg-red-50 text-red-700"
              : hasRisk
                ? "bg-amber-50 text-amber-700"
                : "bg-blue-50 text-blue-700";

            return (
              <div
                key={zone.key}
                className={`rounded-2xl border ${borderColor} bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div
                    className={`flex h-11 w-11 items-center justify-center rounded-xl text-xl ${iconColor}`}
                  >
                    ▦
                  </div>

                  <span className="text-xs font-medium text-slate-400">
                    KHU VỰC {String(index + 1).padStart(2, "0")}
                  </span>
                </div>

                <h3 className="mt-4 font-bold text-slate-900">
                  {zone.label}
                </h3>

                <p className="mt-1 text-sm text-slate-500">
                  {zone.count} cảm biến có bản ghi
                </p>

                <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full rounded-full ${
                      hasFire
                        ? "bg-red-500"
                        : hasRisk
                          ? "bg-amber-500"
                          : "bg-emerald-500"
                    }`}
                    style={{
                      width: `${
                        zone.count > 0
                          ? Math.min(100, (zone.online / zone.count) * 100)
                          : 0
                      }%`,
                    }}
                  />
                </div>

                <div className="mt-4 grid grid-cols-3 gap-2">
                  <div className="rounded-lg bg-emerald-50 p-2">
                    <p className="text-[11px] text-emerald-700">Hoạt động</p>
                    <p className="mt-1 text-lg font-bold text-emerald-800">
                      {zone.online}
                    </p>
                  </div>

                  <div className="rounded-lg bg-amber-50 p-2">
                    <p className="text-[11px] text-amber-700">Nguy cơ</p>
                    <p className="mt-1 text-lg font-bold text-amber-800">
                      {zone.risks}
                    </p>
                  </div>

                  <div className="rounded-lg bg-red-50 p-2">
                    <p className="text-[11px] text-red-700">Cháy</p>
                    <p className="mt-1 text-lg font-bold text-red-800">
                      {zone.fires}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm leading-6 text-blue-800">
          <strong>Lưu ý:</strong> Thống kê khu vực dựa trên tên khu vực trong
          dữ liệu API. Nếu dữ liệu sử dụng tên khác với danh sách cấu hình,
          cảm biến có thể xuất hiện ở mục khu vực chưa xác định hoặc chưa được
          tổng hợp vào khu vực tương ứng.
        </div>
      </>
    );
  }

  function renderAlerts() {
    return (
      <>
        <SectionHeading
          eyebrow="An toàn nhà máy"
          title="Trung tâm cảnh báo"
          description="Theo dõi các bản ghi có trạng thái nguy cơ và phát hiện cháy."
          action={
            <button
              onClick={() => void loadSensors(false)}
              disabled={refreshing}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              ↻ Cập nhật
            </button>
          }
        />

        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <MetricCard
            title="Tổng cảnh báo"
            value={alertSensors.length}
            description="Bản ghi nguy cơ và phát hiện cháy"
            icon="⚠"
            accent="amber"
          />

          <MetricCard
            title="Nguy cơ cháy"
            value={riskSensors.length}
            description="Cần kiểm tra tình trạng khu vực"
            icon="!"
            accent="amber"
          />

          <MetricCard
            title="Phát hiện cháy"
            value={fireSensors.length}
            description="Ưu tiên xác minh và xử lý an toàn"
            icon="!"
            accent="red"
          />
        </div>

        {alertSensors.length > 0 ? (
          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 p-5">
              <h3 className="font-bold text-slate-900">
                Danh sách bản ghi cảnh báo
              </h3>
              <p className="mt-1 text-sm text-slate-500">
                Các bản ghi được lấy từ dữ liệu API hiện có.
              </p>
            </div>

            <div className="divide-y divide-slate-100">
              {alertSensors.map((sensor, index) => {
                const status = getStatus(sensor);
                const freshness = getFreshness(sensor, now);

                return (
                  <div
                    key={`${getSensorId(sensor)}-${getTimestamp(sensor) ?? index}-${index}`}
                    className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-lg ${
                          status === "FIRE"
                            ? "bg-red-100 text-red-700"
                            : "bg-amber-100 text-amber-700"
                        }`}
                      >
                        ⚠
                      </div>

                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h4 className="font-bold text-slate-900">
                            {getSensorId(sensor)}
                          </h4>
                          <StatusBadge status={status} />
                        </div>

                        <p className="mt-1 text-sm text-slate-500">
                          Khu vực: {getZone(sensor)}
                        </p>

                        <p className="mt-1 text-xs text-slate-400">
                          Thời gian ghi nhận:{" "}
                          {formatDate(getTimestamp(sensor))}
                        </p>
                      </div>
                    </div>

                    <div className="sm:text-right">
                      <ConnectionBadge status={freshness} />
                      <p className="mt-2 text-xs text-slate-500">
                        Nhiệt độ: {formatNumber(sensor.temperature)} °C
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ) : (
          <EmptyState
            title="Chưa ghi nhận cảnh báo"
            description="Không tìm thấy bản ghi có trạng thái nguy cơ hoặc phát hiện cháy trong dữ liệu API hiện tại."
          />
        )}

        <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
          <strong>Lưu ý an toàn:</strong> Đây là giao diện giám sát dựa trên dữ
          liệu được hệ thống cung cấp, không thay thế thiết bị báo cháy chuyên
          dụng hoặc quy trình ứng phó khẩn cấp tại nhà máy. Khi có dấu hiệu
          cháy thực tế, cần tuân thủ quy trình an toàn tại chỗ.
        </div>
      </>
    );
  }

  function renderHistory() {
    const sortedHistory = [...sensors].sort((a, b) => {
      const aTime = getTimeMs(a) ?? 0;
      const bTime = getTimeMs(b) ?? 0;

      if (aTime !== bTime) return bTime - aTime;

      return (asNumber(b.id) ?? 0) - (asNumber(a.id) ?? 0);
    });

    return (
      <>
        <SectionHeading
          eyebrow="Nhật ký hệ thống"
          title="Dữ liệu nhận được"
          description="Xem các bản ghi mà API cảm biến hiện trả về, sắp xếp theo thời gian gần nhất."
          action={
            <button
              onClick={() => void loadSensors(false)}
              disabled={refreshing}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              {refreshing ? "Đang tải..." : "↻ Tải dữ liệu"}
            </button>
          }
        />

        <div className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-sm text-slate-500">Bản ghi đã tải</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">
              {sensors.length}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-sm text-slate-500">Cảm biến riêng biệt</p>
            <p className="mt-2 text-3xl font-bold text-blue-600">
              {latestSensors.length}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <p className="text-sm text-slate-500">Lần tải thành công</p>
            <p className="mt-2 text-sm font-bold text-slate-800">
              {lastSuccessfulUpdate
                ? new Date(lastSuccessfulUpdate).toLocaleTimeString("vi-VN")
                : "Chưa có"}
            </p>
          </div>
        </div>

        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 p-5">
            <h3 className="font-bold text-slate-900">Nhật ký dữ liệu</h3>
            <p className="mt-1 text-sm text-slate-500">
              Hiển thị tối đa 500 bản ghi đầu tiên trong dữ liệu API trả về.
            </p>
          </div>

          <div className="overflow-x-auto">
            {sortedHistory.length === 0 ? (
              <EmptyState
                title="Chưa có dữ liệu"
                description="API chưa trả về bản ghi nào."
              />
            ) : (
              <table className="w-full min-w-[800px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-5 py-4 font-semibold">STT</th>
                    <th className="px-5 py-4 font-semibold">Mã cảm biến</th>
                    <th className="px-5 py-4 font-semibold">Khu vực</th>
                    <th className="px-5 py-4 font-semibold">Trạng thái</th>
                    <th className="px-5 py-4 font-semibold">Nhiệt độ</th>
                    <th className="px-5 py-4 font-semibold">Thời gian</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {sortedHistory.slice(0, 500).map((sensor, index) => (
                    <tr
                      key={`${getSensorId(sensor)}-${getTimestamp(sensor) ?? index}-${index}`}
                      className="hover:bg-slate-50"
                    >
                      <td className="px-5 py-4 text-slate-400">
                        {index + 1}
                      </td>

                      <td className="px-5 py-4 font-semibold text-slate-800">
                        {getSensorId(sensor)}
                      </td>

                      <td className="px-5 py-4 text-slate-600">
                        {getZone(sensor)}
                      </td>

                      <td className="px-5 py-4">
                        <StatusBadge status={getStatus(sensor)} />
                      </td>

                      <td className="px-5 py-4 text-slate-600">
                        {formatNumber(sensor.temperature)} °C
                      </td>

                      <td className="whitespace-nowrap px-5 py-4 text-slate-500">
                        {formatDate(getTimestamp(sensor))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        <p className="mt-4 text-xs leading-5 text-slate-500">
          Lưu ý: giao diện chỉ có thể hiển thị những bản ghi API trả về. Nếu
          backend chỉ truy vấn 100 bản ghi gần nhất thì trang này không thể tự
          lấy toàn bộ lịch sử trong MariaDB.
        </p>
      </>
    );
  }

  function renderAI() {
    const probabilities = [
      {
        label: "An toàn",
        value: probabilityAverages.normal,
        color: "bg-emerald-500",
        text: "text-emerald-700",
      },
      {
        label: "Nguy cơ",
        value: probabilityAverages.risk,
        color: "bg-amber-500",
        text: "text-amber-700",
      },
      {
        label: "Cháy",
        value: probabilityAverages.fire,
        color: "bg-red-500",
        text: "text-red-700",
      },
    ];

    return (
      <>
        <SectionHeading
          eyebrow="Phân tích thông minh"
          title="Phân tích AI"
          description="Tổng hợp các xác suất do mô hình dự đoán trả về trong dữ liệu cảm biến."
          action={
            <button
              onClick={() => void loadSensors(false)}
              disabled={refreshing}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              ↻ Cập nhật
            </button>
          }
        />

        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {probabilities.map((item) => (
            <div
              key={item.label}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <p className="text-sm text-slate-500">
                Xác suất trung bình: {item.label.toLowerCase()}
              </p>

              <p className={`mt-3 text-3xl font-bold ${item.text}`}>
                {item.value === null
                  ? "--"
                  : `${item.value.toLocaleString("vi-VN", {
                      maximumFractionDigits: 1,
                    })}%`}
              </p>

              <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={`h-full rounded-full ${item.color}`}
                  style={{
                    width: `${item.value ?? 0}%`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>

        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 p-5">
            <h3 className="font-bold text-slate-900">
              Kết quả dự đoán theo cảm biến
            </h3>
            <p className="mt-1 text-sm text-slate-500">
              Xác suất được lấy trực tiếp từ các trường dữ liệu do backend
              cung cấp.
            </p>
          </div>

          {onlineSensors.length === 0 ? (
            <EmptyState
              title="Chưa có cảm biến đang hoạt động"
              description="Không có bản ghi được xem là mới trong vòng 120 giây để tổng hợp phân tích."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-5 py-4 font-semibold">Cảm biến</th>
                    <th className="px-5 py-4 font-semibold">An toàn</th>
                    <th className="px-5 py-4 font-semibold">Nguy cơ</th>
                    <th className="px-5 py-4 font-semibold">Cháy</th>
                    <th className="px-5 py-4 font-semibold">Dự đoán</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {onlineSensors.map((sensor, index) => (
                    <tr
                      key={`${getSensorId(sensor)}-${index}`}
                      className="hover:bg-slate-50"
                    >
                      <td className="px-5 py-4">
                        <p className="font-semibold text-slate-800">
                          {getSensorId(sensor)}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {getZone(sensor)}
                        </p>
                      </td>

                      {(
                        ["normal", "risk", "fire"] as const
                      ).map((key) => {
                        const value = getProbability(sensor, key);

                        return (
                          <td
                            key={key}
                            className="px-5 py-4 font-medium text-slate-700"
                          >
                            {value === null
                              ? "--"
                              : `${value.toLocaleString("vi-VN", {
                                  maximumFractionDigits: 1,
                                })}%`}
                          </td>
                        );
                      })}

                      <td className="px-5 py-4">
                        <StatusBadge status={getStatus(sensor)} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
          <strong>Lưu ý về xác suất:</strong> Giao diện hiện giả định các trường
          probability_normal, probability_risk và probability_fire có giá trị
          từ 0 đến 1. Nếu backend lưu xác suất theo thang 0–100, cần sửa hàm
          formatProbability để tránh hiển thị sai tỷ lệ.
        </div>
      </>
    );
  }

  function renderPage() {
    switch (page) {
      case "overview":
        return renderOverview();

      case "sensors":
        return renderSensors();

      case "zones":
        return renderZones();

      case "alerts":
        return renderAlerts();

      case "history":
        return renderHistory();

      case "ai":
        return renderAI();

      default:
        return renderOverview();
    }
  }

  /* =========================
     BỐ CỤC CHÍNH
     ========================= */

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      {mobileMenuOpen && (
        <button
          aria-label="Đóng menu"
          onClick={() => setMobileMenuOpen(false)}
          className="fixed inset-0 z-40 bg-slate-950/40 lg:hidden"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[260px] flex-col border-r border-slate-200 bg-white transition-transform duration-200 lg:translate-x-0 ${
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-[76px] items-center gap-3 border-b border-slate-100 px-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-xl font-bold text-white shadow-sm shadow-blue-200">
            S
          </div>

          <div>
            <p className="font-bold tracking-tight text-slate-900">
              SMART FACTORY
            </p>
            <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              Industrial monitoring
            </p>
          </div>

          <button
            aria-label="Đóng menu"
            onClick={() => setMobileMenuOpen(false)}
            className="ml-auto rounded-lg p-2 text-slate-400 hover:bg-slate-100 lg:hidden"
          >
            ✕
          </button>
        </div>

        <div className="px-4 pt-6">
          <div className="rounded-xl border border-emerald-100 bg-emerald-50/70 p-3">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-50" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
              </span>

              <span className="text-xs font-bold text-emerald-800">
                HỆ THỐNG GIÁM SÁT
              </span>
            </div>

            <p className="mt-2 text-xs leading-5 text-emerald-700">
              Tự động cập nhật dữ liệu mỗi 5 giây.
            </p>
          </div>
        </div>

        <nav className="mt-6 flex-1 space-y-1 overflow-y-auto px-3 pb-5">
          {NAV_ITEMS.map((item) => (
            <div key={item.key}>
              {item.section && (
                <p className="mb-2 mt-5 px-3 text-[10px] font-bold tracking-[0.16em] text-slate-400">
                  {item.section}
                </p>
              )}

              <button
                onClick={() => handleNavigate(item.key)}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm transition ${
                  page === item.key
                    ? "bg-blue-50 font-semibold text-blue-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                <span
                  className={`flex h-7 w-7 items-center justify-center rounded-lg text-lg ${
                    page === item.key
                      ? "bg-blue-100 text-blue-700"
                      : "text-slate-400"
                  }`}
                >
                  {item.icon}
                </span>

                <span className="flex-1">{item.label}</span>

                {item.key === "alerts" && alertSensors.length > 0 && (
                  <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-100 px-1.5 text-[10px] font-bold text-red-700">
                    {alertSensors.length}
                  </span>
                )}

                {page === item.key && (
                  <span className="h-1.5 w-1.5 rounded-full bg-blue-600" />
                )}
              </button>
            </div>
          ))}
        </nav>

        <div className="border-t border-slate-100 p-4">
          <div className="rounded-xl bg-slate-50 p-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-200 text-sm text-slate-600">
                ◈
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-800">
                  Smart Factory
                </p>
                <p className="mt-0.5 text-[10px] text-slate-500">
                  Giám sát và cảnh báo
                </p>
              </div>
            </div>
          </div>

          <p className="mt-3 text-center text-[10px] text-slate-400">
            SMART FACTORY MONITORING
          </p>
        </div>
      </aside>

      <div className="min-h-screen lg:pl-[260px]">
        <header className="sticky top-0 z-30 flex h-[76px] items-center justify-between gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              aria-label="Mở menu"
              onClick={() => setMobileMenuOpen(true)}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-200 text-lg text-slate-600 hover:bg-slate-50 lg:hidden"
            >
              ☰
            </button>

            <div className="min-w-0">
              <h1 className="truncate text-lg font-bold tracking-tight text-slate-900">
                {pageTitles[page]}
              </h1>

              <p className="mt-0.5 hidden text-xs text-slate-500 sm:block">
                Hệ thống giám sát và cảnh báo nguy cơ cháy nổ
              </p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-xs font-semibold text-slate-700">
                {now > 0
                  ? new Date(now).toLocaleDateString("vi-VN", {
                      weekday: "short",
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                    })
                  : "Đang khởi tạo..."}
              </p>

              <p className="mt-1 font-mono text-xs text-slate-500">
                {now > 0
                  ? new Date(now).toLocaleTimeString("vi-VN")
                  : "--:--:--"}
              </p>
            </div>

            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-50 font-bold text-blue-700 ring-1 ring-blue-100">
              SF
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
          <div className="mb-6 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span>Smart Factory</span>
            <span className="text-slate-300">/</span>
            <span className="font-medium text-slate-700">
              {pageTitles[page]}
            </span>

            <span className="ml-auto flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  error
                    ? "bg-red-500"
                    : lastSuccessfulUpdate
                      ? "bg-emerald-500"
                      : "bg-amber-500"
                }`}
              />

              {error
                ? "Lỗi kết nối API"
                : lastSuccessfulUpdate
                  ? "Đã kết nối API"
                  : "Đang kết nối"}
            </span>
          </div>

          {renderPage()}

          <footer className="mt-10 flex flex-col justify-between gap-2 border-t border-slate-200 py-5 text-xs text-slate-400 sm:flex-row sm:items-center">
            <p>
              © {now > 0 ? new Date(now).getFullYear() : 2026} Smart Factory.
              Hệ thống giám sát cảm biến.
            </p>

            <p>
              {lastSuccessfulUpdate
                ? `Cập nhật gần nhất: ${new Date(
                    lastSuccessfulUpdate
                  ).toLocaleTimeString("vi-VN")}`
                : "Chưa có dữ liệu cập nhật"}
            </p>
          </footer>
        </main>
      </div>
    </div>
  );
}
