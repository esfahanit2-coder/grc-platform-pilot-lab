"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";

type DocumentRow = {
  id: string;
  organization_unit?: string | null;
  document_type: string;
  code: string;
  title: string;
  owner: number;
  owner_display: string;
  status: string;
  review_date?: string | null;
  current_version?: string | null;
  current_version_code?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type Version = {
  id: string;
  document: string;
  version: string;
  content: string;
  storage_key: string;
  change_summary: string;
  created_by: number;
  status: string;
  created_at: string;
  updated_at: string;
};

type Approval = {
  id: string;
  version: string;
  approver: number;
  approver_display: string;
  approval_order: number;
  decision: string;
  comment: string;
  decided_at?: string | null;
  created_at: string;
  can_decide: boolean;
};

type Unit = { id: string; code: string; name: string; unit_type: string };
type WorkspaceOptions = { tenant_scope_allowed: boolean; units: Unit[] };
type Participant = { id: number; username: string; display: string };

type DocumentForm = {
  scope_mode: "" | "tenant" | "unit";
  organization_unit: string;
  document_type: string;
  code: string;
  title: string;
  owner: string;
  review_date: string;
};

type VersionForm = {
  version: string;
  content: string;
  change_summary: string;
};

const emptyDocumentForm: DocumentForm = {
  scope_mode: "",
  organization_unit: "",
  document_type: "",
  code: "",
  title: "",
  owner: "",
  review_date: "",
};

const emptyVersionForm: VersionForm = { version: "", content: "", change_summary: "" };

const documentTypes: Array<[string, string]> = [
  ["policy", "خط‌مشی"],
  ["procedure", "روش اجرایی"],
  ["standard", "استاندارد"],
  ["guideline", "راهنما"],
  ["plan", "برنامه"],
  ["charter", "منشور"],
  ["form", "فرم"],
  ["record", "رکورد"],
  ["report", "گزارش"],
  ["minutes", "صورت‌جلسه"],
];

const statusLabels: Record<string, string> = {
  draft: "پیش‌نویس",
  review: "در بازبینی",
  approved: "تأییدشده",
  published: "منتشرشده",
  deprecated: "منسوخ",
  superseded: "جایگزین‌شده",
};

const decisionLabels: Record<string, string> = {
  pending: "در انتظار",
  approved: "تأیید",
  rejected: "رد",
  changes_requested: "نیازمند اصلاح",
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

function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value.includes("T") ? value : `${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fa-IR", { year: "numeric", month: "short", day: "numeric" }).format(date);
}

function typeLabel(value: string) {
  return documentTypes.find(([key]) => key === value)?.[1] ?? value;
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [options, setOptions] = useState<WorkspaceOptions>({ tenant_scope_allowed: false, units: [] });
  const [versions, setVersions] = useState<Version[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [ownerCandidates, setOwnerCandidates] = useState<Participant[]>([]);
  const [approverCandidates, setApproverCandidates] = useState<Participant[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [documentMode, setDocumentMode] = useState<"closed" | "create" | "edit">("closed");
  const [documentForm, setDocumentForm] = useState<DocumentForm>(emptyDocumentForm);
  const [versionMode, setVersionMode] = useState<"closed" | "create" | "edit">("closed");
  const [versionForm, setVersionForm] = useState<VersionForm>(emptyVersionForm);
  const [showApproverForm, setShowApproverForm] = useState(false);
  const [approverId, setApproverId] = useState("");
  const [approvalOrder, setApprovalOrder] = useState(1);
  const [decisionDrafts, setDecisionDrafts] = useState<Record<string, { decision: string; comment: string }>>({});

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedId) ?? null,
    [documents, selectedId],
  );
  const selectedVersion = useMemo(
    () => versions.find((version) => version.id === selectedVersionId) ?? null,
    [versions, selectedVersionId],
  );

  const manageableUnitIds = useMemo(() => new Set(options.units.map((unit) => unit.id)), [options.units]);

  const canManageDocument = (document: DocumentRow | null) => {
    if (!document) return false;
    if (!document.organization_unit) return options.tenant_scope_allowed;
    return manageableUnitIds.has(document.organization_unit);
  };

  const filteredDocuments = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase("fa");
    return documents.filter((document) => {
      if (statusFilter !== "all" && document.status !== statusFilter) return false;
      if (typeFilter !== "all" && document.document_type !== typeFilter) return false;
      if (!needle) return true;
      return [document.code, document.title, document.owner_display]
        .filter(Boolean)
        .some((value) => value.toLocaleLowerCase("fa").includes(needle));
    });
  }, [documents, search, statusFilter, typeFilter]);

  async function loadBase() {
    setLoading(true);
    setError("");
    try {
      const [documentResponse, optionResponse] = await Promise.all([
        apiFetch("/documents/?page_size=500"),
        apiFetch("/documents/workspace-options/"),
      ]);
      const [documentBody, optionBody] = await Promise.all([
        documentResponse.json().catch(() => ({})),
        optionResponse.json().catch(() => ({})),
      ]);
      if (!documentResponse.ok) throw new Error(apiError(documentBody, "دریافت مستندات ناموفق بود."));
      if (!optionResponse.ok) throw new Error(apiError(optionBody, "دریافت دسترسی‌های Workspace ناموفق بود."));
      const documentRows = rows<DocumentRow>(documentBody);
      setDocuments(documentRows);
      setOptions({
        tenant_scope_allowed: Boolean(optionBody.tenant_scope_allowed),
        units: Array.isArray(optionBody.units) ? optionBody.units : [],
      });
      if (selectedId && !documentRows.some((item) => item.id === selectedId)) {
        setSelectedId(null);
        setSelectedVersionId(null);
        setVersions([]);
        setApprovals([]);
      }
      return documentRows;
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "دریافت Workspace مستندات ناموفق بود.");
      return [] as DocumentRow[];
    } finally {
      setLoading(false);
    }
  }

  async function loadApprovals(versionId: string) {
    const response = await apiFetch(`/document-approvals/?version=${encodeURIComponent(versionId)}&page_size=200`);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(apiError(body, "دریافت تأییدکنندگان ناموفق بود."));
    setApprovals(rows<Approval>(body));
  }

  async function loadVersions(document: DocumentRow, preferredVersionId?: string | null) {
    setDetailLoading(true);
    setError("");
    try {
      const response = await apiFetch(`/document-versions/?document=${encodeURIComponent(document.id)}&page_size=200`);
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(body, "دریافت نسخه‌های مستند ناموفق بود."));
      const versionRows = rows<Version>(body);
      setVersions(versionRows);
      const candidate = preferredVersionId && versionRows.some((item) => item.id === preferredVersionId)
        ? preferredVersionId
        : document.current_version && versionRows.some((item) => item.id === document.current_version)
          ? document.current_version
          : null;
      setSelectedVersionId(candidate);
      if (candidate) await loadApprovals(candidate);
      else setApprovals([]);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "دریافت جزئیات مستند ناموفق بود.");
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    void loadBase();
  }, []);

  async function selectDocument(document: DocumentRow) {
    setSelectedId(document.id);
    setDocumentMode("closed");
    setVersionMode("closed");
    setShowApproverForm(false);
    setMessage("");
    await loadVersions(document);
  }

  async function selectVersion(id: string) {
    setSelectedVersionId(id);
    setVersionMode("closed");
    setShowApproverForm(false);
    setError("");
    try {
      await loadApprovals(id);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "دریافت تأییدها ناموفق بود.");
    }
  }

  async function refreshSelected(preferredVersionId?: string | null) {
    const documentRows = await loadBase();
    if (!selectedId) return;
    const document = documentRows.find((item) => item.id === selectedId);
    if (document) await loadVersions(document, preferredVersionId ?? selectedVersionId);
  }

  async function loadParticipants(kind: "owner" | "approver", unitId: string | null) {
    const query = new URLSearchParams({ kind });
    if (unitId) query.set("organization_unit", unitId);
    const response = await apiFetch(`/documents/participants/?${query.toString()}`);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(apiError(body, "دریافت کاربران مجاز ناموفق بود."));
    const participantRows = Array.isArray(body.results) ? body.results as Participant[] : [];
    if (kind === "owner") setOwnerCandidates(participantRows);
    else setApproverCandidates(participantRows);
  }

  function resetDocumentForm() {
    setDocumentForm(emptyDocumentForm);
    setOwnerCandidates([]);
  }

  function beginCreateDocument() {
    resetDocumentForm();
    setDocumentMode("create");
    setMessage("");
    setError("");
  }

  async function beginEditDocument() {
    if (!selectedDocument || !canManageDocument(selectedDocument)) return;
    const scopeMode = selectedDocument.organization_unit ? "unit" : "tenant";
    setDocumentForm({
      scope_mode: scopeMode,
      organization_unit: selectedDocument.organization_unit ?? "",
      document_type: selectedDocument.document_type,
      code: selectedDocument.code,
      title: selectedDocument.title,
      owner: String(selectedDocument.owner),
      review_date: selectedDocument.review_date ?? "",
    });
    setDocumentMode("edit");
    setError("");
    try {
      await loadParticipants("owner", selectedDocument.organization_unit ?? null);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "دریافت مالکان مجاز ناموفق بود.");
    }
  }

  async function chooseDocumentScope(scopeMode: "" | "tenant" | "unit", unitId = "") {
    setDocumentForm((current) => ({ ...current, scope_mode: scopeMode, organization_unit: unitId, owner: "" }));
    setOwnerCandidates([]);
    if (!scopeMode) return;
    if (scopeMode === "tenant" && !options.tenant_scope_allowed) return;
    if (scopeMode === "unit" && !unitId) return;
    try {
      await loadParticipants("owner", scopeMode === "unit" ? unitId : null);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "دریافت مالکان مجاز ناموفق بود.");
    }
  }

  async function saveDocument(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!documentForm.scope_mode) {
      setError("دامنه مستند را صریحاً انتخاب کنید.");
      return;
    }
    if (documentForm.scope_mode === "unit" && !documentForm.organization_unit) {
      setError("واحد سازمانی را انتخاب کنید.");
      return;
    }
    if (!documentForm.document_type || !documentForm.code.trim() || !documentForm.title.trim() || !documentForm.owner) {
      setError("نوع، کد، عنوان و مالک مستند الزامی است.");
      return;
    }
    setBusy(true);
    try {
      const payload = {
        organization_unit: documentForm.scope_mode === "tenant" ? null : documentForm.organization_unit,
        document_type: documentForm.document_type,
        code: documentForm.code.trim(),
        title: documentForm.title.trim(),
        owner: Number(documentForm.owner),
        review_date: documentForm.review_date || null,
      };
      const response = await apiFetch(
        documentMode === "edit" && selectedDocument ? `/documents/${selectedDocument.id}/` : "/documents/",
        {
          method: documentMode === "edit" ? "PATCH" : "POST",
          body: JSON.stringify(payload),
        },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(body, "ذخیره مستند ناموفق بود."));
      setDocumentMode("closed");
      resetDocumentForm();
      setMessage(documentMode === "edit" ? "مشخصات مستند ذخیره شد." : "مستند ساخته شد. اکنون یک نسخه Draft ایجاد کنید.");
      const rowsAfter = await loadBase();
      const id = String(body.id ?? selectedDocument?.id ?? "");
      if (id) {
        const document = rowsAfter.find((item) => item.id === id);
        if (document) {
          setSelectedId(id);
          await loadVersions(document);
        }
      }
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "ذخیره مستند ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  async function archiveDocument() {
    if (!selectedDocument || !canManageDocument(selectedDocument)) return;
    if (!window.confirm(`مستند «${selectedDocument.title}» آرشیو/منسوخ شود؟`)) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await apiFetch(`/documents/${selectedDocument.id}/`, { method: "DELETE" });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(apiError(body, "آرشیو مستند ناموفق بود."));
      }
      setSelectedId(null);
      setSelectedVersionId(null);
      setVersions([]);
      setApprovals([]);
      setMessage("مستند آرشیو شد.");
      await loadBase();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "آرشیو مستند ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  function beginCreateVersion() {
    setVersionForm(emptyVersionForm);
    setVersionMode("create");
    setMessage("");
    setError("");
  }

  function beginEditVersion() {
    if (!selectedVersion) return;
    setVersionForm({
      version: selectedVersion.version,
      content: selectedVersion.content,
      change_summary: selectedVersion.change_summary,
    });
    setVersionMode("edit");
    setError("");
  }

  async function saveVersion(event: FormEvent) {
    event.preventDefault();
    if (!selectedDocument) return;
    setError("");
    setMessage("");
    if (!versionForm.version.trim()) {
      setError("شماره/کد نسخه الزامی است.");
      return;
    }
    setBusy(true);
    try {
      const payload = {
        document: selectedDocument.id,
        version: versionForm.version.trim(),
        content: versionForm.content,
        change_summary: versionForm.change_summary,
      };
      const editing = versionMode === "edit" && selectedVersion;
      const response = await apiFetch(
        editing ? `/document-versions/${selectedVersion.id}/` : "/document-versions/",
        { method: editing ? "PATCH" : "POST", body: JSON.stringify(payload) },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(body, "ذخیره نسخه ناموفق بود."));
      setVersionMode("closed");
      setVersionForm(emptyVersionForm);
      setMessage(editing ? "Draft نسخه ذخیره شد." : "نسخه Draft ایجاد و به‌عنوان نسخه جاری انتخاب شد.");
      await refreshSelected(String(body.id ?? selectedVersion?.id ?? ""));
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "ذخیره نسخه ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  async function beginAddApprover() {
    if (!selectedDocument || !selectedVersion) return;
    setShowApproverForm(true);
    setApproverId("");
    setApprovalOrder(approvals.length + 1);
    setError("");
    try {
      await loadParticipants("approver", selectedDocument.organization_unit ?? null);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "دریافت تأییدکنندگان مجاز ناموفق بود.");
    }
  }

  async function addApprover(event: FormEvent) {
    event.preventDefault();
    if (!selectedVersion || !approverId) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await apiFetch("/document-approvals/", {
        method: "POST",
        body: JSON.stringify({
          version: selectedVersion.id,
          approver: Number(approverId),
          approval_order: approvalOrder,
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(body, "تخصیص تأییدکننده ناموفق بود."));
      setShowApproverForm(false);
      setApproverId("");
      setMessage("تأییدکننده به Draft اضافه شد.");
      await loadApprovals(selectedVersion.id);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "تخصیص تأییدکننده ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  async function removeApprover(approval: Approval) {
    if (!window.confirm(`تأییدکننده «${approval.approver_display}» از این Draft حذف شود؟`)) return;
    setBusy(true);
    setError("");
    try {
      const response = await apiFetch(`/document-approvals/${approval.id}/`, { method: "DELETE" });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(apiError(body, "حذف تأییدکننده ناموفق بود."));
      }
      setMessage("تأییدکننده حذف شد.");
      if (selectedVersion) await loadApprovals(selectedVersion.id);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "حذف تأییدکننده ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  async function submitForReview() {
    if (!selectedVersion) return;
    if (!window.confirm("این Draft برای بازبینی ارسال شود؟ پس از ارسال، محتوای همین نسخه قابل ویرایش نیست.")) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await apiFetch(`/document-versions/${selectedVersion.id}/submit/`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(body, "ارسال برای بازبینی ناموفق بود."));
      setMessage("نسخه وارد چرخه بازبینی شد.");
      await refreshSelected(selectedVersion.id);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "ارسال برای بازبینی ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  async function decideApproval(approval: Approval) {
    const draft = decisionDrafts[approval.id] ?? { decision: "", comment: "" };
    if (!draft.decision) {
      setError("تصمیم بازبینی را انتخاب کنید.");
      return;
    }
    if (!window.confirm("تصمیم ثبت شود؟ این تصمیم تاریخچه حاکمیتی مستند است و قابل بازنویسی نیست.")) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await apiFetch(`/document-approvals/${approval.id}/decide/`, {
        method: "POST",
        body: JSON.stringify(draft),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(apiError(body, "ثبت تصمیم ناموفق بود."));
      setDecisionDrafts((current) => {
        const next = { ...current };
        delete next[approval.id];
        return next;
      });
      setMessage(
        draft.decision === "approved"
          ? "تصمیم تأیید ثبت شد."
          : "تصمیم بازبینی ثبت شد؛ برای اصلاح، نسخه Draft جدید ایجاد کنید.",
      );
      await refreshSelected(selectedVersionId);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "ثبت تصمیم ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  async function exportVersion() {
    if (!selectedDocument || !selectedVersion) return;
    setBusy(true);
    setError("");
    try {
      const response = await apiFetch(`/document-versions/${selectedVersion.id}/export/`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(apiError(body, "خروجی DOCX ناموفق بود."));
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${selectedDocument.code}-${selectedVersion.version}.docx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "خروجی DOCX ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  const selectedMutableDraft = Boolean(
    selectedDocument
    && selectedVersion
    && canManageDocument(selectedDocument)
    && selectedVersion.status === "draft"
    && selectedDocument.current_version === selectedVersion.id,
  );

  const canCreateVersion = Boolean(
    selectedDocument
    && canManageDocument(selectedDocument)
    && selectedDocument.status !== "review",
  );

  return (
    <main className="adminPage">
      <div className="pageHead">
        <div>
          <Link href="/">← داشبورد</Link>
          <h1>مستندات کنترل‌شده</h1>
          <p>ایجاد، نسخه‌بندی، بازبینی، تأیید و خروجی مستند با چرخه عمر و RBAC سمت سرور</p>
        </div>
        <div className="headActions">
          <Link href="/work" className="secondaryLink">کارهای من / صف تأیید</Link>
          <button className="secondaryLink" onClick={() => void loadBase()} disabled={loading || busy}>به‌روزرسانی</button>
          {(options.tenant_scope_allowed || options.units.length > 0) && (
            <button className="primary" onClick={beginCreateDocument}>+ مستند جدید</button>
          )}
        </div>
      </div>

      {error && <div className="message">{error}</div>}
      {message && <div className="message successText">{message}</div>}

      {documentMode !== "closed" && (
        <form className="panel settingsForm" onSubmit={saveDocument} style={{ marginBottom: 18 }}>
          <div className="roleTitle">
            <h2>{documentMode === "create" ? "ایجاد مستند کنترل‌شده" : "ویرایش مشخصات مستند"}</h2>
            <button type="button" onClick={() => { setDocumentMode("closed"); resetDocumentForm(); }}>بستن</button>
          </div>
          <label>دامنه *
            <select
              value={documentForm.scope_mode}
              onChange={(event) => void chooseDocumentScope(event.target.value as "" | "tenant" | "unit")}
              disabled={documentMode === "edit" && Boolean(selectedDocument?.current_version && selectedVersion?.status !== "draft")}
            >
              <option value="">انتخاب صریح دامنه…</option>
              {options.tenant_scope_allowed && <option value="tenant">کل Tenant</option>}
              {options.units.length > 0 && <option value="unit">واحد سازمانی مشخص</option>}
            </select>
          </label>
          {documentForm.scope_mode === "unit" && (
            <label>واحد سازمانی *
              <select
                value={documentForm.organization_unit}
                onChange={(event) => void chooseDocumentScope("unit", event.target.value)}
              >
                <option value="">انتخاب واحد…</option>
                {options.units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name} · {unit.code}</option>)}
              </select>
            </label>
          )}
          <label>نوع مستند *
            <select value={documentForm.document_type} onChange={(event) => setDocumentForm({ ...documentForm, document_type: event.target.value })}>
              <option value="">انتخاب نوع…</option>
              {documentTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label>کد مستند *<input dir="ltr" value={documentForm.code} onChange={(event) => setDocumentForm({ ...documentForm, code: event.target.value })} /></label>
          <label>عنوان *<input value={documentForm.title} onChange={(event) => setDocumentForm({ ...documentForm, title: event.target.value })} /></label>
          <label>مالک *
            <select value={documentForm.owner} onChange={(event) => setDocumentForm({ ...documentForm, owner: event.target.value })} disabled={!documentForm.scope_mode}>
              <option value="">انتخاب مالک مجاز…</option>
              {ownerCandidates.map((person) => <option key={person.id} value={person.id}>{person.display} · {person.username}</option>)}
            </select>
          </label>
          <label>تاریخ بازنگری<input type="date" value={documentForm.review_date} onChange={(event) => setDocumentForm({ ...documentForm, review_date: event.target.value })} /></label>
          <small className="muted">وضعیت و نسخه جاری از این فرم قابل تغییر نیستند؛ چرخه عمر فقط از عملیات نسخه/بازبینی کنترل می‌شود.</small>
          <button className="primary" disabled={busy}>ذخیره مستند</button>
        </form>
      )}

      <div className="toolbar" style={{ flexWrap: "wrap" }}>
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="جستجو بر اساس کد، عنوان یا مالک…" />
        <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
          <option value="all">همه انواع</option>
          {documentTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="all">همه وضعیت‌ها</option>
          {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>

      <div className="grid" style={{ alignItems: "start", gridTemplateColumns: "minmax(420px, .9fr) minmax(520px, 1.1fr)" }}>
        <section className="panel">
          <div className="roleTitle"><h2>کتابخانه مستندات</h2><span className="pill">{filteredDocuments.length} مورد</span></div>
          {loading ? (
            <p className="muted">در حال دریافت مستندات…</p>
          ) : filteredDocuments.length === 0 ? (
            <p className="muted">در فیلتر فعلی مستندی وجود ندارد.</p>
          ) : (
            <table className="dataTable">
              <thead><tr><th>کد/عنوان</th><th>نوع</th><th>نسخه جاری</th><th>وضعیت</th><th></th></tr></thead>
              <tbody>
                {filteredDocuments.map((document) => (
                  <tr key={document.id}>
                    <td><strong dir="ltr">{document.code}</strong><div>{document.title}</div><small className="muted">{document.owner_display}</small></td>
                    <td>{typeLabel(document.document_type)}</td>
                    <td dir="ltr">{document.current_version_code ?? "—"}</td>
                    <td><span className="pill">{statusLabels[document.status] ?? document.status}</span></td>
                    <td><button onClick={() => void selectDocument(document)}>{selectedId === document.id ? "انتخاب‌شده" : "باز کردن"}</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="panel">
          {!selectedDocument ? (
            <div className="stack">
              <h2>Workspace مستند</h2>
              <p className="muted">یک مستند را صریحاً از جدول انتخاب کنید. هیچ رکوردی به‌صورت خودکار انتخاب نمی‌شود.</p>
            </div>
          ) : detailLoading ? (
            <p className="muted">در حال دریافت تاریخچه مستند…</p>
          ) : (
            <div className="stack">
              <div className="roleTitle">
                <div>
                  <h2>{selectedDocument.title}</h2>
                  <code dir="ltr">{selectedDocument.code}</code>
                </div>
                <span className="pill">{statusLabels[selectedDocument.status] ?? selectedDocument.status}</span>
              </div>
              <div className="permissionCloud">
                <span className="pill">{typeLabel(selectedDocument.document_type)}</span>
                <span className="pill">مالک: {selectedDocument.owner_display}</span>
                <span className="pill">بازنگری: {formatDate(selectedDocument.review_date)}</span>
              </div>

              {canManageDocument(selectedDocument) && (
                <div className="headActions" style={{ flexWrap: "wrap" }}>
                  <button onClick={() => void beginEditDocument()}>ویرایش مشخصات</button>
                  {canCreateVersion && <button className="primary" onClick={beginCreateVersion}>+ نسخه Draft جدید</button>}
                  <button onClick={() => void archiveDocument()} disabled={busy || selectedDocument.status === "review"}>آرشیو مستند</button>
                </div>
              )}

              {versionMode !== "closed" && (
                <form className="settingsForm" onSubmit={saveVersion} style={{ borderTop: "1px solid #e5ebf2", paddingTop: 16 }}>
                  <div className="roleTitle">
                    <h3>{versionMode === "create" ? "نسخه Draft جدید" : "ویرایش Draft جاری"}</h3>
                    <button type="button" onClick={() => setVersionMode("closed")}>بستن</button>
                  </div>
                  <label>نسخه *<input dir="ltr" value={versionForm.version} onChange={(event) => setVersionForm({ ...versionForm, version: event.target.value })} /></label>
                  <label>خلاصه تغییرات<textarea rows={3} value={versionForm.change_summary} onChange={(event) => setVersionForm({ ...versionForm, change_summary: event.target.value })} style={{ padding: 10, border: "1px solid #cad7e4", borderRadius: 8 }} /></label>
                  <label>محتوای کنترل‌شده<textarea rows={12} value={versionForm.content} onChange={(event) => setVersionForm({ ...versionForm, content: event.target.value })} style={{ padding: 12, border: "1px solid #cad7e4", borderRadius: 8, lineHeight: 1.9 }} /></label>
                  <button className="primary" disabled={busy}>ذخیره Draft</button>
                </form>
              )}

              <div>
                <div className="roleTitle"><h3>تاریخچه نسخه‌ها</h3><span className="pill">{versions.length} نسخه</span></div>
                {versions.length === 0 ? (
                  <p className="muted">هنوز نسخه‌ای ایجاد نشده است.</p>
                ) : (
                  <div className="permissionCloud">
                    {versions.map((version) => (
                      <button
                        key={version.id}
                        onClick={() => void selectVersion(version.id)}
                        className={selectedVersionId === version.id ? "primary" : ""}
                        style={{ direction: "ltr" }}
                      >
                        {version.version} · {statusLabels[version.status] ?? version.status}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {selectedVersion && (
                <div className="stack" style={{ borderTop: "1px solid #e5ebf2", paddingTop: 16 }}>
                  <div className="roleTitle">
                    <div>
                      <h3>نسخه <span dir="ltr">{selectedVersion.version}</span></h3>
                      <small className="muted">ایجاد: {formatDate(selectedVersion.created_at)}</small>
                    </div>
                    <span className="pill">{statusLabels[selectedVersion.status] ?? selectedVersion.status}</span>
                  </div>
                  {selectedVersion.change_summary && <div className="message"><strong>خلاصه تغییرات:</strong> {selectedVersion.change_summary}</div>}
                  <div className="panel" style={{ background: "#f9fbfd", boxShadow: "none", whiteSpace: "pre-wrap", lineHeight: 1.9 }}>
                    {selectedVersion.content || <span className="muted">محتوای متنی برای این نسخه ثبت نشده است.</span>}
                  </div>
                  <div className="headActions" style={{ flexWrap: "wrap" }}>
                    <button onClick={() => void exportVersion()} disabled={busy}>خروجی DOCX ثبت‌شونده در Audit</button>
                    {selectedMutableDraft && <button onClick={beginEditVersion}>ویرایش Draft</button>}
                    {selectedMutableDraft && <button onClick={() => void beginAddApprover()}>+ تأییدکننده</button>}
                    {selectedMutableDraft && approvals.length > 0 && <button className="primary" onClick={() => void submitForReview()} disabled={busy}>ارسال برای بازبینی</button>}
                  </div>

                  {selectedVersion.status !== "draft" && (
                    <div className="message">این نسخه وارد چرخه حاکمیتی شده و محتوای آن دیگر از UI یا API عادی قابل ویرایش نیست.</div>
                  )}

                  {showApproverForm && selectedMutableDraft && (
                    <form className="settingsForm" onSubmit={addApprover}>
                      <h3>افزودن تأییدکننده</h3>
                      <label>تأییدکننده *
                        <select value={approverId} onChange={(event) => setApproverId(event.target.value)}>
                          <option value="">انتخاب کاربر دارای document.approve…</option>
                          {approverCandidates.map((person) => <option key={person.id} value={person.id}>{person.display} · {person.username}</option>)}
                        </select>
                      </label>
                      <label>مرحله تأیید<input type="number" min={1} value={approvalOrder} onChange={(event) => setApprovalOrder(Number(event.target.value))} /></label>
                      <small className="muted">افراد با شماره مرحله یکسان می‌توانند موازی تصمیم بگیرند؛ مرحله بعد فقط پس از تأیید کامل مرحله قبل باز می‌شود.</small>
                      <div className="headActions"><button className="primary" disabled={busy || !approverId}>ثبت تأییدکننده</button><button type="button" onClick={() => setShowApproverForm(false)}>انصراف</button></div>
                    </form>
                  )}

                  <div>
                    <h3>چرخه تأیید</h3>
                    {approvals.length === 0 ? (
                      <p className="muted">برای این نسخه تأییدکننده فعالی ثبت نشده است.</p>
                    ) : approvals.map((approval) => {
                      const decision = decisionDrafts[approval.id] ?? { decision: "", comment: "" };
                      return (
                        <div className="treatmentCard" key={approval.id}>
                          <div className="roleTitle">
                            <strong>{approval.approver_display}</strong>
                            <span className="pill">مرحله {approval.approval_order} · {decisionLabels[approval.decision] ?? approval.decision}</span>
                          </div>
                          {approval.decided_at && <small className="muted">تصمیم: {formatDate(approval.decided_at)}</small>}
                          {approval.comment && <p>{approval.comment}</p>}
                          {selectedMutableDraft && approval.decision === "pending" && (
                            <button onClick={() => void removeApprover(approval)} disabled={busy}>حذف از Draft</button>
                          )}
                          {approval.can_decide && (
                            <div className="settingsForm" style={{ marginTop: 12 }}>
                              <label>تصمیم
                                <select
                                  value={decision.decision}
                                  onChange={(event) => setDecisionDrafts({
                                    ...decisionDrafts,
                                    [approval.id]: { ...decision, decision: event.target.value },
                                  })}
                                >
                                  <option value="">انتخاب تصمیم…</option>
                                  <option value="approved">تأیید</option>
                                  <option value="changes_requested">نیازمند اصلاح</option>
                                  <option value="rejected">رد</option>
                                </select>
                              </label>
                              <label>نظر بازبین<textarea rows={3} value={decision.comment} onChange={(event) => setDecisionDrafts({ ...decisionDrafts, [approval.id]: { ...decision, comment: event.target.value } })} style={{ padding: 10, border: "1px solid #cad7e4", borderRadius: 8 }} /></label>
                              <button className="primary" onClick={() => void decideApproval(approval)} disabled={busy}>ثبت تصمیم</button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
