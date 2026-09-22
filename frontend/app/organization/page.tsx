"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";

type Node = { id: string; code: string; name: string; unit_type: string; status: string; manager?: number | null; children: Node[] };
type Unit = {
  id: string;
  parent?: string | null;
  unit_type: string;
  code: string;
  name: string;
  name_en: string;
  manager?: number | null;
  manager_display?: string | null;
  status: string;
  children_count: number;
};
type User = { id: number; username: string; first_name: string; last_name: string; membership_active: boolean };
type UnitForm = { parent: string; unit_type: string; code: string; name: string; name_en: string; manager: string; status: string };

const unitTypes = [
  ["holding", "هلدینگ"],
  ["company", "شرکت"],
  ["business_unit", "واحد کسب‌وکار"],
  ["department", "دپارتمان"],
  ["site", "سایت"],
  ["team", "تیم"],
] as const;
const emptyForm: UnitForm = { parent: "", unit_type: "department", code: "", name: "", name_en: "", manager: "", status: "active" };

function rows<T>(body: T[] | { results?: T[] }): T[] {
  return Array.isArray(body) ? body : body.results ?? [];
}

function apiError(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const object = body as Record<string, unknown>;
  if (typeof object.detail === "string") return object.detail;
  const messages: string[] = [];
  for (const [field, value] of Object.entries(object)) {
    if (Array.isArray(value)) messages.push(`${field}: ${value.join("، ")}`);
    else if (typeof value === "string") messages.push(`${field}: ${value}`);
  }
  return messages.join(" | ") || fallback;
}

function typeLabel(value: string) {
  return unitTypes.find(([key]) => key === value)?.[1] ?? value;
}

function Tree({ nodes, onSelect, depth = 0 }: { nodes: Node[]; onSelect: (id: string) => void; depth?: number }) {
  return <>{nodes.map((node) => (
    <div key={node.id}>
      <button type="button" className="treeNode" style={{ marginRight: depth * 22, width: "calc(100% - 4px)", border: 0, background: "transparent", cursor: "pointer" }} onClick={() => onSelect(node.id)}>
        <span><strong>{node.name}</strong><small className="muted"> · {typeLabel(node.unit_type)}</small></span>
        <span>{node.code}</span>
      </button>
      <Tree nodes={node.children ?? []} onSelect={onSelect} depth={depth + 1} />
    </div>
  ))}</>;
}

export default function OrganizationPage() {
  const [tree, setTree] = useState<Node[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setMode] = useState<"create" | "edit">("create");
  const [form, setForm] = useState<UnitForm>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const selected = useMemo(() => units.find((unit) => unit.id === selectedId) ?? null, [selectedId, units]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [treeResponse, unitResponse, userResponse] = await Promise.all([
        apiFetch("/organization-units/tree/"),
        apiFetch("/organization-units/?page_size=500"),
        apiFetch("/tenant-users/"),
      ]);
      const [treeBody, unitBody, userBody] = await Promise.all([
        treeResponse.json().catch(() => ({})),
        unitResponse.json().catch(() => ({})),
        userResponse.json().catch(() => ({})),
      ]);
      if (!treeResponse.ok) throw new Error(apiError(treeBody, "دریافت درخت سازمانی ناموفق بود."));
      if (!unitResponse.ok) throw new Error(apiError(unitBody, "دریافت واحدهای سازمانی ناموفق بود."));
      if (!userResponse.ok) throw new Error(apiError(userBody, "دریافت مدیران قابل انتخاب ناموفق بود."));
      setTree(Array.isArray(treeBody) ? treeBody : []);
      setUnits(rows<Unit>(unitBody).filter((unit) => unit.status !== "archived"));
      setUsers(rows<User>(userBody).filter((user) => user.membership_active));
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "دریافت اطلاعات ساختار سازمانی ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  function selectUnit(id: string) {
    const unit = units.find((item) => item.id === id);
    if (!unit) return;
    setSelectedId(id);
    setMode("edit");
    setForm({
      parent: unit.parent ?? "",
      unit_type: unit.unit_type,
      code: unit.code,
      name: unit.name,
      name_en: unit.name_en ?? "",
      manager: unit.manager ? String(unit.manager) : "",
      status: unit.status,
    });
    setError("");
    setMessage("");
  }

  function startCreate(parent = "") {
    setSelectedId(null);
    setMode("create");
    setForm({ ...emptyForm, parent });
    setError("");
    setMessage("");
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!form.code.trim() || !form.name.trim()) {
      setError("کد و نام واحد الزامی است.");
      return;
    }
    setBusy(true);
    try {
      const payload = {
        parent: form.parent || null,
        unit_type: form.unit_type,
        code: form.code.trim(),
        name: form.name.trim(),
        name_en: form.name_en.trim(),
        manager: form.manager ? Number(form.manager) : null,
        status: form.status,
      };
      const response = await apiFetch(mode === "edit" && selected ? `/organization-units/${selected.id}/` : "/organization-units/", {
        method: mode === "edit" ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(body, mode === "edit" ? "ویرایش واحد ناموفق بود." : "ساخت واحد ناموفق بود."));
      setMessage(mode === "edit" ? "واحد سازمانی ذخیره شد." : "واحد سازمانی ایجاد شد.");
      await load();
      if (body?.id) selectUnit(body.id);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "ذخیره واحد سازمانی ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  async function archiveSelected() {
    if (!selected) return;
    if (!window.confirm(`واحد «${selected.name}» آرشیو شود؟`)) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await apiFetch(`/organization-units/${selected.id}/`, { method: "DELETE" });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(apiError(body, "آرشیو واحد ناموفق بود."));
      }
      setMessage("واحد سازمانی آرشیو شد.");
      startCreate();
      await load();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "آرشیو واحد ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="adminPage">
      <div className="pageHead">
        <div>
          <Link href="/">← داشبورد</Link>
          <h1>ساختار سازمانی</h1>
          <p>مدیریت Scopeهای سازمانی با کنترل hierarchy و مجوز Backend</p>
        </div>
        <div className="headActions">
          <Link href="/admin/onboarding" className="secondaryLink">راهنمای راه‌اندازی</Link>
          <button className="primary" type="button" onClick={() => startCreate()}>+ واحد جدید</button>
        </div>
      </div>

      {error && <div className="message">{error}</div>}
      {message && <div className="message successText">{message}</div>}

      <div className="grid" style={{ alignItems: "start" }}>
        <section className="panel">
          <div className="roleTitle"><h2>درخت سازمانی</h2><button type="button" onClick={() => void load()} disabled={loading || busy}>به‌روزرسانی</button></div>
          {loading ? <p className="muted">در حال دریافت ساختار…</p> : tree.length === 0 ? (
            <div className="stack"><p className="muted">هنوز واحد سازمانی ثبت نشده است.</p><button className="primary" type="button" onClick={() => startCreate()}>ساخت اولین واحد</button></div>
          ) : <Tree nodes={tree} onSelect={selectUnit} />}
        </section>

        <section className="panel">
          <div className="roleTitle">
            <div><h2>{mode === "edit" ? "ویرایش واحد" : "واحد سازمانی جدید"}</h2>{selected && <small className="muted">{selected.children_count} زیرواحد فعال</small>}</div>
            {selected && <button type="button" onClick={() => startCreate(selected.id)}>+ زیرواحد</button>}
          </div>
          <form className="settingsForm" onSubmit={save}>
            <label>Parent
              <select value={form.parent} onChange={(event) => setForm({ ...form, parent: event.target.value })}>
                <option value="">ریشه Tenant — انتخاب صریح</option>
                {units.filter((unit) => unit.id !== selectedId).map((unit) => <option key={unit.id} value={unit.id}>{unit.name} · {unit.code}</option>)}
              </select>
            </label>
            <small className="muted">ایجاد یا انتقال به ریشه فقط با whole-tenant `organization.manage` پذیرفته می‌شود.</small>
            <label>نوع واحد
              <select value={form.unit_type} onChange={(event) => setForm({ ...form, unit_type: event.target.value })}>
                {unitTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label>کد *<input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} dir="ltr" /></label>
            <label>نام *<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
            <label>نام انگلیسی<input value={form.name_en} onChange={(event) => setForm({ ...form, name_en: event.target.value })} dir="ltr" /></label>
            <label>مدیر
              <select value={form.manager} onChange={(event) => setForm({ ...form, manager: event.target.value })}>
                <option value="">بدون مدیر</option>
                {users.map((user) => <option key={user.id} value={user.id}>{[user.first_name, user.last_name].filter(Boolean).join(" ") || user.username}</option>)}
              </select>
            </label>
            <label>وضعیت
              <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
                <option value="active">فعال</option>
                <option value="inactive">غیرفعال</option>
              </select>
            </label>
            <div className="headActions">
              <button className="primary" disabled={busy}>{mode === "edit" ? "ذخیره تغییرات" : "ایجاد واحد"}</button>
              {selected && <button type="button" disabled={busy} onClick={() => void archiveSelected()}>آرشیو واحد</button>}
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
