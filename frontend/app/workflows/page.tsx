"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { apiFetch } from "../../lib/api";


type StateDetail = {
  id: string;
  code: string;
  name: string;
  is_initial: boolean;
  is_terminal: boolean;
  sort_order: number;
};

type Definition = {
  id: string;
  name: string;
  object_type: string;
  version: number;
  is_active: boolean;
  states: StateDetail[];
  transitions: unknown[];
};

type WorkflowInstance = {
  id: string;
  definition: string;
  definition_name: string;
  definition_version: number;
  object_type: string;
  object_id: string;
  target_display: string;
  organization_unit?: string | null;
  organization_unit_name?: string | null;
  current_state: string;
  current_state_detail: StateDetail;
  started_by?: number | null;
  started_by_display: string;
  assigned_to?: number | null;
  assigned_to_display: string;
  is_assigned_to_me: boolean;
  can_assign: boolean;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type ExecutableTransition = {
  id: string;
  code: string;
  name: string;
  to_state_detail: StateDetail;
};

type WorkflowEvent = {
  id: string;
  event_type: string;
  transition?: string | null;
  transition_name?: string | null;
  from_state?: string | null;
  from_state_detail?: StateDetail | null;
  to_state: string;
  to_state_detail: StateDetail;
  actor?: number | null;
  actor_display: string;
  comment: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

type Participant = {
  id: number;
  username: string;
  display: string;
};

const objectTypeLabels: Record<string, string> = {
  risk: "ریسک",
  assessment: "ارزیابی",
  finding: "یافته",
  document: "مستند",
  action: "اقدام",
  audit: "ممیزی",
};

const statusLabels: Record<string, string> = {
  active: "فعال",
  completed: "تکمیل‌شده",
};

const eventLabels: Record<string, string> = {
  started: "شروع گردش‌کار",
  transition: "تغییر وضعیت",
  assignment: "تخصیص مسئول",
};

function rows<T>(body: T[] | { results?: T[] }): T[] {
  return Array.isArray(body) ? body : body.results ?? [];
}

function apiError(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const object = body as Record<string, unknown>;
  if (typeof object.detail === "string") return object.detail;
  const messages: string[] = [];
  Object.entries(object).forEach(([field, value]) => {
    if (Array.isArray(value)) messages.push(field + ": " + value.join("، "));
    else if (typeof value === "string") messages.push(field + ": " + value);
  });
  return messages.join(" | ") || fallback;
}

function formatDateTime(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fa-IR", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function objectTypeLabel(value: string) {
  return objectTypeLabels[value] ?? value;
}

function assignmentSummary(event: WorkflowEvent) {
  if (event.event_type !== "assignment") return "";
  const previous = String(event.metadata.previous_assignee_display ?? "").trim();
  const next = String(event.metadata.assignee_display ?? "").trim();
  if (previous && next) return previous + " ← " + next;
  if (next) return "تخصیص به " + next;
  if (previous) return "لغو تخصیص " + previous;
  return "تغییر مسئول";
}

export default function WorkflowsPage() {
  const [definitions, setDefinitions] = useState<Definition[]>([]);
  const [instances, setInstances] = useState<WorkflowInstance[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [transitions, setTransitions] = useState<ExecutableTransition[]>([]);
  const [candidates, setCandidates] = useState<Participant[]>([]);

  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [search, setSearch] = useState("");
  const [objectTypeFilter, setObjectTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [assignmentFilter, setAssignmentFilter] = useState<"all" | "mine" | "unassigned">("all");

  const [assignMode, setAssignMode] = useState(false);
  const [assigneeChoice, setAssigneeChoice] = useState("__none__");
  const [assignmentComment, setAssignmentComment] = useState("");
  const [transitionId, setTransitionId] = useState("");
  const [transitionComment, setTransitionComment] = useState("");

  const selected = useMemo(
    () => instances.find((instance) => instance.id === selectedId) ?? null,
    [instances, selectedId],
  );

  const filteredInstances = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase("fa");
    return instances.filter((instance) => {
      if (objectTypeFilter !== "all" && instance.object_type !== objectTypeFilter) return false;
      if (statusFilter !== "all" && instance.status !== statusFilter) return false;
      if (assignmentFilter === "mine" && !instance.is_assigned_to_me) return false;
      if (assignmentFilter === "unassigned" && instance.assigned_to) return false;
      if (!needle) return true;
      return [
        instance.target_display,
        instance.definition_name,
        instance.current_state_detail?.name,
        instance.assigned_to_display,
        instance.object_id,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLocaleLowerCase("fa").includes(needle));
    });
  }, [instances, search, objectTypeFilter, statusFilter, assignmentFilter]);

  async function loadBase() {
    setLoading(true);
    setError("");
    try {
      const [instanceResponse, definitionResponse] = await Promise.all([
        apiFetch("/workflows/instances/?page_size=500"),
        apiFetch("/workflows/definitions/?page_size=200"),
      ]);
      const [instanceBody, definitionBody] = await Promise.all([
        instanceResponse.json().catch(() => ({})),
        definitionResponse.json().catch(() => ({})),
      ]);
      if (!instanceResponse.ok) {
        throw new Error(apiError(instanceBody, "دریافت گردش‌کارها ناموفق بود."));
      }

      const instanceRows = rows<WorkflowInstance>(instanceBody);
      setInstances(instanceRows);
      setDefinitions(definitionResponse.ok ? rows<Definition>(definitionBody) : []);

      if (selectedId && !instanceRows.some((item) => item.id === selectedId)) {
        setSelectedId(null);
        setEvents([]);
        setTransitions([]);
        setAssignMode(false);
      }
      return instanceRows;
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "دریافت Workspace گردش‌کار ناموفق بود.");
      return [] as WorkflowInstance[];
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(instanceId: string) {
    setDetailLoading(true);
    setError("");
    try {
      const [eventResponse, transitionResponse] = await Promise.all([
        apiFetch("/workflows/instances/" + instanceId + "/events/"),
        apiFetch("/workflows/instances/" + instanceId + "/available-transitions/"),
      ]);
      const [eventBody, transitionBody] = await Promise.all([
        eventResponse.json().catch(() => ({})),
        transitionResponse.json().catch(() => ({})),
      ]);
      if (!eventResponse.ok) throw new Error(apiError(eventBody, "دریافت تاریخچه گردش‌کار ناموفق بود."));
      if (!transitionResponse.ok) {
        throw new Error(apiError(transitionBody, "دریافت اقدامات مجاز گردش‌کار ناموفق بود."));
      }
      setEvents(rows<WorkflowEvent>(eventBody));
      setTransitions(rows<ExecutableTransition>(transitionBody));
      setTransitionId("");
      setTransitionComment("");
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "دریافت جزئیات گردش‌کار ناموفق بود.");
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    void loadBase();
  }, []);

  async function selectInstance(instance: WorkflowInstance) {
    setSelectedId(instance.id);
    setAssignMode(false);
    setCandidates([]);
    setMessage("");
    await loadDetail(instance.id);
  }

  async function refreshSelected() {
    const instanceRows = await loadBase();
    if (!selectedId) return;
    if (instanceRows.some((item) => item.id === selectedId)) {
      await loadDetail(selectedId);
    }
  }

  async function beginAssignment() {
    if (!selected?.can_assign) return;
    setError("");
    setMessage("");
    setAssignMode(true);
    setAssignmentComment("");
    try {
      const response = await apiFetch(
        "/workflows/instances/" + selected.id + "/assignee-candidates/",
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(apiError(body, "دریافت کاربران قابل تخصیص ناموفق بود."));
      }
      const candidateRows = Array.isArray(body.results) ? body.results as Participant[] : [];
      setCandidates(candidateRows);
      setAssigneeChoice(
        selected.assigned_to && candidateRows.some((item) => item.id === selected.assigned_to)
          ? String(selected.assigned_to)
          : "__none__",
      );
    } catch (exception) {
      setAssignMode(false);
      setError(exception instanceof Error ? exception.message : "دریافت کاربران قابل تخصیص ناموفق بود.");
    }
  }

  async function saveAssignment(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    const candidate =
      assigneeChoice === "__none__"
        ? null
        : candidates.find((item) => String(item.id) === assigneeChoice) ?? null;
    const description = candidate ? "«" + candidate.display + "»" : "صف مشترک بدون مسئول";
    if (!window.confirm("مسئول این گردش‌کار به " + description + " تغییر کند؟")) return;

    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await apiFetch("/workflows/instances/" + selected.id + "/assign/", {
        method: "POST",
        body: JSON.stringify({
          assignee_id: candidate?.id ?? null,
          comment: assignmentComment.trim(),
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(body, "تخصیص گردش‌کار ناموفق بود."));
      setAssignMode(false);
      setCandidates([]);
      setAssignmentComment("");
      setMessage(candidate ? "گردش‌کار به " + candidate.display + " تخصیص یافت." : "گردش‌کار به صف مشترک بازگردانده شد.");
      await refreshSelected();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "تخصیص گردش‌کار ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  async function executeTransition(event: FormEvent) {
    event.preventDefault();
    if (!selected || !transitionId) return;
    const transition = transitions.find((item) => item.id === transitionId);
    if (!transition) {
      setError("اقدام انتخاب‌شده دیگر در فهرست مجاز نیست. صفحه را به‌روزرسانی کنید.");
      return;
    }
    if (!window.confirm(
      "اقدام «" + transition.name + "» اجرا و وضعیت به «" + transition.to_state_detail.name + "» منتقل شود؟",
    )) return;

    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await apiFetch("/workflows/instances/" + selected.id + "/transition/", {
        method: "POST",
        body: JSON.stringify({
          transition_id: transition.id,
          comment: transitionComment.trim(),
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(body, "اجرای تغییر وضعیت ناموفق بود."));
      setTransitionId("");
      setTransitionComment("");
      setMessage("اقدام «" + transition.name + "» ثبت شد.");
      await refreshSelected();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "اجرای تغییر وضعیت ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="adminPage">
      <div className="pageHead">
        <div>
          <Link href="/">← داشبورد</Link>
          <h1>اجرای گردش‌کار</h1>
          <p>صف کار، تخصیص مسئول، تغییر وضعیت و تاریخچه؛ authority چرخه روی سرور باقی می‌ماند.</p>
        </div>
        <div className="headActions">
          <Link href="/work" className="secondaryLink">کارهای من</Link>
          <button className="secondaryLink" onClick={() => void loadBase()} disabled={loading || busy}>
            به‌روزرسانی
          </button>
        </div>
      </div>

      {error && <div className="message">{error}</div>}
      {message && <div className="message successText">{message}</div>}

      <div className="toolbar" style={{ flexWrap: "wrap" }}>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="جستجو در موضوع، تعریف، وضعیت یا مسئول…"
        />
        <select value={objectTypeFilter} onChange={(event) => setObjectTypeFilter(event.target.value)}>
          <option value="all">همه حوزه‌ها</option>
          {Object.entries(objectTypeLabels).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="all">همه وضعیت‌ها</option>
          <option value="active">فعال</option>
          <option value="completed">تکمیل‌شده</option>
        </select>
        <select
          value={assignmentFilter}
          onChange={(event) => setAssignmentFilter(event.target.value as "all" | "mine" | "unassigned")}
        >
          <option value="all">همه تخصیص‌ها</option>
          <option value="mine">تخصیص‌یافته به من</option>
          <option value="unassigned">بدون مسئول</option>
        </select>
      </div>

      <div
        className="grid"
        style={{ alignItems: "start", gridTemplateColumns: "minmax(420px, .9fr) minmax(520px, 1.1fr)" }}
      >
        <section className="panel">
          <div className="roleTitle">
            <h2>صف گردش‌کارها</h2>
            <span className="pill">{filteredInstances.length} مورد</span>
          </div>
          {loading ? (
            <p className="muted">در حال دریافت گردش‌کارها…</p>
          ) : filteredInstances.length === 0 ? (
            <p className="muted">در فیلتر فعلی گردش‌کاری وجود ندارد.</p>
          ) : (
            <table className="dataTable">
              <thead>
                <tr>
                  <th>موضوع</th>
                  <th>State</th>
                  <th>مسئول</th>
                  <th>وضعیت</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredInstances.map((instance) => (
                  <tr key={instance.id}>
                    <td>
                      <strong>{instance.target_display}</strong>
                      <div className="muted">
                        {objectTypeLabel(instance.object_type)} · {instance.definition_name}
                      </div>
                    </td>
                    <td>{instance.current_state_detail?.name ?? "—"}</td>
                    <td>
                      {instance.assigned_to_display || "صف مشترک"}
                      {instance.is_assigned_to_me && <div><span className="pill">من</span></div>}
                    </td>
                    <td><span className="pill">{statusLabels[instance.status] ?? instance.status}</span></td>
                    <td>
                      <button onClick={() => void selectInstance(instance)}>
                        {selectedId === instance.id ? "انتخاب‌شده" : "باز کردن"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="panel">
          {!selected ? (
            <div className="stack">
              <h2>Workspace اجرا</h2>
              <p className="muted">
                یک گردش‌کار را صریحاً انتخاب کنید. هیچ Instance به‌صورت خودکار انتخاب نمی‌شود.
              </p>
            </div>
          ) : detailLoading ? (
            <p className="muted">در حال دریافت وضعیت و تاریخچه…</p>
          ) : (
            <div className="stack">
              <div className="roleTitle">
                <div>
                  <h2>{selected.target_display}</h2>
                  <small className="muted">
                    {objectTypeLabel(selected.object_type)} · {selected.definition_name} v{selected.definition_version}
                  </small>
                </div>
                <span className="pill">{statusLabels[selected.status] ?? selected.status}</span>
              </div>

              <div className="permissionCloud">
                <span className="pill">State: {selected.current_state_detail?.name ?? "—"}</span>
                <span className="pill">
                  مسئول: {selected.assigned_to_display || "صف مشترک"}
                </span>
                <span className="pill">
                  دامنه: {selected.organization_unit_name || "کل Tenant"}
                </span>
                {selected.started_by_display && (
                  <span className="pill">شروع‌کننده: {selected.started_by_display}</span>
                )}
              </div>

              <div className="headActions" style={{ flexWrap: "wrap" }}>
                {selected.can_assign && selected.status === "active" && (
                  <button onClick={() => void beginAssignment()} disabled={busy}>
                    تغییر مسئول
                  </button>
                )}
                <button onClick={() => void loadDetail(selected.id)} disabled={busy || detailLoading}>
                  تازه‌سازی جزئیات
                </button>
              </div>

              {assignMode && selected.can_assign && (
                <form className="settingsForm" onSubmit={saveAssignment}>
                  <div className="roleTitle">
                    <h3>تخصیص مسئول</h3>
                    <button
                      type="button"
                      onClick={() => {
                        setAssignMode(false);
                        setCandidates([]);
                      }}
                    >
                      بستن
                    </button>
                  </div>
                  <label>
                    مسئول
                    <select
                      value={assigneeChoice}
                      onChange={(event) => setAssigneeChoice(event.target.value)}
                    >
                      <option value="__none__">بدون مسئول / صف مشترک</option>
                      {candidates.map((person) => (
                        <option key={person.id} value={person.id}>
                          {person.display} · {person.username}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    توضیح تخصیص
                    <textarea
                      rows={3}
                      value={assignmentComment}
                      onChange={(event) => setAssignmentComment(event.target.value)}
                      style={{ padding: 10, border: "1px solid #cad7e4", borderRadius: 8 }}
                    />
                  </label>
                  <small className="muted">
                    تخصیص فقط مسئول کار را مشخص می‌کند و هیچ Permission جدیدی ایجاد نمی‌کند.
                  </small>
                  <button className="primary" disabled={busy}>ثبت تخصیص</button>
                </form>
              )}

              <div style={{ borderTop: "1px solid #e5ebf2", paddingTop: 16 }}>
                <h3>اقدامات مجاز فعلی</h3>
                {selected.status !== "active" ? (
                  <p className="muted">این گردش‌کار تکمیل شده و Transition جدیدی ندارد.</p>
                ) : transitions.length === 0 ? (
                  <p className="muted">
                    برای شما در State فعلی اقدام قابل اجرا وجود ندارد.
                  </p>
                ) : (
                  <form className="settingsForm" onSubmit={executeTransition}>
                    <label>
                      اقدام
                      <select value={transitionId} onChange={(event) => setTransitionId(event.target.value)}>
                        <option value="">انتخاب اقدام مجاز…</option>
                        {transitions.map((transition) => (
                          <option key={transition.id} value={transition.id}>
                            {transition.name} → {transition.to_state_detail.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      توضیح / یادداشت
                      <textarea
                        rows={4}
                        value={transitionComment}
                        onChange={(event) => setTransitionComment(event.target.value)}
                        style={{ padding: 10, border: "1px solid #cad7e4", borderRadius: 8 }}
                      />
                    </label>
                    <button className="primary" disabled={busy || !transitionId}>
                      اجرای تغییر وضعیت
                    </button>
                  </form>
                )}
              </div>

              <div style={{ borderTop: "1px solid #e5ebf2", paddingTop: 16 }}>
                <div className="roleTitle">
                  <h3>تاریخچه</h3>
                  <span className="pill">{events.length} رویداد</span>
                </div>
                {events.length === 0 ? (
                  <p className="muted">هنوز رویدادی ثبت نشده است.</p>
                ) : (
                  <div className="stack">
                    {events.map((event) => (
                      <div className="treatmentCard" key={event.id}>
                        <div className="roleTitle">
                          <strong>{eventLabels[event.event_type] ?? event.event_type}</strong>
                          <small className="muted">{formatDateTime(event.created_at)}</small>
                        </div>
                        <div className="permissionCloud">
                          <span className="pill">عامل: {event.actor_display}</span>
                          {event.transition_name && <span className="pill">{event.transition_name}</span>}
                          {event.event_type === "transition" && event.from_state_detail && (
                            <span className="pill">
                              {event.from_state_detail.name} ← {event.to_state_detail.name}
                            </span>
                          )}
                          {event.event_type === "assignment" && (
                            <span className="pill">{assignmentSummary(event)}</span>
                          )}
                        </div>
                        {event.comment && <p>{event.comment}</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      </div>

      <section className="panel" style={{ marginTop: 18 }}>
        <div className="roleTitle">
          <div>
            <h2>تعریف‌های گردش‌کار</h2>
            <p className="muted">در این Batch فقط نمای خواندنی تعریف‌ها نمایش داده می‌شود؛ Visual Builder اضافه نشده است.</p>
          </div>
          <span className="pill">{definitions.length} تعریف</span>
        </div>
        {definitions.length === 0 ? (
          <p className="muted">
            تعریف‌ها برای این کاربر قابل مشاهده نیستند یا تعریفی وجود ندارد. اجرای Instanceهای مجاز مستقل از این فهرست باقی می‌ماند.
          </p>
        ) : (
          <table className="dataTable">
            <thead>
              <tr>
                <th>نام</th>
                <th>حوزه</th>
                <th>نسخه</th>
                <th>State</th>
                <th>Transition</th>
                <th>فعال</th>
              </tr>
            </thead>
            <tbody>
              {definitions.map((definition) => (
                <tr key={definition.id}>
                  <td>{definition.name}</td>
                  <td>{objectTypeLabel(definition.object_type)}</td>
                  <td dir="ltr">{definition.version}</td>
                  <td>{definition.states?.length ?? 0}</td>
                  <td>{definition.transitions?.length ?? 0}</td>
                  <td>{definition.is_active ? "بله" : "خیر"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
