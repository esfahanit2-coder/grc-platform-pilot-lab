"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

type Framework = {
  id: string; code: string; name: string; publisher: string; framework_type: string;
  license_type: string; status: string; is_global: boolean; versions_count: number;
};

export default function FrameworkLibraryPage() {
  const [rows, setRows] = useState<Framework[]>([]);
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("در حال دریافت چارچوب‌ها...");

  async function load(search = "") {
    const response = await apiFetch(`/frameworks/?search=${encodeURIComponent(search)}`);
    if (!response.ok) { setMessage("برای مشاهده چارچوب‌ها ابتدا وارد شوید و Tenant را انتخاب کنید."); return; }
    const body = await response.json();
    setRows(body.results ?? body); setMessage("");
  }
  useEffect(() => { load(); }, []);

  return <main className="adminPage">
    <div className="pageHead">
      <div><h1>کتابخانه چارچوب‌ها</h1><p>استانداردها، مقررات و چارچوب‌های اختصاصی به‌صورت داده نسخه‌دار مدیریت می‌شوند.</p></div>
      <div className="headActions"><Link className="secondaryLink" href="/frameworks/crosswalk">Crosswalk</Link><Link className="secondaryLink" href="/frameworks/import">Import</Link><Link className="primary linkButton" href="/frameworks/new">+ چارچوب جدید</Link></div>
    </div>
    <div className="toolbar"><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="جستجو در نام، کد یا ناشر..."/><button onClick={()=>load(query)}>جستجو</button><Link href="/">داشبورد</Link></div>
    {message && <p className="message">{message}</p>}
    <div className="frameworkGrid">
      {rows.map(row => <article className="frameworkCard" key={row.id}>
        <div className="frameworkCardHead"><span className={`pill ${row.is_global ? "globalPill" : ""}`}>{row.is_global ? "مرجع سراسری" : "اختصاصی سازمان"}</span><span>{row.status}</span></div>
        <h2>{row.name}</h2><code>{row.code}</code>
        <p>{row.publisher || "بدون ناشر"}</p>
        <div className="frameworkMeta"><span>{row.versions_count} نسخه</span><span>{row.framework_type}</span><span>{row.license_type}</span></div>
        <Link className="primary linkButton" href={`/frameworks/${row.id}`}>باز کردن</Link>
      </article>)}
    </div>
  </main>;
}
