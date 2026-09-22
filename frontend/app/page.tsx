"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../lib/api";

const menuSections = [
  {
    label: "اصلی",
    items: [
      { label: "داشبورد", href: "/", glyph: "⌂" },
      { label: "سازمان", href: "/organization", glyph: "◎" },
      { label: "دارایی‌ها", href: "/assets", glyph: "▦" },
      { label: "چارچوب‌ها", href: "/frameworks", glyph: "▤" },
      { label: "کنترل‌ها", href: "/controls", glyph: "◇" },
      { label: "ریسک", href: "/risks", glyph: "△" },
      { label: "انطباق و ارزیابی", href: "/assessments", glyph: "✓" },
    ],
  },
  {
    label: "عملیات",
    items: [
      { label: "ممیزی", href: "/audits", glyph: "◉" },
      { label: "یافته‌ها", href: "/findings", glyph: "!" },
      { label: "اقدامات", href: "/actions", glyph: "□" },
      { label: "شواهد", href: "/evidence", glyph: "◈" },
      { label: "مستندات", href: "/documents", glyph: "▱" },
      { label: "اتصال‌ها", href: "/connectors", glyph: "↔" },
      { label: "گزارش‌ها", href: "/reports", glyph: "▥" },
    ],
  },
  {
    label: "اتوماسیون",
    items: [
      { label: "آزمون کنترل‌ها", href: "/control-tests", glyph: "⌁" },
      { label: "گردش‌کار", href: "/workflows", glyph: "⇄" },
      { label: "اعلان‌ها", href: "/notifications", glyph: "•" },
      { label: "هوش مصنوعی", href: "/ai", glyph: "✦" },
    ],
  },
  {
    label: "مدیریت",
    items: [
      { label: "کاربران", href: "/admin/users", glyph: "♙" },
      { label: "نقش‌ها و مجوزها", href: "/admin/roles", glyph: "⌘" },
      { label: "تنظیمات امنیتی", href: "/settings/security", glyph: "⚙" },
      { label: "عملیات سامانه", href: "/admin/operations", glyph: "◷" },
    ],
  },
];

type Finding = {
  id: string;
  title: string;
  severity?: string;
  due_date?: string | null;
};

type FrameworkSummary = {
  framework_version_id: string;
  framework_code: string;
  framework_name: string;
  version_code: string;
  assessment_count: number;
  average_score: number | null;
  average_progress: number | null;
  completed_count: number;
  in_progress_count: number;
  draft_count: number;
};

type RiskHeatCell = {
  likelihood: number;
  impact: number;
  count: number;
  max_level: string;
};

type TopRisk = {
  id: string;
  code: string;
  title: string;
  status: string;
  owner: string;
  score: number | null;
  level: string;
  likelihood: number | null;
  impact: number | null;
  evaluated_at?: string | null;
};

type AttentionAction = {
  id: string;
  title: string;
  owner: string;
  priority: string;
  status: string;
  progress: number;
  source_type: string;
  source_id?: string | null;
  due_date?: string | null;
  is_overdue: boolean;
};

type Deadline = {
  type: string;
  date: string;
  title: string;
  subtitle: string;
  href: string;
};

type Dashboard = {
  dashboard_schema_version?: number;
  compliance_score: number | null;
  high_critical_residual_risks: number;
  open_findings: number;
  overdue_actions: number;
  control_effectiveness: Record<string, number>;
  effective_controls_percent?: number | null;
  assessments_due: number;
  top_findings: Finding[];
  framework_summaries?: FrameworkSummary[];
  risk_heatmap?: RiskHeatCell[];
  top_risks?: TopRisk[];
  attention_actions?: AttentionAction[];
  upcoming_deadlines?: Deadline[];
};

const severityLabels: Record<string, string> = {
  critical: "بحرانی",
  high: "بالا",
  medium: "متوسط",
  low: "پایین",
};

const actionStatusLabels: Record<string, string> = {
  todo: "در انتظار",
  in_progress: "در جریان",
  review: "در بازبینی",
  done: "تکمیل",
  cancelled: "لغو",
};

const sourceLabels: Record<string, string> = {
  risk: "ریسک",
  finding: "یافته",
  assessment: "ارزیابی",
  audit: "ممیزی",
  control: "کنترل",
  document: "مستند",
};

const deadlineTypeLabels: Record<string, string> = {
  assessment: "ارزیابی",
  action: "اقدام",
  risk_review: "بازنگری ریسک",
  audit: "ممیزی",
};

function clampPercent(value: number | null | undefined) {
  return Math.max(0, Math.min(100, value ?? 0));
}

function formatNumber(value: number | null | undefined, digits = 0) {
  if (value == null) return "—";
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: digits }).format(value);
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fa-IR", { day: "numeric", month: "short" }).format(date);
}

function formatSeverity(value?: string) {
  return severityLabels[value ?? ""] ?? value ?? "—";
}

function metricTone(value: number | null) {
  if (value === null) return "neutral";
  if (value >= 80) return "good";
  if (value >= 60) return "warn";
  return "bad";
}

function EmptyState({ children }: { children: string }) {
  return <p className="dashboardEmpty">{children}</p>;
}

function ProgressBar({ value, tone = "blue" }: { value: number | null; tone?: string }) {
  const percent = clampPercent(value);
  return (
    <div className="dashboardProgress" aria-label={value == null ? "بدون امتیاز" : `${value}%`}>
      <span className={`dashboardProgressFill ${tone}`} style={{ width: `${percent}%` }} />
    </div>
  );
}

function HomeHeatmap({ cells }: { cells: RiskHeatCell[] }) {
  const likelihoods = useMemo(
    () => Array.from(new Set(cells.map((cell) => cell.likelihood))).sort((a, b) => b - a),
    [cells],
  );
  const impacts = useMemo(
    () => Array.from(new Set(cells.map((cell) => cell.impact))).sort((a, b) => a - b),
    [cells],
  );
  const cellMap = useMemo(
    () => new Map(cells.map((cell) => [`${cell.likelihood}:${cell.impact}`, cell])),
    [cells],
  );

  if (!cells.length) {
    return <EmptyState>هنوز ارزیابی Residual برای ساخت نقشه ریسک ثبت نشده است.</EmptyState>;
  }

  return (
    <div className="heatmapWrap">
      <div className="heatmapAxisTitle vertical">احتمال</div>
      <div className="heatmapBody">
        {likelihoods.map((likelihood) => (
          <div
            className="heatmapRow"
            key={likelihood}
            style={{ gridTemplateColumns: `72px repeat(${impacts.length}, minmax(44px, 1fr))` }}
          >
            <span className="heatmapScale">{formatNumber(likelihood, 2)}</span>
            {impacts.map((impact) => {
              const cell = cellMap.get(`${likelihood}:${impact}`);
              return (
                <div
                  key={`${likelihood}:${impact}`}
                  className={`heatmapCell ${cell?.max_level || "empty"}`}
                  title={cell ? `${cell.count} ریسک · ${formatSeverity(cell.max_level)}` : "بدون ریسک"}
                >
                  {cell?.count ? formatNumber(cell.count) : ""}
                </div>
              );
            })}
          </div>
        ))}
        <div
          className="heatmapBottom"
          style={{ gridTemplateColumns: `72px repeat(${impacts.length}, minmax(44px, 1fr))` }}
        >
          <span />
          {impacts.map((impact) => (
            <span key={impact}>{formatNumber(impact, 2)}</span>
          ))}
        </div>
        <div className="heatmapAxisTitle horizontal">شدت اثر</div>
      </div>
    </div>
  );
}

export default function Home() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await apiFetch("/dashboard/management/");
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || body.message || `HTTP ${response.status}`);
      }
      setData(await response.json());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "دریافت داشبورد ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const cards = [
    {
      label: "درصد انطباق کل",
      value: data?.compliance_score == null ? "—" : `${formatNumber(data.compliance_score, 1)}٪`,
      tone: metricTone(data?.compliance_score ?? null),
      glyph: "✓",
      description: "میانگین امتیاز ارزیابی‌های دارای امتیاز",
    },
    {
      label: "ریسک‌های بالا و بحرانی",
      value: data ? formatNumber(data.high_critical_residual_risks) : "—",
      tone: data && data.high_critical_residual_risks > 0 ? "bad" : "good",
      glyph: "△",
      description: "بر اساس آخرین ارزیابی Residual هر ریسک",
    },
    {
      label: "یافته‌های باز",
      value: data ? formatNumber(data.open_findings) : "—",
      tone: "neutral",
      glyph: "!",
      description: "یافته‌های بسته یا پذیرفته‌شده حذف شده‌اند",
    },
    {
      label: "اقدامات معوق",
      value: data ? formatNumber(data.overdue_actions) : "—",
      tone: data && data.overdue_actions > 0 ? "warn" : "good",
      glyph: "◷",
      description: "اقدامات تکمیل‌نشده با سررسید گذشته",
    },
    {
      label: "کنترل‌های موثر",
      value:
        data?.effective_controls_percent == null
          ? "—"
          : `${formatNumber(data.effective_controls_percent, 1)}٪`,
      tone: metricTone(data?.effective_controls_percent ?? null),
      glyph: "◇",
      description: "درصد Effective بین کنترل‌های ارزیابی‌شده",
    },
    {
      label: "ارزیابی‌های دارای سررسید",
      value: data ? formatNumber(data.assessments_due) : "—",
      tone: "neutral",
      glyph: "▤",
      description: "ارزیابی‌های باز که تاریخ سررسید دارند",
    },
  ];

  const frameworks = data?.framework_summaries ?? [];
  const heatmap = data?.risk_heatmap ?? [];
  const topRisks = data?.top_risks ?? [];
  const attentionActions = data?.attention_actions ?? [];
  const upcomingDeadlines = data?.upcoming_deadlines ?? [];

  return (
    <main className="shell dashboardShell">
      <aside className="sidebar dashboardSidebar">
        <div className="brand dashboardBrand">
          <div className="brandMark dashboardShield">G</div>
          <div>
            <strong>GRC Platform</strong>
            <small>Governance · Risk · Compliance</small>
          </div>
        </div>
        <nav className="dashboardNav">
          {menuSections.map((section) => (
            <div className="navSection" key={section.label}>
              <span className="navSectionTitle">{section.label}</span>
              {section.items.map((item) => (
                <Link key={item.href} href={item.href} className={item.href === "/" ? "active" : ""}>
                  <span className="navGlyph" aria-hidden="true">{item.glyph}</span>
                  <span>{item.label}</span>
                </Link>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <section className="workspace dashboardWorkspace">
        <header className="topbar dashboardTopbar">
          <div className="liveStatus">
            <strong>داشبورد مدیریتی</strong>
            <small>فقط داده‌های tenant و محدوده دسترسی جاری</small>
          </div>
          <div className="topbarLinks dashboardTopbarLinks">
            <Link className="secondaryLink" href="/reports">گزارش مدیریتی</Link>
            <Link className="secondaryLink" href="/connectors">وضعیت اتصال‌ها</Link>
            <Link className="ai" href="/ai">دستیار هوشمند ✦</Link>
          </div>
        </header>

        <div className="content dashboardContent">
          <div className="titleRow dashboardTitleRow">
            <div>
              <span className="eyebrow">نمای اجرایی زنده</span>
              <h1>داشبورد</h1>
              <p>خلاصه واقعی حاکمیت، ریسک، کنترل و انطباق؛ بدون داده نمایشی یا عدد ساختگی.</p>
            </div>
            <button className="primary refreshButton" onClick={load} disabled={loading}>
              {loading ? "در حال بروزرسانی…" : "بروزرسانی داده‌ها"}
            </button>
          </div>

          {error && (
            <div className="errorBanner" role="alert">
              <strong>دریافت داشبورد ناموفق بود.</strong>
              <span>{error}</span>
            </div>
          )}

          <section className="dashboardKpis" aria-label="شاخص‌های کلیدی">
            {cards.map((card) => (
              <article key={card.label} className={`executiveKpi ${card.tone}`}>
                <div className={`executiveKpiIcon ${card.tone}`}>{card.glyph}</div>
                <div className="executiveKpiBody">
                  <span>{card.label}</span>
                  <strong>{loading ? "…" : card.value}</strong>
                  <small>{card.description}</small>
                </div>
              </article>
            ))}
          </section>

          <section className="executiveGrid topExecutiveGrid">
            <article className="dashboardPanel heatmapPanel">
              <div className="panelHead dashboardPanelHead">
                <div>
                  <h2>نقشه حرارتی ریسک</h2>
                  <small>آخرین ارزیابی Residual ریسک‌های فعال</small>
                </div>
                <Link href="/risks">مشاهده ریسک‌ها</Link>
              </div>
              {loading ? <EmptyState>در حال دریافت ریسک‌ها…</EmptyState> : <HomeHeatmap cells={heatmap} />}
            </article>

            <article className="dashboardPanel">
              <div className="panelHead dashboardPanelHead">
                <div>
                  <h2>انطباق بر اساس چارچوب</h2>
                  <small>میانگین ارزیابی‌های واقعی هر نسخه</small>
                </div>
                <Link href="/frameworks">همه چارچوب‌ها</Link>
              </div>
              {!loading && frameworks.length === 0 ? (
                <EmptyState>هنوز ارزیابی دارای چارچوب ثبت نشده است.</EmptyState>
              ) : (
                <div className="frameworkSummaryList">
                  {frameworks.map((framework, index) => (
                    <div className="frameworkSummaryRow" key={framework.framework_version_id}>
                      <div className="frameworkSummaryMeta">
                        <strong>{framework.framework_name}</strong>
                        <small>{framework.version_code}</small>
                      </div>
                      <ProgressBar value={framework.average_score} tone={`tone${index % 5}`} />
                      <b>{framework.average_score == null ? "—" : `${formatNumber(framework.average_score, 1)}٪`}</b>
                    </div>
                  ))}
                </div>
              )}
            </article>

            <article className="dashboardPanel">
              <div className="panelHead dashboardPanelHead">
                <div>
                  <h2>پیشرفت ارزیابی‌ها</h2>
                  <small>پیشرفت و وضعیت واقعی Assessmentها</small>
                </div>
                <Link href="/assessments">همه ارزیابی‌ها</Link>
              </div>
              {!loading && frameworks.length === 0 ? (
                <EmptyState>داده‌ای برای پیشرفت ارزیابی‌ها وجود ندارد.</EmptyState>
              ) : (
                <div className="assessmentProgressList">
                  {frameworks.map((framework) => (
                    <div className="assessmentProgressRow" key={framework.framework_version_id}>
                      <div className="assessmentProgressTitle">
                        <strong>{framework.framework_name}</strong>
                        <span>{formatNumber(framework.average_progress, 1)}٪</span>
                      </div>
                      <ProgressBar value={framework.average_progress} />
                      <div className="assessmentStatusMini">
                        <span className="statusDot done" />
                        {formatNumber(framework.completed_count)} تکمیل
                        <span className="statusDot active" />
                        {formatNumber(framework.in_progress_count)} در جریان
                        <span className="statusDot draft" />
                        {formatNumber(framework.draft_count)} پیش‌نویس
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>
          </section>

          <section className="executiveGrid lowerExecutiveGrid">
            <article className="dashboardPanel">
              <div className="panelHead dashboardPanelHead">
                <h2>ریسک‌های برتر</h2>
                <Link href="/risks">مشاهده همه</Link>
              </div>
              {!loading && topRisks.length === 0 ? (
                <EmptyState>ریسک Residual ارزیابی‌شده‌ای وجود ندارد.</EmptyState>
              ) : (
                <div className="dashboardTableWrap">
                  <table className="dashboardTable">
                    <thead>
                      <tr>
                        <th>شناسه</th>
                        <th>عنوان ریسک</th>
                        <th>سطح</th>
                        <th>مالک</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topRisks.map((risk) => (
                        <tr key={risk.id}>
                          <td><Link href={`/risks/${risk.id}`}>{risk.code}</Link></td>
                          <td>{risk.title}</td>
                          <td><span className={`riskLevel ${risk.level}`}>{formatSeverity(risk.level)}</span></td>
                          <td>{risk.owner}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </article>

            <article className="dashboardPanel">
              <div className="panelHead dashboardPanelHead">
                <h2>اقدامات نیازمند توجه</h2>
                <Link href="/actions">مشاهده همه</Link>
              </div>
              {!loading && attentionActions.length === 0 ? (
                <EmptyState>اقدام بازی در محدوده دسترسی فعلی وجود ندارد.</EmptyState>
              ) : (
                <div className="dashboardTableWrap">
                  <table className="dashboardTable">
                    <thead>
                      <tr>
                        <th>اقدام</th>
                        <th>منبع</th>
                        <th>سررسید</th>
                        <th>وضعیت</th>
                      </tr>
                    </thead>
                    <tbody>
                      {attentionActions.map((action) => (
                        <tr key={action.id}>
                          <td>{action.title}</td>
                          <td>{sourceLabels[action.source_type] ?? (action.source_type || "—")}</td>
                          <td className={action.is_overdue ? "overdueText" : ""}>{formatDate(action.due_date)}</td>
                          <td><span className={`actionStatus ${action.is_overdue ? "overdue" : action.status}`}>{action.is_overdue ? "معوق" : actionStatusLabels[action.status] ?? action.status}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </article>

            <article className="dashboardPanel deadlinesPanel">
              <div className="panelHead dashboardPanelHead">
                <h2>رویدادها و سررسیدهای پیش رو</h2>
                <span className="pill">{formatNumber(upcomingDeadlines.length)} مورد</span>
              </div>
              {!loading && upcomingDeadlines.length === 0 ? (
                <EmptyState>سررسید آینده‌ای در داده‌های جاری ثبت نشده است.</EmptyState>
              ) : (
                <div className="deadlineList">
                  {upcomingDeadlines.map((deadline, index) => (
                    <Link className="deadlineItem" href={deadline.href} key={`${deadline.type}-${deadline.date}-${index}`}>
                      <div className="deadlineDate">
                        <strong>{formatDate(deadline.date)}</strong>
                        <small>{deadlineTypeLabels[deadline.type] ?? deadline.type}</small>
                      </div>
                      <div>
                        <strong>{deadline.title}</strong>
                        <small>{deadline.subtitle}</small>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </article>
          </section>

          <section className="dashboardPanel dashboardOperations">
            <div className="panelHead dashboardPanelHead">
              <div>
                <h2>عملیات Pilot / RC</h2>
                <small>میان‌بر به مسیرهای عملیاتی واقعی محصول</small>
              </div>
            </div>
            <div className="operationsLinks executiveOperationsLinks">
              <Link href="/connectors">Connector Health & Sync</Link>
              <Link href="/reports">گزارش مدیریتی</Link>
              <Link href="/control-tests">آزمون کنترل‌ها</Link>
              <Link href="/frameworks/crosswalk">Crosswalk چارچوب‌ها</Link>
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}