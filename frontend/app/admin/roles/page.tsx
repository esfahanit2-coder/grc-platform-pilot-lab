"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../../lib/api";

type Permission = { id: string; code: string; module: string; name: string; description: string };
type Role = {
  id: string;
  code: string;
  name: string;
  description: string;
  is_system: boolean;
  is_active: boolean;
  permissions: Permission[];
};
type RoleForm = { code: string; name: string; description: string; permission_codes: string[] };

const emptyForm: RoleForm = { code: "", name: "", description: "", permission_codes: [] };

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

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setMode] = useState<"create" | "edit">("create");
  const [form, setForm] = useState<RoleForm>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const selected = useMemo(() => roles.find((role) => role.id === selectedId) ?? null, [roles, selectedId]);
  const groupedPermissions = useMemo(() => {
    const groups = new Map<string, Permission[]>();
    permissions.forEach((permission) => {
      const group = groups.get(permission.module) ?? [];
      group.push(permission);
      groups.set(permission.module, group);
    });
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [permissions]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [roleResponse, permissionResponse] = await Promise.all([
        apiFetch("/roles/?page_size=200"),
        apiFetch("/permissions/?page_size=500"),
      ]);
      const [roleBody, permissionBody] = await Promise.all([
        roleResponse.json().catch(() => ({})),
        permissionResponse.json().catch(() => ({})),
      ]);
      if (!roleResponse.ok) throw new Error(apiError(roleBody, "دریافت Roleها ناموفق بود."));
      if (!permissionResponse.ok) throw new Error(apiError(permissionBody, "دریافت Permission catalog ناموفق بود."));
      setRoles(rows<Role>(roleBody));
      setPermissions(rows<Permission>(permissionBody));
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "دریافت RBAC ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  function startCreate() {
    setSelectedId(null);
    setMode("create");
    setForm(emptyForm);
    setError("");
    setMessage("");
  }

  function editRole(role: Role) {
    if (role.is_system) return;
    setSelectedId(role.id);
    setMode("edit");
    setForm({
      code: role.code,
      name: role.name,
      description: role.description ?? "",
      permission_codes: role.permissions.map((permission) => permission.code),
    });
    setError("");
    setMessage("");
  }

  function togglePermission(code: string) {
    setForm((current) => ({
      ...current,
      permission_codes: current.permission_codes.includes(code)
        ? current.permission_codes.filter((item) => item !== code)
        : [...current.permission_codes, code],
    }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!form.code.trim() || !form.name.trim()) {
      setError("کد و نام Role الزامی است.");
      return;
    }
    if (selected?.is_system) {
      setError("System Role از این Workspace قابل ویرایش نیست.");
      return;
    }
    setBusy(true);
    try {
      const response = await apiFetch(mode === "edit" && selected ? `/roles/${selected.id}/` : "/roles/", {
        method: mode === "edit" ? "PATCH" : "POST",
        body: JSON.stringify({
          code: form.code.trim(),
          name: form.name.trim(),
          description: form.description.trim(),
          permission_codes: form.permission_codes,
          is_active: true,
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(body, mode === "edit" ? "ویرایش Role ناموفق بود." : "ساخت Role ناموفق بود."));
      setMessage(mode === "edit" ? "Custom Role ذخیره شد." : "Custom Role ایجاد شد.");
      await load();
      if (body?.id) setSelectedId(body.id);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "ذخیره Role ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  async function archiveRole() {
    if (!selected || selected.is_system) return;
    if (!window.confirm(`Custom Role «${selected.name}» آرشیو شود؟`)) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await apiFetch(`/roles/${selected.id}/`, { method: "DELETE" });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(apiError(body, "آرشیو Role ناموفق بود."));
      }
      setMessage("Custom Role آرشیو شد.");
      startCreate();
      await load();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "آرشیو Role ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="adminPage">
      <div className="pageHead">
        <div>
          <Link href="/">← داشبورد</Link>
          <h1>نقش‌ها و مجوزها</h1>
          <p>مدیریت Custom Role بر پایه Permission catalog واقعی؛ System Roleها محافظت‌شده و خواندنی‌اند.</p>
        </div>
        <div className="headActions">
          <Link href="/admin/onboarding" className="secondaryLink">راهنمای راه‌اندازی</Link>
          <Link href="/admin/users" className="secondaryLink">کاربران و Scopeها</Link>
          <button className="primary" type="button" onClick={startCreate}>+ Custom Role</button>
        </div>
      </div>

      {error && <div className="message">{error}</div>}
      {message && <div className="message successText">{message}</div>}

      <div className="grid" style={{ alignItems: "start" }}>
        <section className="panel">
          <div className="roleTitle"><h2>Roleهای Tenant</h2><button type="button" onClick={() => void load()} disabled={loading || busy}>به‌روزرسانی</button></div>
          {loading ? <p className="muted">در حال دریافت Roleها…</p> : roles.length === 0 ? <p className="muted">هیچ Role فعالی یافت نشد.</p> : (
            <div className="stack">
              {roles.map((role) => (
                <article className="treatmentCard" key={role.id}>
                  <div className="roleTitle">
                    <div><strong>{role.name}</strong> <code dir="ltr">{role.code}</code></div>
                    <span className="pill">{role.is_system ? "System" : "Custom"}</span>
                  </div>
                  <p className="muted">{role.description || "بدون توضیح"}</p>
                  <div className="permissionCloud">{role.permissions.slice(0, 10).map((permission) => <span className="pill" key={permission.code}>{permission.code}</span>)}{role.permissions.length > 10 && <span className="pill">+{role.permissions.length - 10}</span>}</div>
                  {role.is_system ? <small className="muted">System Role در این Workspace قابل تغییر نیست.</small> : <button type="button" onClick={() => editRole(role)}>ویرایش Custom Role</button>}
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="panel">
          <div className="roleTitle"><h2>{mode === "edit" ? "ویرایش Custom Role" : "Custom Role جدید"}</h2>{mode === "edit" && <button type="button" onClick={startCreate}>فرم جدید</button>}</div>
          <form className="settingsForm" onSubmit={save}>
            <label>کد *<input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} dir="ltr" placeholder="risk-reviewer" /></label>
            <label>نام *<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
            <label>توضیح<textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} rows={3} /></label>
            <div>
              <div className="roleTitle"><h3>Permissionها</h3><span className="pill">{form.permission_codes.length} انتخاب</span></div>
              {groupedPermissions.length === 0 ? <p className="muted">Permission catalog خالی است.</p> : groupedPermissions.map(([module, modulePermissions]) => (
                <div className="treatmentCard" key={module}>
                  <strong dir="ltr">{module}</strong>
                  <div className="stack" style={{ marginTop: 10 }}>
                    {modulePermissions.map((permission) => (
                      <label className="checkRow" key={permission.code} style={{ fontWeight: 400 }}>
                        <input type="checkbox" checked={form.permission_codes.includes(permission.code)} onChange={() => togglePermission(permission.code)} />
                        <span><code dir="ltr">{permission.code}</code> — {permission.name}{permission.description && <small className="muted"> · {permission.description}</small>}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="headActions">
              <button className="primary" disabled={busy}>{mode === "edit" ? "ذخیره Custom Role" : "ایجاد Custom Role"}</button>
              {selected && !selected.is_system && <button type="button" disabled={busy} onClick={() => void archiveRole()}>آرشیو Role</button>}
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
