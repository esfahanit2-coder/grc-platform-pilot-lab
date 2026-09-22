"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { apiFetch } from "../../lib/api";

type Row = {
  id: string;
  title: string;
  framework_name: string;
  version_code: string;
  organization_name?: string;
  owner_display: string;
  progress_percent: string;
  overall_score?: string;
  status: string;
};
type Version = { id: string; framework_name: string; version_code: string; status: string };
type Unit = { id: string; name: string };
type User = {
  id: number;
  username: string;
  first_name?: string;
  last_name?: string;
  membership_active?: boolean;
};
type AssessmentForm = {
  title: string;
  framework_version: string;
  organization_unit: string;
  owner: string;
  assessment_type: "compliance" | "maturity" | "internal" | "self";
  start_date: string;
  due_date: string;
};

const emptyForm: AssessmentForm = {
  title: "",
  framework_version: "",
  organization_unit: "",
  owner: "",
  assessment_type: "compliance",
  start_date: "",
  due_date: "",
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

export default function Assessments() {
  const [rows, setRows] = useState<Row[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [form, setForm] = useState<AssessmentForm>(emptyForm);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    setLoading(true);
    setLoadError("");
    const [assessmentRes, versionRes, unitRes, userRes] = await Promise.all([
      apiFetch("/assessments/"),
      apiFetch("/framework-versions/?page_size=200"),
      apiFetch("/organization-units/?page_size=200"),
      apiFetch("/tenant-users/"),
    ]);

    if (assessmentRes.ok) {
      const body = (await assessmentRes.json()) as Row[] | { results?: Row[] };
      setRows(unpack(body));
    } else {
      setLoadError("بارگذاری فهرست ارزیابی‌ها ناموفق بود.");
    }

    const referenceFailures: string[] = [];
    if (versionRes.ok) {
      const body = (await versionRes.json()) as Version[] | { results?: Version[] };
      setVersions(unpack(body).filter(version => version.status === "active"));
    } else referenceFailures.push("Framework Versionها");

    if (unitRes.ok) {
      const body = (await unitRes.json()) as Unit[] | { results?: Unit[] };
      setUnits(unpack(body));
    } else referenceFailures.push("ساختار سازمانی");

    if (userRes.ok) {
      const body = (await userRes.json()) as User[] | { results?: User[] };
      setUsers(unpack(body).filter(user => user.membership_active !== false));
    } else referenceFailures.push("کاربران Tenant");

    if (referenceFailures.length) {
      setLoadError(current => [current, `داده مرجع قابل بارگذاری نیست: ${referenceFailures.join("، ")}.`].filter(Boolean).join(" "));
    }
    setLoading(false);
  }

  useEffect(() => {
    void load();
    // Initial tenant-scoped load only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const referencesReady = versions.length > 0 && users.length > 0 && !loadError.includes("داده مرجع قابل بارگذاری نیست");

  function update<K extends keyof AssessmentForm>(key: K, value: AssessmentForm[K]) {
    setForm(current => ({ ...current, [key]: value }));
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMsg("");
    if (!referencesReady) {
      setMsg("برای ساخت ارزیابی حداقل یک Framework فعال و یک کاربر فعال لازم است و داده‌های مرجع باید بدون خطا بارگذاری شوند.");
      return;
    }
    if (!form.title.trim() || !form.framework_version || !form.owner) {
      setMsg("عنوان، Framework Version و مالک ارزیابی الزامی هستند.");
      return;
    }
    if (form.start_date && form.due_date && form.due_date < form.start_date) {
      setMsg("تاریخ سررسید نمی‌تواند قبل از تاریخ شروع باشد.");
      return;
    }

    setSaving(true);
    const response = await apiFetch("/assessments/", {
      method: "POST",
      body: JSON.stringify({
        framework_version: form.framework_version,
        organization_unit: form.organization_unit || null,
        title: form.title.trim(),
        assessment_type: form.assessment_type,
        owner: Number(form.owner),
        start_date: form.start_date || null,
        due_date: form.due_date || null,
        metadata: {},
      }),
    });

    if (response.ok) {
      setMsg("ارزیابی ساخته شد و Requirementها Snapshot شدند.");
      setForm(emptyForm);
      setShowCreate(false);
      await load();
    } else {
      const body = await response.json().catch(() => null) as unknown;
      setMsg(apiError(body, "ساخت ارزیابی ناموفق بود."));
    }
    setSaving(false);
  }

  return (
    <main className="adminPage">
      <div className="pageHead">
        <div>
          <Link href="/">← داشبورد</Link>
          <h1>ارزیابی و انطباق</h1>
          <p>Framework Assessment با Snapshot تاریخی و امتیاز انطباق</p>
        </div>
        <button className="primary" type="button" onClick={() => setShowCreate(value => !value)}>
          {showCreate ? "بستن فرم" : "+ ارزیابی جدید"}
        </button>
      </div>

      {msg && <p className="message">{msg}</p>}
      {loadError && <p className="message">{loadError}</p>}

      {showCreate && (
        <section className="panel" style={{ marginBottom: 20 }}>
          <h2>ارزیابی جدید</h2>
          {versions.length === 0 && !loading && <p className="message">هیچ Framework Version فعالی برای ارزیابی وجود ندارد.</p>}
          {users.length === 0 && !loading && <p className="message">هیچ کاربر فعال Tenant برای مالکیت ارزیابی وجود ندارد.</p>}
          <form className="settingsForm" onSubmit={create}>
            <label>
              عنوان ارزیابی *
              <input value={form.title} onChange={event => update("title", event.target.value)} placeholder="مثلاً ارزیابی انطباق ISMS - پاییز" maxLength={255} />
            </label>
            <label>
              Framework Version *
              <select value={form.framework_version} onChange={event => update("framework_version", event.target.value)}>
                <option value="">انتخاب Framework...</option>
                {versions.map(version => (
                  <option key={version.id} value={version.id}>{version.framework_name} · {version.version_code}</option>
                ))}
              </select>
            </label>
            <label>
              نوع ارزیابی
              <select value={form.assessment_type} onChange={event => update("assessment_type", event.target.value as AssessmentForm["assessment_type"])}>
                <option value="compliance">Compliance / انطباق</option>
                <option value="maturity">Maturity / بلوغ</option>
                <option value="internal">Internal / داخلی</option>
                <option value="self">Self Assessment / خودارزیابی</option>
              </select>
            </label>
            <label>
              دامنه سازمانی
              <select value={form.organization_unit} onChange={event => update("organization_unit", event.target.value)}>
                <option value="">کل سازمان</option>
                {units.map(unit => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
              </select>
            </label>
            <label>
              مالک ارزیابی *
              <select value={form.owner} onChange={event => update("owner", event.target.value)}>
                <option value="">انتخاب مالک...</option>
                {users.map(user => <option key={user.id} value={String(user.id)}>{userLabel(user)}</option>)}
              </select>
            </label>
            <label>
              تاریخ شروع
              <input dir="ltr" type="date" value={form.start_date} onChange={event => update("start_date", event.target.value)} />
            </label>
            <label>
              تاریخ سررسید
              <input dir="ltr" type="date" value={form.due_date} onChange={event => update("due_date", event.target.value)} />
            </label>
            <div className="headActions">
              <button className="primary" type="submit" disabled={saving || !referencesReady}>{saving ? "در حال ساخت..." : "ساخت ارزیابی"}</button>
              <button type="button" onClick={() => { setForm(emptyForm); setShowCreate(false); }}>انصراف</button>
            </div>
          </form>
        </section>
      )}

      <section className="panel">
        {loading ? <p className="muted">در حال بارگذاری ارزیابی‌ها...</p> : rows.length === 0 ? <p className="muted">هنوز ارزیابی‌ای در این Tenant ثبت نشده است.</p> : (
          <table className="dataTable">
            <thead><tr><th>عنوان</th><th>چارچوب</th><th>دامنه</th><th>مالک</th><th>پیشرفت</th><th>انطباق</th><th>وضعیت</th></tr></thead>
            <tbody>{rows.map(row => (
              <tr key={row.id}>
                <td><Link href={`/assessments/${row.id}`}>{row.title}</Link></td>
                <td>{row.framework_name} · {row.version_code}</td>
                <td>{row.organization_name || "کل سازمان"}</td>
                <td>{row.owner_display}</td>
                <td>{Number(row.progress_percent).toFixed(0)}%</td>
                <td>{row.overall_score ? `${Number(row.overall_score).toFixed(1)}%` : "—"}</td>
                <td><span className="pill">{row.status}</span></td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </section>
    </main>
  );
}
