"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { apiFetch } from "../../lib/api";

type EvidenceMetadata = {
  malware_scan_required?: boolean;
  malware_scan_status?: string;
  malware_scan_scanner?: string;
  malware_scan_signature?: string;
  malware_scan_error_code?: string;
  malware_scan_scanned_at?: string;
};

type Row = {
  id: string;
  title: string;
  description?: string;
  evidence_type: string;
  source?: string;
  organization_name?: string;
  owner_display: string;
  collected_at?: string | null;
  valid_until?: string | null;
  classification: string;
  original_filename?: string;
  mime_type?: string;
  size: number;
  sha256: string;
  url?: string;
  text_content?: string;
  metadata?: EvidenceMetadata;
  links_count: number;
};

type Unit = { id: string; name: string };
type User = {
  id: number;
  username: string;
  first_name?: string;
  last_name?: string;
  membership_active?: boolean;
};
type EvidenceForm = {
  title: string;
  description: string;
  evidence_type: "file" | "text" | "url";
  source: string;
  organization_unit: string;
  owner: string;
  classification: "public" | "internal" | "confidential" | "secret";
  collected_at: string;
  valid_until: string;
  url: string;
  text_content: string;
};

const emptyForm: EvidenceForm = {
  title: "",
  description: "",
  evidence_type: "file",
  source: "",
  organization_unit: "",
  owner: "",
  classification: "internal",
  collected_at: "",
  valid_until: "",
  url: "",
  text_content: "",
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

function typeLabel(value: string) {
  const labels: Record<string, string> = {
    file: "فایل",
    url: "URL",
    text: "متن",
    screenshot: "Screenshot",
    report: "گزارش",
    log: "Log",
    configuration: "Configuration",
    other: "سایر",
  };
  return labels[value] ?? value;
}

function scanLabel(row: Row) {
  if (!row.original_filename) return "غیرفایلی";
  const status = String(row.metadata?.malware_scan_status || "not_scanned").toLowerCase();
  const labels: Record<string, string> = {
    clean: "پاک / مجاز",
    pending: "در صف اسکن",
    scanning: "در حال اسکن",
    infected: "آلوده / قرنطینه",
    error: "خطای اسکن",
    not_scanned: "اسکن نشده",
  };
  return labels[status] ?? status;
}

function dateLabel(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function validityLabel(value?: string | null) {
  if (!value) return "بدون انقضا";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.getTime() < Date.now() ? `منقضی · ${dateLabel(value)}` : `معتبر تا ${dateLabel(value)}`;
}

function formatBytes(value: number) {
  if (!Number.isFinite(value) || value <= 0) return "—";
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(1)} GB`;
}

function toIso(value: string) {
  return value ? new Date(value).toISOString() : "";
}

export default function EvidencePage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [form, setForm] = useState<EvidenceForm>(emptyForm);
  const [file, setFile] = useState<File | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState("");
  const [search, setSearch] = useState("");
  const [classification, setClassification] = useState("");
  const [loadError, setLoadError] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    setLoading(true);
    setLoadError("");
    const params = new URLSearchParams();
    if (search.trim()) params.set("search", search.trim());
    if (classification) params.set("classification", classification);
    const query = params.toString();
    const [evidenceRes, unitRes, userRes] = await Promise.all([
      apiFetch(`/evidence/${query ? `?${query}` : ""}`),
      apiFetch("/organization-units/?page_size=200"),
      apiFetch("/tenant-users/"),
    ]);

    if (evidenceRes.ok) {
      const body = (await evidenceRes.json()) as Row[] | { results?: Row[] };
      setRows(unpack(body));
    } else {
      setLoadError("بارگذاری Evidence Library ناموفق بود.");
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

    if (referenceFailures.length) {
      setLoadError(current => [current, `داده مرجع قابل بارگذاری نیست: ${referenceFailures.join("، ")}.`].filter(Boolean).join(" "));
    }
    setLoading(false);
  }

  useEffect(() => {
    void load();
    // Initial tenant-scoped load only; filters are submitted explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const referencesReady = users.length > 0 && !loadError.includes("داده مرجع قابل بارگذاری نیست");

  function update<K extends keyof EvidenceForm>(key: K, value: EvidenceForm[K]) {
    setForm(current => ({ ...current, [key]: value }));
  }

  function resetCreate() {
    setForm(emptyForm);
    setFile(null);
    setShowCreate(false);
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMsg("");
    if (!referencesReady) {
      setMsg("برای ثبت Evidence ابتدا داده‌های مرجع صفحه را بدون خطا بارگذاری کنید و حداقل یک کاربر فعال داشته باشید.");
      return;
    }
    if (!form.title.trim() || !form.owner) {
      setMsg("عنوان و مالک Evidence الزامی هستند.");
      return;
    }
    if (form.valid_until && form.collected_at && new Date(form.valid_until) < new Date(form.collected_at)) {
      setMsg("تاریخ اعتبار نمی‌تواند قبل از زمان جمع‌آوری Evidence باشد.");
      return;
    }
    if (form.evidence_type === "file" && !file) {
      setMsg("برای Evidence نوع فایل، انتخاب فایل الزامی است.");
      return;
    }
    if (form.evidence_type === "url" && !form.url.trim()) {
      setMsg("برای Evidence نوع URL، آدرس منبع الزامی است.");
      return;
    }
    if (form.evidence_type === "text" && !form.text_content.trim()) {
      setMsg("برای Evidence متنی، محتوای Evidence الزامی است.");
      return;
    }

    setSaving(true);
    let response: Response;
    if (form.evidence_type === "file") {
      const body = new FormData();
      body.append("title", form.title.trim());
      body.append("description", form.description.trim());
      body.append("evidence_type", "file");
      body.append("source", form.source.trim());
      body.append("owner", form.owner);
      body.append("classification", form.classification);
      if (form.organization_unit) body.append("organization_unit", form.organization_unit);
      if (form.collected_at) body.append("collected_at", toIso(form.collected_at));
      if (form.valid_until) body.append("valid_until", toIso(form.valid_until));
      if (file) body.append("file", file);
      response = await apiFetch("/evidence/", { method: "POST", body });
    } else {
      response = await apiFetch("/evidence/", {
        method: "POST",
        body: JSON.stringify({
          organization_unit: form.organization_unit || null,
          title: form.title.trim(),
          description: form.description.trim(),
          evidence_type: form.evidence_type,
          source: form.source.trim(),
          owner: Number(form.owner),
          collected_at: form.collected_at ? toIso(form.collected_at) : null,
          valid_until: form.valid_until ? toIso(form.valid_until) : null,
          classification: form.classification,
          url: form.evidence_type === "url" ? form.url.trim() : "",
          text_content: form.evidence_type === "text" ? form.text_content.trim() : "",
        }),
      });
    }

    if (response.ok) {
      setMsg(form.evidence_type === "file" ? "Evidence ثبت و برای پردازش امنیتی ارسال شد." : "Evidence ثبت شد.");
      resetCreate();
      await load();
    } else {
      const body = await response.json().catch(() => null) as unknown;
      setMsg(apiError(body, "ثبت Evidence ناموفق بود."));
    }
    setSaving(false);
  }

  async function download(row: Row) {
    setDownloading(row.id);
    setMsg("");
    const response = await apiFetch(`/evidence/${row.id}/download/`);
    const body = await response.json().catch(() => null) as unknown;
    if (!response.ok) {
      setMsg(apiError(body, "دانلود Evidence مجاز یا در دسترس نیست."));
      setDownloading("");
      return;
    }
    const record = body && typeof body === "object" ? body as Record<string, unknown> : {};
    if (typeof record.url !== "string" || !record.url) {
      setMsg("Backend لینک دانلود معتبر برنگرداند.");
      setDownloading("");
      return;
    }
    const anchor = document.createElement("a");
    anchor.href = record.url;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setDownloading("");
  }

  return (
    <main className="adminPage">
      <div className="pageHead">
        <div>
          <Link href="/">← داشبورد</Link>
          <h1>Evidence Library</h1>
          <p>شواهد قابل استفاده مجدد با Provenance، Integrity، Validity و وضعیت اسکن امنیتی</p>
        </div>
        <button className="primary" type="button" onClick={() => setShowCreate(value => !value)}>
          {showCreate ? "بستن فرم" : "+ Evidence جدید"}
        </button>
      </div>

      {msg && <p className="message">{msg}</p>}
      {loadError && <p className="message">{loadError}</p>}

      {showCreate && (
        <section className="panel" style={{ marginBottom: 20 }}>
          <h2>ثبت Evidence جدید</h2>
          <p className="muted">ثبت یا اسکن موفق Evidence به‌تنهایی به معنی Compliance نیست؛ Evidence باید در Flowهای کنترل/ارزیابی/ممیزی بررسی و استفاده شود.</p>
          <form className="settingsForm" onSubmit={create}>
            <label>
              عنوان *
              <input value={form.title} onChange={event => update("title", event.target.value)} placeholder="عنوان قابل پیگیری Evidence" maxLength={255} />
            </label>
            <label>
              نوع Evidence
              <select value={form.evidence_type} onChange={event => { update("evidence_type", event.target.value as EvidenceForm["evidence_type"]); setFile(null); }}>
                <option value="file">فایل</option>
                <option value="text">متن</option>
                <option value="url">URL</option>
              </select>
            </label>
            <label>
              توضیح
              <textarea style={{ minHeight: 88, border: "1px solid #cad7e4", borderRadius: 8, padding: 10 }} value={form.description} onChange={event => update("description", event.target.value)} placeholder="Evidence چیست و چرا نگهداری می‌شود؟" />
            </label>
            <label>
              منبع / Provenance
              <input value={form.source} onChange={event => update("source", event.target.value)} placeholder="مثلاً Manual upload، AD، FortiGate، Veeam..." maxLength={255} />
            </label>
            <label>
              دامنه سازمانی
              <select value={form.organization_unit} onChange={event => update("organization_unit", event.target.value)}>
                <option value="">کل سازمان (نیازمند مجوز کل Tenant)</option>
                {units.map(unit => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
              </select>
            </label>
            <label>
              مالک *
              <select value={form.owner} onChange={event => update("owner", event.target.value)}>
                <option value="">انتخاب مالک...</option>
                {users.map(user => <option key={user.id} value={String(user.id)}>{userLabel(user)}</option>)}
              </select>
            </label>
            <label>
              طبقه‌بندی
              <select value={form.classification} onChange={event => update("classification", event.target.value as EvidenceForm["classification"])}>
                <option value="public">Public</option>
                <option value="internal">Internal</option>
                <option value="confidential">Confidential</option>
                <option value="secret">Secret</option>
              </select>
            </label>
            <label>
              زمان جمع‌آوری
              <input dir="ltr" type="datetime-local" value={form.collected_at} onChange={event => update("collected_at", event.target.value)} />
            </label>
            <label>
              اعتبار تا
              <input dir="ltr" type="datetime-local" value={form.valid_until} onChange={event => update("valid_until", event.target.value)} />
            </label>

            {form.evidence_type === "file" && (
              <label>
                فایل *
                <input type="file" onChange={event => setFile(event.target.files?.[0] ?? null)} />
                {file && <small className="muted" dir="ltr">{file.name} · {formatBytes(file.size)}</small>}
              </label>
            )}
            {form.evidence_type === "url" && (
              <label>
                URL *
                <input dir="ltr" type="url" value={form.url} onChange={event => update("url", event.target.value)} placeholder="https://..." />
              </label>
            )}
            {form.evidence_type === "text" && (
              <label>
                محتوای Evidence *
                <textarea style={{ minHeight: 140, border: "1px solid #cad7e4", borderRadius: 8, padding: 10 }} value={form.text_content} onChange={event => update("text_content", event.target.value)} />
              </label>
            )}

            <div className="headActions">
              <button className="primary" type="submit" disabled={saving || !referencesReady}>{saving ? "در حال ثبت..." : "ثبت Evidence"}</button>
              <button type="button" onClick={resetCreate}>انصراف</button>
            </div>
          </form>
        </section>
      )}

      <div className="toolbar">
        <input value={search} onChange={event => setSearch(event.target.value)} onKeyDown={event => { if (event.key === "Enter") void load(); }} placeholder="جستجو در عنوان، توضیح یا منبع..." />
        <select value={classification} onChange={event => setClassification(event.target.value)} style={{ border: "1px solid #cad7e4", borderRadius: 9, padding: "10px 12px", background: "white" }}>
          <option value="">همه طبقه‌بندی‌ها</option>
          <option value="public">Public</option>
          <option value="internal">Internal</option>
          <option value="confidential">Confidential</option>
          <option value="secret">Secret</option>
        </select>
        <button type="button" onClick={() => void load()} disabled={loading}>{loading ? "در حال بارگذاری..." : "اعمال فیلتر"}</button>
      </div>

      <section className="panel">
        {loading ? <p className="muted">در حال بارگذاری Evidence Library...</p> : rows.length === 0 ? <p className="muted">Evidence مطابق این فیلتر وجود ندارد.</p> : (
          <div style={{ overflowX: "auto" }}>
            <table className="dataTable">
              <thead>
                <tr><th>Evidence</th><th>نوع / منبع</th><th>دامنه / مالک</th><th>اعتبار</th><th>اسکن فایل</th><th>مصرف</th><th>Integrity / فایل</th></tr>
              </thead>
              <tbody>{rows.map(row => (
                <tr key={row.id}>
                  <td>
                    <strong>{row.title}</strong>
                    {row.description && <small className="muted" style={{ display: "block", marginTop: 5 }}>{row.description}</small>}
                    <span className="pill">{row.classification}</span>
                  </td>
                  <td>
                    <strong>{typeLabel(row.evidence_type)}</strong>
                    <small className="muted" style={{ display: "block", marginTop: 5 }}>{row.source || "منبع ثبت نشده"}</small>
                    <small className="muted" style={{ display: "block" }}>جمع‌آوری: {dateLabel(row.collected_at)}</small>
                  </td>
                  <td>
                    <span>{row.organization_name || "کل سازمان"}</span>
                    <small className="muted" style={{ display: "block", marginTop: 5 }}>{row.owner_display}</small>
                  </td>
                  <td>{validityLabel(row.valid_until)}</td>
                  <td>
                    <span className="pill">{scanLabel(row)}</span>
                    {row.metadata?.malware_scan_error_code && <small className="muted" dir="ltr" style={{ display: "block" }}>{row.metadata.malware_scan_error_code}</small>}
                    {row.metadata?.malware_scan_scanned_at && <small className="muted" style={{ display: "block" }}>{dateLabel(row.metadata.malware_scan_scanned_at)}</small>}
                  </td>
                  <td>{row.links_count}</td>
                  <td>
                    {row.sha256 ? <code className="hashText" title={row.sha256}>{row.sha256.slice(0, 16)}…</code> : <span className="muted">Hash ندارد</span>}
                    {row.original_filename && (
                      <>
                        <small className="muted" dir="ltr" style={{ display: "block", marginTop: 5 }}>{row.original_filename} · {formatBytes(row.size)}</small>
                        <button type="button" style={{ marginTop: 7 }} onClick={() => void download(row)} disabled={downloading === row.id}>
                          {downloading === row.id ? "در حال دریافت..." : "دانلود امن"}
                        </button>
                      </>
                    )}
                    {row.evidence_type === "url" && row.url && <a dir="ltr" style={{ display: "block", marginTop: 7 }} href={row.url} target="_blank" rel="noopener noreferrer">مشاهده URL</a>}
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
