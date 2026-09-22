"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { apiFetch } from "../../lib/api";

type Eval = { score: string; level: string };
type Risk = {
  id: string;
  code: string;
  title: string;
  organization_name?: string;
  owner_display: string;
  status: string;
  latest_evaluations: Record<string, Eval>;
};
type Unit = { id: string; name: string };
type User = {
  id: number;
  username: string;
  first_name?: string;
  last_name?: string;
  membership_active?: boolean;
};
type Asset = { id: string; title: string; organization_unit?: string | null };
type RiskForm = {
  code: string;
  title: string;
  scenario: string;
  cause: string;
  consequence: string;
  organization_unit: string;
  asset: string;
  owner: string;
  review_date: string;
};

const emptyForm: RiskForm = {
  code: "",
  title: "",
  scenario: "",
  cause: "",
  consequence: "",
  organization_unit: "",
  asset: "",
  owner: "",
  review_date: "",
};

function unpack<T>(body: T[] | { results?: T[] }): T[] {
  return Array.isArray(body) ? body : body.results ?? [];
}

function apiError(payload: unknown, fallback: string) {
  if (typeof payload === "string" && payload.trim()) return payload;
  if (!payload || typeof payload !== "object") return fallback;
  const record = payload as Record<string, unknown>;
  for (const key of ["detail", "message", "error"]) {
    if (typeof record[key] === "string" && record[key]) return record[key] as string;
  }
  const parts = Object.entries(record).flatMap(([field, value]) => {
    if (Array.isArray(value)) return value.map(item => `${field}: ${String(item)}`);
    if (typeof value === "string") return [`${field}: ${value}`];
    return [];
  });
  return parts.length ? parts.join(" • ") : fallback;
}

function userLabel(user: User) {
  const fullName = `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim();
  return fullName ? `${fullName} (${user.username})` : user.username;
}

export default function RisksPage() {
  const [rows, setRows] = useState<Risk[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [form, setForm] = useState<RiskForm>(emptyForm);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [msg, setMsg] = useState("");
  const [search, setSearch] = useState("");

  async function load() {
    setLoading(true);
    setLoadError("");
    const [riskRes, unitRes, userRes, assetRes] = await Promise.all([
      apiFetch(`/risks/?search=${encodeURIComponent(search)}`),
      apiFetch("/organization-units/?page_size=200"),
      apiFetch("/tenant-users/"),
      apiFetch("/assets/?page_size=200"),
    ]);

    if (riskRes.ok) {
      const body = (await riskRes.json()) as Risk[] | { results?: Risk[] };
      setRows(unpack(body));
    } else {
      setLoadError("بارگذاری فهرست ریسک‌ها ناموفق بود.");
    }

    const referenceFailures: string[] = [];
    if (unitRes.ok) {
      const body = (await unitRes.json()) as Unit[] | { results?: Unit[] };
      setUnits(unpack(body));
    } else referenceFailures.push("ساختار سازمانی");

    if (userRes.ok) {
      const body = (await userRes.json()) as User[] | { results?: User[] };
      setUsers(unpack(body).filter(user => user.membership_active !== false));
    } else referenceFailures.push("کاربران Tenant");

    if (assetRes.ok) {
      const body = (await assetRes.json()) as Asset[] | { results?: Asset[] };
      setAssets(unpack(body));
    } else referenceFailures.push("دارایی‌ها");

    if (referenceFailures.length) {
      setLoadError(current => [current, `داده مرجع قابل بارگذاری نیست: ${referenceFailures.join("، ")}.`].filter(Boolean).join(" "));
    }
    setLoading(false);
  }

  useEffect(() => {
    void load();
    // Initial tenant-scoped load only; search is submitted explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visibleAssets = useMemo(
    () => form.organization_unit
      ? assets.filter(asset => asset.organization_unit === form.organization_unit)
      : assets.filter(asset => !asset.organization_unit),
    [assets, form.organization_unit],
  );

  const referencesReady = users.length > 0 && !loadError.includes("داده مرجع قابل بارگذاری نیست");

  function update<K extends keyof RiskForm>(key: K, value: RiskForm[K]) {
    setForm(current => ({ ...current, [key]: value }));
  }

  function changeScope(value: string) {
    setForm(current => ({ ...current, organization_unit: value, asset: "" }));
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMsg("");
    if (!referencesReady) {
      setMsg("برای ثبت ریسک ابتدا داده‌های مرجع صفحه را بدون خطا بارگذاری کنید و حداقل یک کاربر فعال داشته باشید.");
      return;
    }
    if (!form.code.trim() || !form.title.trim() || !form.owner) {
      setMsg("کد، عنوان و مالک ریسک الزامی هستند.");
      return;
    }

    setSaving(true);
    const response = await apiFetch("/risks/", {
      method: "POST",
      body: JSON.stringify({
        organization_unit: form.organization_unit || null,
        asset: form.asset || null,
        category: null,
        code: form.code.trim(),
        title: form.title.trim(),
        scenario: form.scenario.trim(),
        cause: form.cause.trim(),
        consequence: form.consequence.trim(),
        owner: Number(form.owner),
        status: "open",
        review_date: form.review_date || null,
        metadata: {},
      }),
    });

    if (response.ok) {
      setMsg("ریسک ثبت شد.");
      setForm(emptyForm);
      setShowCreate(false);
      await load();
    } else {
      const body = await response.json().catch(() => null) as unknown;
      setMsg(apiError(body, "ثبت ریسک ناموفق بود."));
    }
    setSaving(false);
  }

  return (
    <main className="adminPage">
      <div className="pageHead">
        <div>
          <Link href="/">← داشبورد</Link>
          <h1>Risk Register</h1>
          <p>Inherent، Residual و Target Risk با تاریخچه کامل</p>
        </div>
        <div className="headActions">
          <Link className="secondaryLink" href="/risks/methodologies">روش ارزیابی</Link>
          <button className="primary" type="button" onClick={() => setShowCreate(value => !value)}>
            {showCreate ? "بستن فرم" : "+ ریسک جدید"}
          </button>
        </div>
      </div>

      {msg && <p className="message">{msg}</p>}
      {loadError && <p className="message">{loadError}</p>}

      {showCreate && (
        <section className="panel" style={{ marginBottom: 20 }}>
          <h2>ثبت ریسک جدید</h2>
          {!referencesReady && (
            <p className="message">برای ثبت ریسک، کاربران فعال و داده‌های مرجع باید قابل دسترس باشند.</p>
          )}
          <form className="settingsForm" onSubmit={create}>
            <label>
              کد ریسک *
              <input dir="ltr" value={form.code} onChange={event => update("code", event.target.value)} placeholder="RISK-001" maxLength={80} />
            </label>
            <label>
              عنوان ریسک *
              <input value={form.title} onChange={event => update("title", event.target.value)} placeholder="عنوان روشن و قابل پیگیری" maxLength={255} />
            </label>
            <label>
              دامنه سازمانی
              <select value={form.organization_unit} onChange={event => changeScope(event.target.value)}>
                <option value="">کل سازمان</option>
                {units.map(unit => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
              </select>
            </label>
            <label>
              دارایی مرتبط (اختیاری)
              <select value={form.asset} onChange={event => update("asset", event.target.value)}>
                <option value="">بدون دارایی مشخص</option>
                {visibleAssets.map(asset => <option key={asset.id} value={asset.id}>{asset.title}</option>)}
              </select>
            </label>
            <label>
              مالک ریسک *
              <select value={form.owner} onChange={event => update("owner", event.target.value)}>
                <option value="">انتخاب مالک...</option>
                {users.map(user => <option key={user.id} value={String(user.id)}>{userLabel(user)}</option>)}
              </select>
            </label>
            <label>
              سناریوی ریسک
              <textarea style={{ minHeight: 88, border: "1px solid #cad7e4", borderRadius: 8, padding: 10 }} value={form.scenario} onChange={event => update("scenario", event.target.value)} placeholder="چه رویدادی ممکن است رخ دهد؟" />
            </label>
            <label>
              علت
              <textarea style={{ minHeight: 72, border: "1px solid #cad7e4", borderRadius: 8, padding: 10 }} value={form.cause} onChange={event => update("cause", event.target.value)} placeholder="علت یا محرک ریسک" />
            </label>
            <label>
              پیامد
              <textarea style={{ minHeight: 72, border: "1px solid #cad7e4", borderRadius: 8, padding: 10 }} value={form.consequence} onChange={event => update("consequence", event.target.value)} placeholder="پیامد کسب‌وکاری یا کنترلی" />
            </label>
            <label>
              تاریخ بازنگری
              <input dir="ltr" type="date" value={form.review_date} onChange={event => update("review_date", event.target.value)} />
            </label>
            <div className="headActions">
              <button className="primary" type="submit" disabled={saving || !referencesReady}>{saving ? "در حال ثبت..." : "ثبت ریسک"}</button>
              <button type="button" onClick={() => { setForm(emptyForm); setShowCreate(false); }}>انصراف</button>
            </div>
          </form>
        </section>
      )}

      <div className="toolbar">
        <input value={search} onChange={event => setSearch(event.target.value)} onKeyDown={event => { if (event.key === "Enter") void load(); }} placeholder="جستجو در ریسک‌ها..." />
        <button type="button" onClick={() => void load()} disabled={loading}>{loading ? "در حال بارگذاری..." : "جستجو"}</button>
      </div>

      <section className="panel">
        {loading ? <p className="muted">در حال بارگذاری Risk Register...</p> : rows.length === 0 ? <p className="muted">ریسکی در این دامنه ثبت نشده است.</p> : (
          <table className="dataTable">
            <thead><tr><th>کد</th><th>ریسک</th><th>واحد</th><th>مالک</th><th>Inherent</th><th>Residual</th><th>Target</th><th>وضعیت</th></tr></thead>
            <tbody>{rows.map(risk => (
              <tr key={risk.id}>
                <td><Link href={`/risks/${risk.id}`}>{risk.code}</Link></td>
                <td>{risk.title}</td>
                <td>{risk.organization_name || "کل سازمان"}</td>
                <td>{risk.owner_display}</td>
                <td><RiskCell x={risk.latest_evaluations?.inherent} /></td>
                <td><RiskCell x={risk.latest_evaluations?.residual} /></td>
                <td><RiskCell x={risk.latest_evaluations?.target} /></td>
                <td><span className="pill">{risk.status}</span></td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </section>
    </main>
  );
}

function RiskCell({ x }: { x?: Eval }) {
  if (!x) return <span className="muted">—</span>;
  return <span className={`riskLevel ${x.level}`}>{x.score} · {x.level}</span>;
}
