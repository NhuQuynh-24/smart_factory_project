"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

type SensorStatus = "NORMAL" | "RISK" | "FIRE" | "UNKNOWN";
type ConnectionStatus = "ONLINE" | "OFFLINE" | "UNKNOWN";
type PageKey = "overview" | "sensors" | "zones" | "alerts" | "history" | "ai";

type Sensor = {
  id?: number | string;
  sensor_id?: string;
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

type ApiResponse = {
  data?: Sensor[];
  sensors?: Sensor[];
  results?: Sensor[];
  error?: string;
  message?: string;
};

const TOTAL_SENSORS = 50;
const STALE_SECONDS = 120;
const REFRESH_INTERVAL = 5000;

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

const NAV: { key: PageKey; label: string; icon: string; group?: string }[] = [
  { key: "overview", label: "Tổng quan", icon: "◫", group: "GIÁM SÁT" },
  { key: "sensors", label: "Giám sát cảm biến", icon: "⌁" },
  { key: "zones", label: "Khu vực nhà máy", icon: "▦" },
  { key: "alerts", label: "Cảnh báo", icon: "⚠" },
  { key: "history", label: "Dữ liệu nhận được", icon: "▤", group: "DỮ LIỆU" },
  { key: "ai", label: "Phân tích AI", icon: "✳" },
];

function num(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function sensorId(s: Sensor): string {
  return String(s.sensor_id ?? s.id ?? "UNKNOWN");
}

function rawZone(s: Sensor): string {
  return String(s.zone ?? s.area ?? s.location ?? "Chưa xác định");
}

function zoneName(s: Sensor): string {
  const raw = rawZone(s);
  return ZONES[raw] ?? raw.replaceAll("_", " ");
}

function timestamp(s: Sensor): string | null {
  const value = s.created_at ?? s.timestamp;
  return value === null || value === undefined || value === "" ? null : String(value);
}

function timeMs(s: Sensor): number | null {
  const value = timestamp(s);
  if (!value) return null;
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : null;
}

function statusOf(value: unknown): SensorStatus {
  const v = String(value ?? "").trim().toUpperCase().replaceAll("-", "_").replaceAll(" ", "_");
  if (["FIRE", "FIRE_DETECTED", "FIRE_ALERT", "CHAY", "CHÁY", "DANGER_FIRE", "2"].includes(v)) return "FIRE";
  if (["RISK", "FIRE_RISK", "WARNING", "WARN", "DANGER", "CANH_BAO", "CẢNH_BÁO", "1"].includes(v)) return "RISK";
  if (["NORMAL", "SAFE", "OK", "AN_TOAN", "AN_TOÀN", "0"].includes(v)) return "NORMAL";
  return "UNKNOWN";
}

function getStatus(s: Sensor): SensorStatus {
  return statusOf(s.status ?? s.prediction ?? s.predicted_class ?? s.result ?? s.label);
}

function connectionOf(s: Sensor, now: number): ConnectionStatus {
  const t = timeMs(s);
  if (t === null || now === 0) return "UNKNOWN";
  const age = (now - t) / 1000;
  return age >= -60 && age <= STALE_SECONDS ? "ONLINE" : "OFFLINE";
}

function statusLabel(s: SensorStatus): string {
  return ({ NORMAL: "NORMAL · An toàn", RISK: "RISK · Nguy cơ", FIRE: "FIRE · Phát hiện cháy", UNKNOWN: "UNKNOWN · Chưa xác định" })[s];
}

function fmtTime(value: string | null): string {
  if (!value) return "Chưa có dữ liệu";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString("vi-VN");
}

function fmtClock(value: string | null): string {
  if (!value) return "--:--:--";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleTimeString("vi-VN");
}

function fmtNum(value: unknown, digits = 1): string {
  const n = num(value);
  return n === null ? "--" : n.toLocaleString("vi-VN", { maximumFractionDigits: digits });
}

function probability(value: unknown): number | null {
  const n = num(value);
  if (n === null) return null;
  // Đang giả định xác suất lưu ở thang 0–1.
  // Nếu backend lưu ở thang 0–100, đổi phép tính thành: Math.max(0, Math.min(100, n))
  return Math.max(0, Math.min(100, n * 100));
}

function probabilityOf(s: Sensor, kind: "normal" | "risk" | "fire"): number | null {
  const field = kind === "normal" ? s.probability_normal : kind === "risk" ? s.probability_risk : s.probability_fire;
  return probability(field);
}

function Badge({ status }: { status: SensorStatus }) {
  const cls: Record<SensorStatus, string> = {
    NORMAL: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    RISK: "bg-amber-50 text-amber-700 ring-amber-200",
    FIRE: "bg-red-50 text-red-700 ring-red-200",
    UNKNOWN: "bg-slate-100 text-slate-600 ring-slate-200",
  };
  const dot: Record<SensorStatus, string> = {
    NORMAL: "bg-emerald-500", RISK: "bg-amber-500", FIRE: "bg-red-500", UNKNOWN: "bg-slate-400",
  };
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${cls[status]}`}><span className={`h-1.5 w-1.5 rounded-full ${dot[status]}`} />{statusLabel(status)}</span>;
}

function ConnectionBadge({ status }: { status: ConnectionStatus }) {
  const cls = status === "ONLINE" ? "bg-emerald-50 text-emerald-700" : status === "OFFLINE" ? "bg-slate-100 text-slate-600" : "bg-amber-50 text-amber-700";
  const label = status === "ONLINE" ? "ONLINE" : status === "OFFLINE" ? "OFFLINE" : "UNKNOWN";
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${cls}`}>{label}</span>;
}

function Metric({ title, value, detail, icon, tone }: { title: string; value: string | number; detail: string; icon: string; tone: "blue" | "green" | "amber" | "red" | "slate" }) {
  const tones = {
    blue: "bg-blue-50 text-blue-700", green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700", red: "bg-red-50 text-red-700", slate: "bg-slate-100 text-slate-700",
  };
  return <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md">
    <div className="flex items-start justify-between gap-3">
      <div><p className="text-sm font-medium text-slate-500">{title}</p><p className="mt-3 text-3xl font-bold tracking-tight text-slate-900">{value}</p></div>
      <div className={`flex h-11 w-11 items-center justify-center rounded-xl text-xl ${tones[tone]}`}>{icon}</div>
    </div>
    <p className="mt-4 text-xs leading-5 text-slate-500">{detail}</p>
  </div>;
}

function Heading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div>
    <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-600">{eyebrow}</p>
    <h2 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">{title}</h2>
    <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
  </div>{action}</div>;
}

function Empty({ title, description }: { title: string; description: string }) {
  return <div className="flex min-h-44 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center">
    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-200 text-xl">▤</div>
    <h3 className="mt-4 font-semibold text-slate-800">{title}</h3><p className="mt-2 max-w-md text-sm leading-6 text-slate-500">{description}</p>
  </div>;
}

function SensorTable({ sensors, now, compact = false }: { sensors: Sensor[]; now: number; compact?: boolean }) {
  if (!sensors.length) return <Empty title="Chưa có dữ liệu cảm biến" description="API chưa trả về bản ghi phù hợp. Kiểm tra API và kết nối backend cảm biến." />;
  return <div className="overflow-x-auto"><table className="w-full min-w-[790px] text-left text-sm">
    <thead><tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
      <th className="px-5 py-4 font-semibold">Mã cảm biến</th><th className="px-5 py-4 font-semibold">Khu vực</th><th className="px-5 py-4 font-semibold">Trạng thái</th><th className="px-5 py-4 font-semibold">Kết nối</th><th className="px-5 py-4 font-semibold">Nhiệt độ</th><th className="px-5 py-4 font-semibold">Cập nhật gần nhất</th>
    </tr></thead>
    <tbody className="divide-y divide-slate-100">{sensors.slice(0, compact ? 6 : undefined).map((s, i) => <tr key={`${sensorId(s)}-${timestamp(s) ?? i}-${i}`} className="hover:bg-slate-50">
      <td className="whitespace-nowrap px-5 py-4 font-semibold text-slate-800">{sensorId(s)}</td><td className="px-5 py-4 text-slate-600">{zoneName(s)}</td><td className="px-5 py-4"><Badge status={getStatus(s)} /></td><td className="px-5 py-4"><ConnectionBadge status={connectionOf(s, now)} /></td><td className="px-5 py-4 text-slate-600">{fmtNum(s.temperature)} °C</td><td className="whitespace-nowrap px-5 py-4 text-slate-500">{fmtClock(timestamp(s))}</td>
    </tr>)}</tbody>
  </table></div>;
}

export default function Home() {
  const [page, setPage] = useState<PageKey>("overview");
  const [sensors, setSensors] = useState<Sensor[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [now, setNow] = useState(0);
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [zoneFilter, setZoneFilter] = useState("ALL");

  const loadSensors = useCallback(async (initial = false) => {
    if (initial) setLoading(true); else setRefreshing(true);
    try {
      const response = await fetch("/api/sensors", { method: "GET", cache: "no-store", headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`API trả về mã lỗi ${response.status}. Kiểm tra API và kết nối backend cảm biến.`);
      const payload: unknown = await response.json();
      let rows: Sensor[] = [];
      if (Array.isArray(payload)) rows = payload as Sensor[];
      else if (payload && typeof payload === "object") {
        const p = payload as ApiResponse;
        if (Array.isArray(p.data)) rows = p.data;
        else if (Array.isArray(p.sensors)) rows = p.sensors;
        else if (Array.isArray(p.results)) rows = p.results;
        else if (p.error) throw new Error(p.error);
      }
      setSensors(rows);
      setError("");
      setLastUpdate(Date.now());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Đã xảy ra lỗi không xác định.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Date.now() chỉ được gọi sau khi component chạy trên trình duyệt để tránh lỗi prerender.
  useEffect(() => {
    setNow(Date.now());
    void loadSensors(true);
    const refreshTimer = window.setInterval(() => void loadSensors(false), REFRESH_INTERVAL);
    const clockTimer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => {
      window.clearInterval(refreshTimer);
      window.clearInterval(clockTimer);
    };
  }, [loadSensors]);

  const latestSensors = useMemo(() => {
    const latest = new Map<string, Sensor>();
    const sorted = [...sensors].sort((a, b) => {
      const ta = timeMs(a) ?? 0, tb = timeMs(b) ?? 0;
      if (ta !== tb) return tb - ta;
      return (num(b.id) ?? 0) - (num(a.id) ?? 0);
    });
    for (const s of sorted) if (!latest.has(sensorId(s))) latest.set(sensorId(s), s);
    return [...latest.values()];
  }, [sensors]);

  const online = useMemo(() => latestSensors.filter(s => connectionOf(s, now) === "ONLINE"), [latestSensors, now]);
  const offline = useMemo(() => latestSensors.filter(s => connectionOf(s, now) === "OFFLINE"), [latestSensors, now]);
  const unknownConnection = useMemo(() => latestSensors.filter(s => connectionOf(s, now) === "UNKNOWN"), [latestSensors, now]);

  // NORMAL is counted only when the sensor has a fresh record; RISK/FIRE are shown even if stale
  // so the dashboard does not hide a previously recorded warning.
  const normal = useMemo(() => online.filter(s => getStatus(s) === "NORMAL"), [online]);
  const risk = useMemo(() => latestSensors.filter(s => getStatus(s) === "RISK"), [latestSensors]);
  const fire = useMemo(() => latestSensors.filter(s => getStatus(s) === "FIRE"), [latestSensors]);
  const unknownStatus = useMemo(() => latestSensors.filter(s => getStatus(s) === "UNKNOWN"), [latestSensors]);
  const alerts = useMemo(() => latestSensors.filter(s => ["RISK", "FIRE"].includes(getStatus(s))), [latestSensors]);
  const missing = Math.max(0, TOTAL_SENSORS - latestSensors.length);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return sensors.filter(s => {
      const matchQ = !q || sensorId(s).toLowerCase().includes(q) || zoneName(s).toLowerCase().includes(q);
      return matchQ && (statusFilter === "ALL" || getStatus(s) === statusFilter) && (zoneFilter === "ALL" || zoneName(s) === zoneFilter);
    });
  }, [sensors, search, statusFilter, zoneFilter]);

  const zones = useMemo(() => [...new Set(latestSensors.map(zoneName))].sort(), [latestSensors]);
  const zoneSummaries = useMemo(() => Object.entries(ZONES).map(([key, label]) => {
    const rows = latestSensors.filter(s => rawZone(s) === key || zoneName(s) === label);
    return {
      key, label, count: rows.length,
      online: rows.filter(s => connectionOf(s, now) === "ONLINE").length,
      risk: rows.filter(s => getStatus(s) === "RISK").length,
      fire: rows.filter(s => getStatus(s) === "FIRE").length,
    };
  }), [latestSensors, now]);

  const averages = useMemo(() => {
    const avg = (kind: "normal" | "risk" | "fire"): number | null => {
      const vals = online.map(s => probabilityOf(s, kind)).filter((v): v is number => v !== null);
      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
    };
    return { normal: avg("normal"), risk: avg("risk"), fire: avg("fire") };
  }, [online]);

  const titles: Record<PageKey, string> = {
    overview: "Tổng quan hệ thống", sensors: "Giám sát cảm biến", zones: "Khu vực nhà máy",
    alerts: "Trung tâm cảnh báo", history: "Dữ liệu nhận được", ai: "Phân tích AI",
  };
  const go = (key: PageKey) => { setPage(key); setMobileMenu(false); };

  function renderOverview() {
    const metrics = [
  {
    title: "TỔNG CẢM BIẾN",
    value: TOTAL_SENSORS,
    detail: "Tổng số cảm biến được cấu hình",
    icon: "⌁",
    tone: "blue" as const,
  },
  {
    title: "ĐÃ CÓ DỮ LIỆU",
    value: latestSensors.length,
    detail: "Cảm biến đã xuất hiện trong API",
    icon: "▤",
    tone: "green" as const,
  },
  {
    title: "CHƯA CÓ DỮ LIỆU",
    value: missing,
    detail: "Cảm biến chưa xuất hiện trong API",
    icon: "○",
    tone: "slate" as const,
  },
  {
    title: "NORMAL · AN TOÀN",
    value: normal.length,
    detail: "Cảm biến đang hoạt động an toàn",
    icon: "✓",
    tone: "green" as const,
  },
  {
    title: "RISK · NGUY CƠ",
    value: risk.length,
    detail: "Cảm biến có cảnh báo nguy cơ",
    icon: "⚠",
    tone: "amber" as const,
  },
  {
    title: "FIRE · PHÁT HIỆN CHÁY",
    value: fire.length,
    detail: "Cảm biến ghi nhận trạng thái cháy",
    icon: "!",
    tone: "red" as const,
  },
  {
    title: "OFFLINE · MẤT KẾT NỐI",
    value: offline.length,
    detail: "Cảm biến đã quá thời gian cập nhật",
    icon: "◌",
    tone: "slate" as const,
  },
  {
    title: "UNKNOWN · CHƯA XÁC ĐỊNH",
    value: unknownStatus.length + unknownConnection.length,
    detail: "Cảm biến chưa xác định được trạng thái",
    icon: "?",
    tone: "blue" as const,
  },
];
    const breakdown = [
      { label: "NORMAL — An toàn", value: normal.length, color: "bg-emerald-500" },
      { label: "RISK — Nguy cơ", value: risk.length, color: "bg-amber-500" },
      { label: "FIRE — Phát hiện cháy", value: fire.length, color: "bg-red-500" },
      { label: "OFFLINE — Mất kết nối", value: offline.length, color: "bg-slate-400" },
      { label: "UNKNOWN — Chưa xác định trạng thái", value: unknownStatus.length, color: "bg-blue-500" },
      { label: "Chưa xuất hiện trong dữ liệu", value: missing, color: "bg-slate-300" },
    ];
    return <>
      <Heading eyebrow="Bảng điều khiển" title="Tổng quan hệ thống" description="Theo dõi 50 cảm biến cấu hình, tình trạng an toàn và cảnh báo nhà máy theo dữ liệu API." action={<button onClick={() => void loadSensors(false)} disabled={refreshing} className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60">{refreshing ? "Đang cập nhật..." : "↻ Làm mới dữ liệu"}</button>} />
      {error && <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"><p className="font-semibold">Không thể tải dữ liệu cảm biến</p><p className="mt-1 break-words">{error}</p><button onClick={() => void loadSensors(false)} className="mt-3 rounded-lg border border-red-200 bg-white px-3 py-2 font-semibold">Thử lại</button></div>}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">{metrics.map(m => <Metric key={m.title} {...m} />)}</div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm xl:col-span-2">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-bold text-slate-900">Phân bổ trạng thái cảm biến</h3><p className="mt-1 text-sm text-slate-500">Đối chiếu từng nhóm với tổng cấu hình 50 cảm biến.</p></div><span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">{TOTAL_SENSORS} cảm biến</span></div>
          <div className="mt-6 space-y-5">{breakdown.map(item => <div key={item.label}>
            <div className="mb-2 flex items-center justify-between gap-3 text-sm"><span className="text-slate-600">{item.label}</span><span className="font-bold text-slate-900">{item.value}/{TOTAL_SENSORS}</span></div>
            <div className="h-2.5 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${item.color}`} style={{ width: `${Math.min(100, item.value / TOTAL_SENSORS * 100)}%` }} /></div>
          </div>)}</div>
          <p className="mt-5 rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-500">Các nhóm được tính từ bản ghi API hiện có. Một cảm biến có thể vừa có trạng thái RISK/FIRE vừa bị OFFLINE nếu bản ghi của nó đã cũ; vì vậy các nhóm không nhất thiết cộng lại bằng 50.</p>
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3"><h3 className="font-bold text-slate-900">Cảnh báo gần đây</h3><span className="rounded-full bg-red-50 px-2.5 py-1 text-xs font-bold text-red-700">{alerts.length}</span></div>
          <p className="mt-1 text-sm text-slate-500">Các cảm biến có trạng thái RISK hoặc FIRE.</p>
          <div className="mt-4 space-y-3">{alerts.slice(0, 5).map((s, i) => <div key={`${sensorId(s)}-${i}`} className="flex items-start gap-3 rounded-xl border border-slate-100 p-3">
            <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${getStatus(s) === "FIRE" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}`}>⚠</div>
            <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-slate-800">{sensorId(s)}</p><p className="mt-1 truncate text-xs text-slate-500">{zoneName(s)}</p><div className="mt-2"><Badge status={getStatus(s)} /></div></div>
          </div>)}{alerts.length === 0 && <div className="rounded-xl bg-emerald-50 p-5 text-center"><p className="font-semibold text-emerald-800">Chưa ghi nhận cảnh báo</p><p className="mt-1 text-xs text-emerald-700">Không có bản ghi RISK hoặc FIRE.</p></div>}</div>
          {alerts.length > 5 && <button onClick={() => go("alerts")} className="mt-4 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-semibold hover:bg-slate-50">Xem tất cả cảnh báo →</button>}
        </section>
      </div>

      <section className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-5"><div><h3 className="font-bold text-slate-900">Cảm biến cập nhật gần đây</h3><p className="mt-1 text-sm text-slate-500">Bản ghi mới nhất của mỗi cảm biến được API trả về.</p></div><button onClick={() => go("sensors")} className="text-sm font-semibold text-blue-600">Xem danh sách →</button></div>
        <SensorTable sensors={latestSensors} now={now} compact />
      </section>
      <div className="mt-6 rounded-2xl border border-blue-100 bg-blue-50 p-4 text-sm leading-6 text-blue-900"><strong>Trạng thái API:</strong> {lastUpdate ? `Lần tải dữ liệu thành công gần nhất ${new Date(lastUpdate).toLocaleTimeString("vi-VN")}.` : "Đang chờ dữ liệu API."} {loading ? "Đang tải lần đầu..." : "Tự động làm mới mỗi 5 giây."}</div>
    </>;
  }

  function renderSensors() {
    return <>
      <Heading eyebrow="Giám sát thời gian thực" title="Giám sát cảm biến" description="Tìm kiếm và lọc cảm biến theo mã, khu vực và trạng thái." action={<button onClick={() => void loadSensors(false)} disabled={refreshing} className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{refreshing ? "Đang tải..." : "↻ Làm mới"}</button>} />
      {error && <p className="mb-4 rounded-xl bg-red-50 p-4 text-sm text-red-700">{error}</p>}
      <div className="mb-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Metric title="Tổng cấu hình" value={TOTAL_SENSORS} detail="Số cảm biến dự kiến" icon="⌁" tone="blue" />
        <Metric title="Có bản ghi" value={latestSensors.length} detail="Cảm biến đã xuất hiện trong API" icon="▤" tone="blue" />
        <Metric title="ONLINE" value={online.length} detail="Dữ liệu trong 120 giây" icon="●" tone="green" />
        <Metric title="OFFLINE" value={offline.length} detail="Bản ghi đã quá cũ" icon="◌" tone="slate" />
      </div>
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="grid grid-cols-1 gap-3 border-b border-slate-100 p-5 md:grid-cols-3">
          <input aria-label="Tìm cảm biến" value={search} onChange={e => setSearch(e.target.value)} placeholder="Tìm mã cảm biến, khu vực..." className="rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-400" />
          <select aria-label="Lọc trạng thái" value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-400"><option value="ALL">Tất cả trạng thái</option><option value="NORMAL">NORMAL</option><option value="RISK">RISK</option><option value="FIRE">FIRE</option><option value="UNKNOWN">UNKNOWN</option></select>
          <select aria-label="Lọc khu vực" value={zoneFilter} onChange={e => setZoneFilter(e.target.value)} className="rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-400"><option value="ALL">Tất cả khu vực</option>{zones.map(z => <option key={z} value={z}>{z}</option>)}</select>
        </div>
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3 text-sm"><span className="text-slate-500">Tìm thấy <b className="text-slate-800">{filtered.length}</b> bản ghi</span><button onClick={() => { setSearch(""); setStatusFilter("ALL"); setZoneFilter("ALL"); }} className="font-semibold text-blue-600">Xóa bộ lọc</button></div>
        <SensorTable sensors={filtered} now={now} />
      </section>
    </>;
  }

  function renderZones() {
    return <>
      <Heading eyebrow="Bản đồ vận hành" title="Khu vực nhà máy" description="Tổng hợp cảm biến theo 10 khu vực được cấu hình." />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">{zoneSummaries.map((z, i) => <div key={z.key} className={`rounded-2xl border bg-white p-5 shadow-sm ${z.fire ? "border-red-200" : z.risk ? "border-amber-200" : "border-slate-200"}`}>
        <div className="flex items-start justify-between"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-xl text-blue-700">▦</div><span className="text-xs text-slate-400">KHU VỰC {String(i + 1).padStart(2, "0")}</span></div>
        <h3 className="mt-4 font-bold text-slate-900">{z.label}</h3><p className="mt-1 text-sm text-slate-500">{z.count} cảm biến có bản ghi</p>
        <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100"><div className={`h-full ${z.fire ? "bg-red-500" : z.risk ? "bg-amber-500" : "bg-emerald-500"}`} style={{ width: `${z.count ? z.online / z.count * 100 : 0}%` }} /></div>
        <div className="mt-4 grid grid-cols-3 gap-2">{[{ label: "ONLINE", n: z.online, cls: "bg-emerald-50 text-emerald-800" }, { label: "RISK", n: z.risk, cls: "bg-amber-50 text-amber-800" }, { label: "FIRE", n: z.fire, cls: "bg-red-50 text-red-800" }].map(x => <div key={x.label} className={`rounded-lg p-2 ${x.cls}`}><p className="text-[11px]">{x.label}</p><p className="mt-1 text-lg font-bold">{x.n}</p></div>)}</div>
      </div>)}</div>
      <p className="mt-5 rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm leading-6 text-blue-800">Khu vực được ghép theo tên trong dữ liệu API. Nếu backend dùng tên khác danh sách cấu hình, bản ghi có thể không được ghép đúng khu vực.</p>
    </>;
  }

  function renderAlerts() {
    return <>
      <Heading eyebrow="An toàn nhà máy" title="Trung tâm cảnh báo" description="Theo dõi các bản ghi RISK và FIRE." action={<button onClick={() => void loadSensors(false)} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold">↻ Cập nhật</button>} />
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3"><Metric title="Tổng cảnh báo" value={alerts.length} detail="Bản ghi RISK và FIRE" icon="⚠" tone="amber" /><Metric title="RISK" value={risk.length} detail="Phát hiện nguy cơ" icon="!" tone="amber" /><Metric title="FIRE" value={fire.length} detail="Phát hiện cháy" icon="!" tone="red" /></div>
      {alerts.length === 0 ? <Empty title="Chưa ghi nhận cảnh báo" description="Không tìm thấy bản ghi RISK hoặc FIRE trong dữ liệu API hiện tại." /> : <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">{alerts.map((s, i) => <div key={`${sensorId(s)}-${i}`} className="flex flex-col justify-between gap-3 border-b border-slate-100 p-5 sm:flex-row sm:items-center"><div><div className="flex flex-wrap items-center gap-2"><b>{sensorId(s)}</b><Badge status={getStatus(s)} /></div><p className="mt-1 text-sm text-slate-500">{zoneName(s)} · {fmtTime(timestamp(s))}</p></div><div className="sm:text-right"><ConnectionBadge status={connectionOf(s, now)} /><p className="mt-2 text-xs text-slate-500">Nhiệt độ: {fmtNum(s.temperature)} °C</p></div></div>)}</section>}
      <p className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900"><b>Lưu ý an toàn:</b> Giao diện giám sát không thay thế thiết bị báo cháy chuyên dụng hoặc quy trình ứng phó khẩn cấp.</p>
    </>;
  }

  function renderHistory() {
    const history = [...sensors].sort((a, b) => (timeMs(b) ?? 0) - (timeMs(a) ?? 0));
    return <>
      <Heading eyebrow="Nhật ký hệ thống" title="Dữ liệu nhận được" description="Các bản ghi mà API trả về, sắp xếp theo thời gian gần nhất." action={<button onClick={() => void loadSensors(false)} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold">↻ Tải dữ liệu</button>} />
      <div className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3"><Metric title="Bản ghi API" value={sensors.length} detail="Số bản ghi tải về" icon="▤" tone="blue" /><Metric title="Cảm biến riêng biệt" value={latestSensors.length} detail="Mã cảm biến khác nhau" icon="⌁" tone="green" /><Metric title="Số bản ghi đang hiển thị" value={Math.min(history.length, 500)} detail="Tối đa 500 bản ghi" icon="◷" tone="slate" /></div>
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="border-b border-slate-100 p-5"><h3 className="font-bold">Nhật ký dữ liệu</h3><p className="mt-1 text-sm text-slate-500">Lịch sử giới hạn theo số bản ghi API trả về.</p></div>{!history.length ? <Empty title="Chưa có dữ liệu" description="API chưa trả về bản ghi nào." /> : <div className="overflow-x-auto"><table className="w-full min-w-[800px] text-left text-sm"><thead><tr className="border-b bg-slate-50 text-xs uppercase text-slate-500"><th className="px-5 py-4">STT</th><th className="px-5 py-4">Cảm biến</th><th className="px-5 py-4">Khu vực</th><th className="px-5 py-4">Trạng thái</th><th className="px-5 py-4">Nhiệt độ</th><th className="px-5 py-4">Thời gian</th></tr></thead><tbody className="divide-y divide-slate-100">{history.slice(0, 500).map((s, i) => <tr key={`${sensorId(s)}-${timestamp(s) ?? i}-${i}`}><td className="px-5 py-4 text-slate-400">{i + 1}</td><td className="px-5 py-4 font-semibold">{sensorId(s)}</td><td className="px-5 py-4">{zoneName(s)}</td><td className="px-5 py-4"><Badge status={getStatus(s)} /></td><td className="px-5 py-4">{fmtNum(s.temperature)} °C</td><td className="whitespace-nowrap px-5 py-4 text-slate-500">{fmtTime(timestamp(s))}</td></tr>)}</tbody></table></div>}</section>
      <p className="mt-4 text-xs leading-5 text-slate-500">Trang này chỉ hiển thị dữ liệu API trả về. Nếu backend chỉ truy vấn 100 bản ghi gần nhất, cần sửa truy vấn backend để xem lịch sử dài hơn.</p>
    </>;
  }

  function renderAI() {
    const cards = [{ label: "An toàn", value: averages.normal, color: "bg-emerald-500", text: "text-emerald-700" }, { label: "Nguy cơ", value: averages.risk, color: "bg-amber-500", text: "text-amber-700" }, { label: "Cháy", value: averages.fire, color: "bg-red-500", text: "text-red-700" }];
    return <>
      <Heading eyebrow="Phân tích thông minh" title="Phân tích AI" description="Tổng hợp xác suất dự đoán do backend cung cấp." action={<button onClick={() => void loadSensors(false)} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold">↻ Cập nhật</button>} />
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">{cards.map(c => <div key={c.label} className="rounded-2xl border border-slate-200 bg-white p-5"><p className="text-sm text-slate-500">Xác suất trung bình: {c.label}</p><p className={`mt-3 text-3xl font-bold ${c.text}`}>{c.value === null ? "--" : `${c.value.toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%`}</p><div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${c.color}`} style={{ width: `${c.value ?? 0}%` }} /></div></div>)}</div>
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="border-b border-slate-100 p-5"><h3 className="font-bold">Kết quả dự đoán theo cảm biến</h3><p className="mt-1 text-sm text-slate-500">Chỉ hiển thị cảm biến có dữ liệu mới trong 120 giây.</p></div>{!online.length ? <Empty title="Chưa có cảm biến đang hoạt động" description="Chưa có bản ghi mới để tổng hợp phân tích AI." /> : <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead><tr className="border-b bg-slate-50 text-xs uppercase text-slate-500"><th className="px-5 py-4">Cảm biến</th><th className="px-5 py-4">An toàn</th><th className="px-5 py-4">Nguy cơ</th><th className="px-5 py-4">Cháy</th><th className="px-5 py-4">Trạng thái</th></tr></thead><tbody className="divide-y divide-slate-100">{online.map((s, i) => <tr key={`${sensorId(s)}-${i}`}><td className="px-5 py-4"><b>{sensorId(s)}</b><p className="mt-1 text-xs text-slate-500">{zoneName(s)}</p></td>{(["normal", "risk", "fire"] as const).map(k => { const v = probabilityOf(s, k); return <td key={k} className="px-5 py-4">{v === null ? "--" : `${v.toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%`}</td>; })}<td className="px-5 py-4"><Badge status={getStatus(s)} /></td></tr>)}</tbody></table></div>}</section>
      <p className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900"><b>Lưu ý:</b> Mã đang giả định các trường probability có thang 0–1. Nếu backend lưu thang 0–100, sửa hàm probability ở đầu file để không nhân thêm 100.</p>
    </>;
  }

  return <div className="min-h-screen bg-slate-50 text-slate-800">
    {mobileMenu && <button aria-label="Đóng menu" onClick={() => setMobileMenu(false)} className="fixed inset-0 z-40 bg-slate-950/40 lg:hidden" />}
    <aside className={`fixed inset-y-0 left-0 z-50 flex w-[260px] flex-col border-r border-slate-200 bg-white transition-transform lg:translate-x-0 ${mobileMenu ? "translate-x-0" : "-translate-x-full"}`}>
      <div className="flex h-[76px] items-center gap-3 border-b border-slate-100 px-5"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-xl font-bold text-white">S</div><div><p className="font-bold text-slate-900">SMART FACTORY</p><p className="mt-0.5 text-[10px] uppercase tracking-[0.16em] text-slate-400">Industrial monitoring</p></div><button onClick={() => setMobileMenu(false)} className="ml-auto lg:hidden" aria-label="Đóng menu">✕</button></div>
      <div className="px-4 pt-6"><div className="rounded-xl border border-emerald-100 bg-emerald-50 p-3"><p className="text-xs font-bold text-emerald-800">● HỆ THỐNG GIÁM SÁT</p><p className="mt-2 text-xs text-emerald-700">Tự động cập nhật mỗi 5 giây.</p></div></div>
     <nav className="mt-5 flex-1 space-y-1 overflow-y-auto px-3 pb-5">
  {NAV.map((item) => (
    <div key={item.key}>
      {item.group && (
        <p className="mb-2 mt-5 px-3 text-[10px] font-bold tracking-[0.16em] text-slate-400">
          {item.group}
        </p>
      )}

      <button
        onClick={() => go(item.key)}
        className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm transition ${
          page === item.key
            ? "bg-blue-50 font-semibold text-blue-700"
            : "text-slate-600 hover:bg-slate-50"
        }`}
      >
        <span className="flex h-7 w-7 items-center justify-center text-lg">
          {item.icon}
        </span>

        <span className="flex-1">{item.label}</span>

        {item.key === "alerts" && alerts.length > 0 && (
          <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700">
            {alerts.length}
          </span>
        )}
      </button>
    </div>
  ))}
</nav>
      <div className="border-t border-slate-100 p-4"><p className="text-center text-[10px] text-slate-400">SMART FACTORY MONITORING</p></div>
    </aside>

    <div className="min-h-screen lg:pl-[260px]">
      <header className="sticky top-0 z-30 flex h-[76px] items-center justify-between gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3"><button aria-label="Mở menu" onClick={() => setMobileMenu(true)} className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 lg:hidden">☰</button><div className="min-w-0"><h1 className="truncate text-lg font-bold text-slate-900">{titles[page]}</h1><p className="mt-0.5 hidden text-xs text-slate-500 sm:block">Hệ thống giám sát và cảnh báo nguy cơ cháy nổ</p></div></div>
        <div className="flex shrink-0 items-center gap-3"><div className="hidden text-right sm:block"><p className="text-xs font-semibold text-slate-700">{now ? new Date(now).toLocaleDateString("vi-VN") : "Đang khởi tạo..."}</p><p className="mt-1 font-mono text-xs text-slate-500">{now ? new Date(now).toLocaleTimeString("vi-VN") : "--:--:--"}</p></div><div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-50 font-bold text-blue-700">SF</div></div>
      </header>
      <main className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
        <div className="mb-6 flex flex-wrap items-center gap-2 text-xs text-slate-500"><span>Smart Factory</span><span className="text-slate-300">/</span><span className="font-medium text-slate-700">{titles[page]}</span><span className="ml-auto flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5"><span className={`h-1.5 w-1.5 rounded-full ${error ? "bg-red-500" : lastUpdate ? "bg-emerald-500" : "bg-amber-500"}`} />{error ? "Lỗi kết nối API" : lastUpdate ? "Đã kết nối API" : "Đang kết nối"}</span></div>
        {page === "overview" ? renderOverview() : page === "sensors" ? renderSensors() : page === "zones" ? renderZones() : page === "alerts" ? renderAlerts() : page === "history" ? renderHistory() : renderAI()}
        <footer className="mt-10 flex flex-col justify-between gap-2 border-t border-slate-200 py-5 text-xs text-slate-400 sm:flex-row"><p>© {now ? new Date(now).getFullYear() : 2026} Smart Factory · Hệ thống giám sát cảm biến</p><p>{lastUpdate ? `Cập nhật gần nhất: ${new Date(lastUpdate).toLocaleTimeString("vi-VN")}` : "Chưa có dữ liệu cập nhật"}</p></footer>
      </main>
    </div>
  </div>;
}
