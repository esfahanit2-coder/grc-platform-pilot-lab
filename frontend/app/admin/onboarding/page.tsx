"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../../lib/api";

type Unit = { id: string; status: string };
type Assignment = { id: string };
type User = { id: number; membership_active: boolean; role_assignments: Assignment[] };
type Role = { id: string; is_system: boolean; is_active: boolean };
type Security = { require_mfa: boolean; password_min_length: number; session_minutes: number };

type Readiness = {
  units: number;
  activeUsers: number;
  assignments: number;
  customRoles: number;
  security: Security | null;
};

function rows<T>(body: T[] | { results?: T[] }): T[] {
  return Array.isArray(body) ? body : body.results ?? [];
}

function apiError(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const object = body as Record<string, unknown>;
  if (typeof object.detail === "string") return object.detail;
  return fallback;
}

export default function OnboardingPage() {
  const [data, setData] = useState<Readiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [unitResponse, userResponse, roleResponse, securityResponse] = await Promise.all([
        apiFetch("/organization-units/?page_size=500"),
        apiFetch("/tenant-users/?include_inactive=true"),
        apiFetch("/roles/?page_size=200"),
        apiFetch("/tenant/security"),
      ]);
      const [unitBody, userBody, roleBody, securityBody] = await Promise.all([
        unitResponse.json().catch(() => ({})),
        userResponse.json().catch(() => ({})),
        roleResponse.json().catch(() => ({})),
        securityResponse.json().catch(() => ({})),
      ]);
      if (!unitResponse.ok) throw new Error(apiError(unitBody, "ساختار سازمانی قابل خواندن نیست."));
      if (!userResponse.ok) throw new Error(apiError(userBody, "فهرست کاربران قابل خواندن نیست."));
      if (!roleResponse.ok) throw new Error(apiError(roleBody, "Roleهای Tenant قابل خواندن نیستند."));
      if (!securityResponse.ok) throw new Error(apiError(securityBody, "تنظیمات امنیتی Tenant قابل خواندن نیست."));

      const units = rows<Unit>(unitBody).filter((unit) => unit.status !== "archived");
      const users = rows<User>(userBody);
      const roles = rows<Role>(roleBody);
      setData({
        units: units.length,
        activeUsers: users.filter((user) => user.membership_active).length,
        assignments: users.reduce((count, user) => count + (user.role_assignments?.length ?? 0), 0),
        customRoles: roles.filter((role) => role.is_active && !role.is_system).length,
        security: securityBody as Security,
      });
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "محاسبه وضعیت راه‌اندازی ناموفق بود.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const steps = useMemo(() => {
    const security = data?.security;
    return [
      {
        title: "۱. ساختار سازمانی",
        done: Boolean(data && data.units > 0),
        detail: data ? `${data.units} واحد فعال/قابل استفاده ثبت شده است.` : "—",
        href: "/organization",
        action: "مدیریت ساختار",
      },
      {
        title: "۲. کاربران Tenant",
        done: Boolean(data && data.activeUsers > 0),
        detail: data ? `${data.activeUsers} عضویت فعال وجود دارد.` : "—",
        href: "/admin/users",
        action: "مدیریت کاربران",
      },
      {
        title: "۳. Role و Scope",
        done: Boolean(data && data.assignments > 0),
        detail: data ? `${data.assignments} Role Assignment فعال است؛ ${data.customRoles} Custom Role نیز تعریف شده.` : "—",
        href: "/admin/users",
        action: "تخصیص دسترسی",
      },
      {
        title: "۴. سیاست امنیت Tenant",
        done: Boolean(security && security.password_min_length >= 10 && security.session_minutes >= 5),
        detail: security
          ? `MFA: ${security.require_mfa ? "اجباری" : "اختیاری"} · حداقل رمز: ${security.password_min_length} · نشست: ${security.session_minutes} دقیقه`
          : "—",
        href: "/settings/security",
        action: "تنظیم امنیت",
      },
    ];
  }, [data]);

  const completed = steps.filter((step) => step.done).length;

  return (
    <main className="adminPage">
      <div className="pageHead">
        <div>
          <Link href="/">← داشبورد</Link>
          <h1>راه‌اندازی Tenant</h1>
          <p>چک‌لیست عملیاتی برای آماده‌سازی ساختار، اعضا، Scopeها و سیاست امنیتی</p>
        </div>
        <div className="headActions">
          <button type="button" onClick={() => void load()} disabled={loading}>به‌روزرسانی وضعیت</button>
          <Link href="/work" className="secondaryLink">کارهای من</Link>\n          <Link href="/admin/data-exchange" className="secondaryLink">ورود/خروج داده</Link>
        </div>
      </div>

      {error && <div className="message">{error}</div>}
      {loading ? <div className="panel"><p className="muted">در حال ارزیابی وضعیت Tenant…</p></div> : (
        <>
          <div className="kpis" style={{ marginBottom: 18 }}>
            <article className={`kpi ${completed === steps.length ? "good" : "warn"}`}><span>مراحل آماده</span><strong>{completed}/{steps.length}</strong><small>این شاخص فقط onboarding نرم‌افزاری Tenant است؛ معادل Pilot/Production acceptance نیست.</small></article>
            <article className="kpi"><span>واحد سازمانی</span><strong>{data?.units ?? 0}</strong><small>Scopeهای فعال</small></article>
            <article className="kpi"><span>کاربر فعال</span><strong>{data?.activeUsers ?? 0}</strong><small>عضویت‌های فعال Tenant</small></article>
            <article className="kpi"><span>Role Assignment</span><strong>{data?.assignments ?? 0}</strong><small>دسترسی‌های فعال و صریح</small></article>
          </div>

          <div className="cardsList">
            {steps.map((step) => (
              <article className="panel" key={step.title}>
                <div className="roleTitle">
                  <h2>{step.title}</h2>
                  <span className="pill">{step.done ? "آماده" : "نیازمند اقدام"}</span>
                </div>
                <p className="muted">{step.detail}</p>
                <Link className={step.done ? "secondaryLink" : "primary linkButton"} href={step.href}>{step.action}</Link>
              </article>
            ))}
          </div>

          <section className="panel" style={{ marginTop: 18 }}>
            <h2>مرز این صفحه</h2>
            <p className="muted">این صفحه هیچ Flag جدیدی برای «آماده بودن» ذخیره نمی‌کند. وضعیت از رکوردهای authoritative همان لحظه محاسبه می‌شود و درباره clean-host، DR، live connector، محتوای دارای مجوز یا pentest ادعای PASS ندارد.</p>
          </section>
        </>
      )}
    </main>
  );
}
