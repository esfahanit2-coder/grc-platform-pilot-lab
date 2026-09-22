"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../../lib/api";

type Assignment = {
  id: string;
  role: { id: string; code: string; name: string };
  organization_unit?: { id: string; code: string; name: string } | null;
  valid_from?: string | null;
  valid_until?: string | null;
};
type User = {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  user_active: boolean;
  membership_active: boolean;
  last_login?: string | null;
  role_assignments: Assignment[];
};
type Role = { id: string; code: string; name: string; is_system: boolean; is_active: boolean };
type Unit = { id: string; code: string; name: string; status: string };

type CreateUserForm = {
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  password: string;
};

type AssignmentForm = {
  role_code: string;
  scope_mode: "tenant" | "unit";
  organization_unit: string;
  valid_from: string;
  valid_until: string;
};

const emptyCreate: CreateUserForm = { username: "", first_name: "", last_name: "", email: "", password: "" };
const emptyAssignment: AssignmentForm = {
  role_code: "",
  scope_mode: "tenant",
  organization_unit: "",
  valid_from: "",
  valid_until: "",
};

function rows<T>(body: T[] | { results?: T[] }): T[] {
  return Array.isArray(body) ? body : body.results ?? [];
}

function apiError(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const object = body as Record<string, unknown>;
  if (typeof object.detail === "string") return object.detail;
  if (typeof object.message === "string") return object.message;
  const messages: string[] = [];
  Object.entries(object).forEach(([field, value]) => {
    if (Array.isArray(value)) messages.push(`${field}: ${value.join("، ")}`);
    else if (typeof value === "string") messages.push(`${field}: ${value}`);
    else if (value && typeof value === "object") messages.push(`${field}: ${JSON.stringify(value)}`);
  });
  return messages.join(" | ") || fallback;
}

function formatDateTime(value?: string | null) {
  if (!value) return "بدون محدودیت";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function toIsoOrNull(value: string) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState<CreateUserForm>(emptyCreate);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ first_name: "", last_name: "", email: "", membership_active: true });
  const [assignment, setAssignment] = useState<AssignmentForm>(emptyAssignment);

  const selected = useMemo(() => users.find((user) => user.id === selectedId) ?? null, [selectedId, users]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [userResponse, roleResponse, unitResponse] = await Promise.all([
        apiFetch("/tenant-users/?include_inactive=true"),
        apiFetch("/roles/?page_size=200"),
        apiFetch("/organization-units/?page_size=500"),
      ]);
      const [userBody, roleBody, unitBody] = await Promise.all([
        userResponse.json().catch(() => ({})),
        roleResponse.json().catch(() => ({})),
        unitResponse.json().catch(() => ({})),
      ]);
      if (!userResponse.ok) throw new Error(apiError(userBody, "دریافت کاربران ناموفق بود."));
      if (!roleResponse.ok) throw new Error(apiError(roleBody, "دریافت نقش‌ها ناموفق بود."));
      if (!unitResponse.ok) throw new Error(apiError(unitBody, "دریافت ساختار سازمانی ناموفق بود."));
      setUsers(rows<User>(userBody));
      setRoles(rows<Role>(roleBody).filter((role) => role.is_active));
      setUnits(rows<Unit>(unitBody).filter((unit) => unit.status !== "archived"));
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "دریافت اطلاعات مدیریت کاربران ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!selected) return;
    setEditForm({
      first_name: selected.first_name ?? "",
      last_name: selected.last_name ?? "",
      email: selected.email ?? "",
      membership_active: selected.membership_active,
    });
    setAssignment(emptyAssignment);
  }, [selected]);

  async function createUser(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setError("");
    if (!createForm.username.trim() || !createForm.password) {
      setError("نام کاربری و رمز عبور الزامی است.");
      return;
    }
    setBusy(true);
    const payload = { ...createForm, username: createForm.username.trim() };
    try {
      const response = await apiFetch("/tenant-users/", { method: "POST", body: JSON.stringify(payload) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(body, "ساخت کاربر ناموفق بود."));
      setCreateForm(emptyCreate);
      setShowCreate(false);
      setMessage("کاربر ساخته شد. برای اعطای دسترسی، Role و Scope را صریحاً تخصیص دهید.");
      await load();
      if (body?.id) setSelectedId(body.id);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "ساخت کاربر ناموفق بود.");
    } finally {
      // Password is intentionally discarded after every submit, including failed validation.
      setCreateForm((current) => ({ ...current, password: "" }));
      setBusy(false);
    }
  }

  async function saveUser(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await apiFetch(`/tenant-users/${selected.id}/`, {
        method: "PATCH",
        body: JSON.stringify(editForm),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(body, "ویرایش کاربر ناموفق بود."));
      setMessage(
        editForm.membership_active
          ? "اطلاعات/عضویت کاربر ذخیره شد. Roleهای لغوشده در زمان غیرفعال‌سازی خودکار برنمی‌گردند."
          : "عضویت غیرفعال شد و Scopeهای فعال کاربر نیز لغو شدند.",
      );
      await load();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "ویرایش کاربر ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  async function assignRole(event: FormEvent) {
    event.preventDefault();
    if (!selected || !selected.membership_active) return;
    setError("");
    setMessage("");
    if (!assignment.role_code) {
      setError("Role را انتخاب کنید.");
      return;
    }
    if (assignment.scope_mode === "unit" && !assignment.organization_unit) {
      setError("برای Scope سازمانی، واحد را صریحاً انتخاب کنید.");
      return;
    }
    if (assignment.valid_from && assignment.valid_until) {
      const start = new Date(assignment.valid_from);
      const end = new Date(assignment.valid_until);
      if (!Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime()) && end < start) {
        setError("پایان اعتبار نمی‌تواند قبل از شروع اعتبار باشد.");
        return;
      }
    }
    setBusy(true);
    try {
      const response = await apiFetch(`/tenant-users/${selected.id}/role-assignments/`, {
        method: "POST",
        body: JSON.stringify({
          role_code: assignment.role_code,
          organization_unit: assignment.scope_mode === "tenant" ? null : assignment.organization_unit,
          valid_from: toIsoOrNull(assignment.valid_from),
          valid_until: toIsoOrNull(assignment.valid_until),
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(body, "تخصیص نقش ناموفق بود."));
      setAssignment(emptyAssignment);
      setMessage("Role و Scope با موفقیت تخصیص داده شد.");
      await load();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "تخصیص نقش ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  async function revokeAssignment(id: string) {
    if (!window.confirm("این Role Assignment غیرفعال شود؟")) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await apiFetch(`/role-assignments/${id}/`, { method: "DELETE" });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(apiError(body, "لغو Role Assignment ناموفق بود."));
      }
      setMessage("Role Assignment لغو شد.");
      await load();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "لغو Role Assignment ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="adminPage">
      <div className="pageHead">
        <div>
          <Link href="/">← داشبورد</Link>
          <h1>کاربران و دسترسی‌ها</h1>
          <p>چرخه عضویت، Role و Scope سازمانی با اختیار صریح مدیر Tenant</p>
        </div>
        <div className="headActions">
          <Link href="/admin/onboarding" className="secondaryLink">راهنمای راه‌اندازی</Link>
          <Link href="/admin/roles" className="secondaryLink">مدیریت Roleها</Link>
          <button className="primary" onClick={() => setShowCreate((value) => !value)}>
            {showCreate ? "بستن فرم" : "+ کاربر جدید"}
          </button>
        </div>
      </div>

      {error && <div className="message">{error}</div>}
      {message && <div className="message successText">{message}</div>}

      {showCreate && (
        <form className="panel settingsForm" onSubmit={createUser} autoComplete="off" style={{ marginBottom: 18 }}>
          <h2>ساخت کاربر Tenant</h2>
          <p className="muted">ساخت کاربر هیچ Role مدیریتی را به‌طور خودکار اعطا نمی‌کند.</p>
          <label>نام کاربری *<input value={createForm.username} onChange={(event) => setCreateForm({ ...createForm, username: event.target.value })} autoComplete="off" /></label>
          <label>نام<input value={createForm.first_name} onChange={(event) => setCreateForm({ ...createForm, first_name: event.target.value })} /></label>
          <label>نام خانوادگی<input value={createForm.last_name} onChange={(event) => setCreateForm({ ...createForm, last_name: event.target.value })} /></label>
          <label>ایمیل<input type="email" value={createForm.email} onChange={(event) => setCreateForm({ ...createForm, email: event.target.value })} /></label>
          <label>رمز عبور اولیه *<input type="password" value={createForm.password} onChange={(event) => setCreateForm({ ...createForm, password: event.target.value })} autoComplete="new-password" /></label>
          <small className="muted">رمز بعد از Submit از فرم پاک می‌شود و توسط UI ذخیره یا دوباره نمایش داده نمی‌شود.</small>
          <button className="primary" disabled={busy}>ساخت کاربر</button>
        </form>
      )}

      <div className="grid" style={{ alignItems: "start" }}>
        <section className="panel">
          <div className="roleTitle"><h2>اعضای Tenant</h2><button onClick={() => void load()} disabled={loading || busy}>به‌روزرسانی</button></div>
          {loading ? <p className="muted">در حال دریافت کاربران…</p> : users.length === 0 ? (
            <p className="muted">هنوز کاربری برای این Tenant وجود ندارد.</p>
          ) : (
            <table className="dataTable">
              <thead><tr><th>کاربر</th><th>عضویت</th><th>Roleها</th><th></th></tr></thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td><strong>{user.username}</strong><div className="muted">{[user.first_name, user.last_name].filter(Boolean).join(" ") || user.email || "—"}</div></td>
                    <td><span className="pill">{user.membership_active ? "فعال" : "غیرفعال"}</span></td>
                    <td>{user.role_assignments.length || "—"}</td>
                    <td><button onClick={() => setSelectedId(user.id)}>مدیریت</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="panel">
          {!selected ? (
            <p className="muted">برای ویرایش عضویت و دسترسی‌ها یک کاربر را انتخاب کنید.</p>
          ) : (
            <div className="stack">
              <div><h2>{selected.username}</h2><p className="muted">User ID: <span dir="ltr">{selected.id}</span></p></div>
              <form className="settingsForm" onSubmit={saveUser}>
                <label>نام<input value={editForm.first_name} onChange={(event) => setEditForm({ ...editForm, first_name: event.target.value })} /></label>
                <label>نام خانوادگی<input value={editForm.last_name} onChange={(event) => setEditForm({ ...editForm, last_name: event.target.value })} /></label>
                <label>ایمیل<input type="email" value={editForm.email} onChange={(event) => setEditForm({ ...editForm, email: event.target.value })} /></label>
                <label className="checkRow"><input type="checkbox" checked={editForm.membership_active} onChange={(event) => setEditForm({ ...editForm, membership_active: event.target.checked })} /> عضویت Tenant فعال باشد</label>
                <small className="muted">غیرفعال‌سازی، Role Scopeهای فعال را لغو می‌کند. فعال‌سازی مجدد آن‌ها را خودکار برنمی‌گرداند.</small>
                <button className="primary" disabled={busy}>ذخیره کاربر</button>
              </form>

              <div>
                <h3>Role Assignmentهای فعال</h3>
                {selected.role_assignments.length === 0 ? <p className="muted">هیچ Role فعالی تخصیص داده نشده است.</p> : selected.role_assignments.map((item) => (
                  <div className="treatmentCard" key={item.id}>
                    <strong>{item.role.name}</strong> <code dir="ltr">{item.role.code}</code>
                    <p>{item.organization_unit ? `${item.organization_unit.name} · ${item.organization_unit.code}` : "کل Tenant"}</p>
                    <small className="muted">اعتبار: {formatDateTime(item.valid_from)} ← {formatDateTime(item.valid_until)}</small>
                    <div><button type="button" onClick={() => void revokeAssignment(item.id)} disabled={busy}>لغو دسترسی</button></div>
                  </div>
                ))}
              </div>

              <form className="settingsForm" onSubmit={assignRole}>
                <h3>تخصیص Role جدید</h3>
                {!selected.membership_active && <p className="message">برای تخصیص Role ابتدا عضویت کاربر را فعال کنید.</p>}
                <label>Role
                  <select value={assignment.role_code} onChange={(event) => setAssignment({ ...assignment, role_code: event.target.value })} disabled={!selected.membership_active}>
                    <option value="">انتخاب Role…</option>
                    {roles.map((role) => <option key={role.id} value={role.code}>{role.name} · {role.code}</option>)}
                  </select>
                </label>
                <label>Scope
                  <select value={assignment.scope_mode} onChange={(event) => setAssignment({ ...assignment, scope_mode: event.target.value as "tenant" | "unit", organization_unit: "" })} disabled={!selected.membership_active}>
                    <option value="tenant">کل Tenant — انتخاب صریح</option>
                    <option value="unit">واحد سازمانی مشخص</option>
                  </select>
                </label>
                {assignment.scope_mode === "unit" && (
                  <label>واحد سازمانی
                    <select value={assignment.organization_unit} onChange={(event) => setAssignment({ ...assignment, organization_unit: event.target.value })} disabled={!selected.membership_active}>
                      <option value="">انتخاب واحد…</option>
                      {units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name} · {unit.code}</option>)}
                    </select>
                  </label>
                )}
                <label>شروع اعتبار (اختیاری)<input type="datetime-local" value={assignment.valid_from} onChange={(event) => setAssignment({ ...assignment, valid_from: event.target.value })} /></label>
                <label>پایان اعتبار (اختیاری)<input type="datetime-local" value={assignment.valid_until} onChange={(event) => setAssignment({ ...assignment, valid_until: event.target.value })} /></label>
                <button className="primary" disabled={busy || !selected.membership_active}>تخصیص Role و Scope</button>
              </form>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
