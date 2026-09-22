"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";

type WorkItem = {
  key: string;
  source: string;
  source_id: string;
  title: string;
  subtitle: string;
  status: string;
  status_label: string;
  responsibility: string;
  priority: string;
  due_date?: string | null;
  organization_unit: string;
  href: string;
  can_act: boolean;
  is_review: boolean;
  is_overdue: boolean;
  is_due_soon: boolean;
  attention: string;
};

type WorkCenterResponse = {
  schema_version: number;
  due_soon_days: number;
  summary: {
    total: number;
    overdue: number;
    due_soon: number;
    review: number;
    actionable: number;
    sources: Record<string, number>;
  };
  items: WorkItem[];
};

const sourceLabels: Record<string, string> = {
  action: "اقدام",
  finding: "یافته",
  assessment_item: "آیتم ارزیابی",
  assessment_review: "بازبینی ارزیابی",
  document_approval: "تأیید مستند",
  audit_engagement: "ممیزی",
  audit_workpaper: "کاربرگ ممیزی",
  audit_workpaper_review: "بازبینی کاربرگ",
};

const responsibilityLabels: Record<string, string> = {
  owner: "مالک",
  reviewer: "بازبین",
  assignee: "مسئول انجام",
  approver: "تأییدکننده",
  lead_auditor: "سرممیز",
  tester: "اجراکننده",
  review_queue: "صف بازبینی",
};

const attentionLabels: Record<string, string> = {
  overdue: "گذشته از موعد",
  due_soon: "نزدیک سررسید",
  review: "نیازمند بازبینی",
  normal: "عادی",
};

function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fa-IR", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

export default function WorkCenterPage() {
  const [data, setData] = useState<WorkCenterResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("all");
  const [status, setStatus] = useState("all");
  const [attention, setAttention] = useState("all");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await apiFetch("/work-center/");
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `خطا در دریافت کارهای من (${response.status})`);
      }
      setData(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "دریافت کارهای من ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const statuses = useMemo(
    () => Array.from(new Set((data?.items ?? []).map((item) => item.status).filter(Boolean))).sort(),
    [data],
  );

  const filtered = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase("fa");
    return (data?.items ?? []).filter((item) => {
      if (source !== "all" && item.source !== source) return false;
      if (status !== "all" && item.status !== status) return false;
      if (attention === "overdue" && !item.is_overdue) return false;
      if (attention === "due_soon" && !item.is_due_soon) return false;
      if (attention === "review" && !item.is_review) return false;
      if (attention === "actionable" && !item.can_act) return false;
      if (!needle) return true;
      return [item.title, item.subtitle, item.organization_unit, sourceLabels[item.source], item.status_label]
        .filter(Boolean)
        .some((value) => value.toLocaleLowerCase("fa").includes(needle));
    });
  }, [attention, data, search, source, status]);

  const summary = data?.summary;

  return (
    <main className="adminPage">
      <div className="pageHead">
        <div>
          <Link href="/">← داشبورد</Link>
          <h1>کارهای من</h1>
          <p>صف عملیاتی واحد برای مسئولیت‌ها، سررسیدها و بازبینی‌های شما در ماژول‌های GRC</p>
        </div>
        <button className="secondaryLink" onClick={() => void load()} disabled={loading}>
          {loading ? "در حال به‌روزرسانی…" : "به‌روزرسانی"}
        </button>
      </div>

      {error && <p className="message">{error}</p>}

      <div className="kpis">
        <div className="kpi">
          <span>کل کارهای فعال</span>
          <strong>{summary?.total ?? 0}</strong>
          <small>{summary?.actionable ?? 0} مورد قابل اقدام با مجوز فعلی</small>
        </div>
        <div className="kpi bad">
          <span>گذشته از موعد</span>
          <strong>{summary?.overdue ?? 0}</strong>
          <small>نیازمند توجه فوری</small>
        </div>
        <div className="kpi warn">
          <span>نزدیک سررسید</span>
          <strong>{summary?.due_soon ?? 0}</strong>
          <small>در {data?.due_soon_days ?? 7} روز آینده</small>
        </div>
        <div className="kpi good">
          <span>صف بازبینی</span>
          <strong>{summary?.review ?? 0}</strong>
          <small>بازبینی یا تأیید منتظر شما</small>
        </div>
      </div>

      <div className="toolbar" style={{ marginTop: 20, flexWrap: "wrap" }}>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="جستجو در عنوان، دامنه یا منبع…"
        />
        <select value={source} onChange={(event) => setSource(event.target.value)}>
          <option value="all">همه منابع</option>
          {Object.entries(sourceLabels).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="all">همه وضعیت‌ها</option>
          {statuses.map((value) => (
            <option key={value} value={value}>{value}</option>
          ))}
        </select>
        <select value={attention} onChange={(event) => setAttention(event.target.value)}>
          <option value="all">همه سطح‌های توجه</option>
          <option value="overdue">گذشته از موعد</option>
          <option value="due_soon">نزدیک سررسید</option>
          <option value="review">بازبینی/تأیید</option>
          <option value="actionable">فقط قابل اقدام</option>
        </select>
      </div>

      <section className="panel">
        {loading && !data ? (
          <p className="muted">در حال دریافت مسئولیت‌های شما…</p>
        ) : filtered.length === 0 ? (
          <p className="muted">در فیلتر فعلی کار فعالی برای شما وجود ندارد.</p>
        ) : (
          <table className="dataTable">
            <thead>
              <tr>
                <th>توجه</th>
                <th>کار</th>
                <th>منبع</th>
                <th>مسئولیت</th>
                <th>وضعیت</th>
                <th>سررسید</th>
                <th>دامنه</th>
                <th>دسترسی</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.key}>
                  <td><span className="pill">{attentionLabels[item.attention] ?? item.attention}</span></td>
                  <td>
                    <Link href={item.href}><strong>{item.title}</strong></Link>
                    {item.subtitle && <div className="muted">{item.subtitle}</div>}
                  </td>
                  <td>{sourceLabels[item.source] ?? item.source}</td>
                  <td>{responsibilityLabels[item.responsibility] ?? item.responsibility}</td>
                  <td><span className="pill">{item.status_label || item.status}</span></td>
                  <td>{formatDate(item.due_date)}</td>
                  <td>{item.organization_unit || "کل سازمان"}</td>
                  <td>
                    <Link className="secondaryLink" href={item.href}>
                      {item.can_act ? "باز کردن و اقدام" : "مشاهده"}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
