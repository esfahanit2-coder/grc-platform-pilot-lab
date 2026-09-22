"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import {
  Button,
  EmptyState,
  FormField,
  Input,
  PageHeader,
  Select,
  StatusMessage,
  Surface,
  TechnicalText,
  Textarea,
} from "../../components/ui";

type Asset = {
  id: string;
  code: string;
  title: string;
  asset_type: string;
  organization_name: string;
  owner_display: string;
  custodian_display?: string | null;
  confidentiality: number;
  integrity: number;
  availability: number;
  criticality: string;
  status: string;
};

type OptionUnit = { id: string; code: string; name: string };
type OptionUser = { id: number; username: string; display: string };
type SelectorOptions = { organization_units: OptionUnit[]; users: OptionUser[] };

const typeLabels: Record<string, string> = {
  information: "اطلاعات",
  hardware: "سخت‌افزار",
  software: "نرم‌افزار",
  application: "کاربرد",
  database: "پایگاه داده",
  cloud_service: "سرویس ابری",
  service: "سرویس",
  process: "فرآیند",
  person: "فرد",
  site: "سایت",
  other: "سایر",
};

const statusLabels: Record<string, string> = {
  active: "فعال",
  retired: "بازنشسته",
  archived: "آرشیو",
};

const emptyForm = {
  code: "",
  title: "",
  asset_type: "application",
  organization_unit: "",
  owner: "",
  custodian: "",
  description: "",
  confidentiality: "3",
  integrity: "3",
  availability: "3",
  criticality: "3",
  status: "active",
};

async function responseError(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (typeof body?.detail === "string") return body.detail;
  return "عملیات ناموفق بود. مجوزها و مقادیر ورودی را بررسی کنید.";
}

export default function AssetsPage() {
  const [rows, setRows] = useState<Asset[]>([]);
  const [options, setOptions] = useState<SelectorOptions | null>(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");

    const q = new URLSearchParams({ page: String(page) });
    if (search.trim()) q.set("search", search.trim());
    if (typeFilter) q.set("asset_type", typeFilter);
    if (statusFilter) q.set("status", statusFilter);

    const response = await apiFetch("/assets/?" + q.toString());
    if (!response.ok) {
      setRows([]);
      setError(await responseError(response));
      setLoading(false);
      return;
    }

    const body = await response.json();
    if (Array.isArray(body)) {
      setRows(body);
      setCount(body.length);
    } else {
      setRows(body.results ?? []);
      setCount(body.count ?? (body.results?.length ?? 0));
    }
    setLoading(false);
  }, [search, typeFilter, statusFilter, page]);

  useEffect(() => {
    void load();
  }, [load]);

  async function openCreate() {
    setMessage("");
    setError("");
    const response = await apiFetch("/assets/selector-options/");
    if (!response.ok) {
      setError("فرم ایجاد دارایی برای این حساب قابل استفاده نیست یا مجوز asset.manage ندارید.");
      return;
    }
    const body = (await response.json()) as SelectorOptions;
    setOptions(body);
    setForm(emptyForm);
    setShowCreate(true);
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    if (!form.organization_unit || !form.owner) {
      setError("واحد سازمانی و مالک را انتخاب کنید.");
      return;
    }

    setSaving(true);
    setError("");
    setMessage("");

    const payload = {
      ...form,
      owner: Number(form.owner),
      custodian: form.custodian ? Number(form.custodian) : null,
      confidentiality: Number(form.confidentiality),
      integrity: Number(form.integrity),
      availability: Number(form.availability),
      criticality: form.criticality,
      metadata: {},
    };

    const response = await apiFetch("/assets/", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      setError(await responseError(response));
      setSaving(false);
      return;
    }

    setMessage("دارایی با موفقیت ثبت شد.");
    setShowCreate(false);
    setForm(emptyForm);
    setSaving(false);

    if (page === 1) await load();
    else setPage(1);
  }

  const field = (key: keyof typeof emptyForm, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  const pageCount = Math.max(1, Math.ceil(count / 50));

  return (
    <main className="adminPage" dir="rtl">
      <PageHeader
        eyebrow={<Link href="/">بازگشت به داشبورد</Link>}
        title="دفتر دارایی‌ها"
        description="مالکیت، CIA، بحرانی‌بودن و ردیابی وابستگی‌های دارایی"
        actions={<Button onClick={() => void openCreate()}>+ دارایی جدید</Button>}
      />

      {message ? <StatusMessage tone="success">{message}</StatusMessage> : null}
      {error ? <StatusMessage tone="danger">{error}</StatusMessage> : null}

      {showCreate && options ? (
        <Surface className="stack">
          <div className="roleTitle">
            <div>
              <h2>دارایی جدید</h2>
              <p className="muted">مالک و واحد سازمانی از گزینه‌های مجاز حساب جاری انتخاب می‌شوند.</p>
            </div>
            <Button variant="secondary" onClick={() => setShowCreate(false)}>بستن</Button>
          </div>

          <form onSubmit={create}>
            <div className="uiFormGrid">
              <FormField label="کد" required>
                <Input dir="ltr" value={form.code} onChange={(e) => field("code", e.target.value)} required />
              </FormField>

              <FormField label="عنوان" required>
                <Input value={form.title} onChange={(e) => field("title", e.target.value)} required />
              </FormField>

              <FormField label="نوع" required>
                <Select value={form.asset_type} onChange={(e) => field("asset_type", e.target.value)}>
                  {Object.entries(typeLabels).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </Select>
              </FormField>

              <FormField label="واحد سازمانی" required>
                <Select value={form.organization_unit} onChange={(e) => field("organization_unit", e.target.value)} required>
                  <option value="">انتخاب کنید</option>
                  {options.organization_units.map((unit) => (
                    <option key={unit.id} value={unit.id}>{unit.code} — {unit.name}</option>
                  ))}
                </Select>
              </FormField>

              <FormField label="مالک" required>
                <Select value={form.owner} onChange={(e) => field("owner", e.target.value)} required>
                  <option value="">انتخاب کنید</option>
                  {options.users.map((user) => (
                    <option key={user.id} value={user.id}>{user.display} ({user.username})</option>
                  ))}
                </Select>
              </FormField>

              <FormField label="متولی" hint="اختیاری؛ برای مسئول نگهداری یا بهره‌برداری">
                <Select value={form.custodian} onChange={(e) => field("custodian", e.target.value)}>
                  <option value="">بدون متولی</option>
                  {options.users.map((user) => (
                    <option key={user.id} value={user.id}>{user.display} ({user.username})</option>
                  ))}
                </Select>
              </FormField>

              <FormField label="محرمانگی (C)">
                <Select value={form.confidentiality} onChange={(e) => field("confidentiality", e.target.value)}>
                  {[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value}</option>)}
                </Select>
              </FormField>

              <FormField label="یکپارچگی (I)">
                <Select value={form.integrity} onChange={(e) => field("integrity", e.target.value)}>
                  {[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value}</option>)}
                </Select>
              </FormField>

              <FormField label="دسترس‌پذیری (A)">
                <Select value={form.availability} onChange={(e) => field("availability", e.target.value)}>
                  {[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value}</option>)}
                </Select>
              </FormField>

              <FormField label="بحرانی‌بودن">
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  dir="ltr"
                  value={form.criticality}
                  onChange={(e) => field("criticality", e.target.value)}
                />
              </FormField>

              <FormField label="وضعیت">
                <Select value={form.status} onChange={(e) => field("status", e.target.value)}>
                  {Object.entries(statusLabels)
                    .filter(([value]) => value !== "archived")
                    .map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </Select>
              </FormField>
            </div>

            <FormField label="توضیحات" className="stack">
              <Textarea value={form.description} onChange={(e) => field("description", e.target.value)} />
            </FormField>

            <div className="uiFormActions">
              <Button type="submit" busy={saving}>ثبت دارایی</Button>
            </div>
          </form>
        </Surface>
      ) : null}

      <div className="uiToolbar">
        <Input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="جستجو در کد، عنوان یا توضیحات"
          aria-label="جستجوی دارایی‌ها"
        />
        <Select
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value);
            setPage(1);
          }}
          aria-label="فیلتر نوع دارایی"
        >
          <option value="">همه انواع</option>
          {Object.entries(typeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </Select>
        <Select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          aria-label="فیلتر وضعیت دارایی"
        >
          <option value="">همه وضعیت‌ها</option>
          {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </Select>
      </div>

      <Surface padded={false}>
        {loading ? (
          <EmptyState title="در حال دریافت دارایی‌ها…" />
        ) : rows.length === 0 ? (
          <EmptyState
            title="دارایی‌ای مطابق فیلترها یافت نشد."
            description="عبارت جستجو یا فیلترها را تغییر دهید، یا در صورت داشتن مجوز یک دارایی جدید ثبت کنید."
          />
        ) : (
          <div className="uiTableWrap">
            <table className="uiTable">
              <thead>
                <tr>
                  <th>کد</th>
                  <th>دارایی</th>
                  <th>نوع</th>
                  <th>واحد</th>
                  <th>مالک</th>
                  <th>C/I/A</th>
                  <th>بحرانی‌بودن</th>
                  <th>وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((asset) => (
                  <tr key={asset.id}>
                    <td><TechnicalText>{asset.code}</TechnicalText></td>
                    <td><Link href={"/assets/" + asset.id}>{asset.title}</Link></td>
                    <td>{typeLabels[asset.asset_type] ?? asset.asset_type}</td>
                    <td>{asset.organization_name}</td>
                    <td>{asset.owner_display}</td>
                    <td><TechnicalText>{asset.confidentiality}/{asset.integrity}/{asset.availability}</TechnicalText></td>
                    <td><TechnicalText>{asset.criticality}</TechnicalText></td>
                    <td>{statusLabels[asset.status] ?? asset.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {count > 50 ? (
          <div className="uiPagination">
            <Button
              variant="secondary"
              size="sm"
              disabled={page <= 1 || loading}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
            >
              صفحه قبل
            </Button>
            <span>صفحه {page} از {pageCount} · {count} رکورد</span>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= pageCount || loading}
              onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
            >
              صفحه بعد
            </Button>
          </div>
        ) : null}
      </Surface>
    </main>
  );
}
