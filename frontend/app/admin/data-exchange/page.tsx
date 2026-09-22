"use client";

import Link from "next/link";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../../lib/api";

type Dataset = { label:string; headers:string[]; formats:string[] };
type PlanRow = { row:number; key:string; action:string; errors:Record<string,unknown> };
type Plan = {
  dataset:string; format:string; row_count:number; create_count:number; update_count:number;
  error_count:number; results:PlanRow[]; validation_token:string|null; preview:Record<string,string>[];
};

export default function DataExchangePage(){
  const[datasets,setDatasets]=useState<Record<string,Dataset>>({});
  const[dataset,setDataset]=useState("organization");
  const[file,setFile]=useState<File|null>(null);
  const[plan,setPlan]=useState<Plan|null>(null);
  const[confirmed,setConfirmed]=useState(false);
  const[busy,setBusy]=useState(false);
  const[error,setError]=useState("");

  useEffect(()=>{
    apiFetch("/data-exchange/catalog/").then(async r=>{
      const body=await r.json().catch(()=>({}));
      if(r.ok)setDatasets(body.datasets||{});
      else setError("فهرست قابلیت‌های ورود/خروج داده قابل دریافت نیست.");
    });
  },[]);

  const selected=datasets[dataset];
  const canCommit=Boolean(file&&plan?.validation_token&&plan.error_count===0&&confirmed&&!busy);

  function onFile(e:ChangeEvent<HTMLInputElement>){
    setFile(e.target.files?.[0]||null);setPlan(null);setConfirmed(false);setError("");
  }

  async function download(kind:"template"|"export",fmt:"csv"|"xlsx"){
    setError("");
    const r=await apiFetch(`/data-exchange/${kind}/?dataset=${encodeURIComponent(dataset)}&format=${fmt}`);
    if(!r.ok){setError(kind==="export"?"خروجی‌گیری مجاز نیست یا ناموفق بود.":"دریافت قالب ناموفق بود.");return;}
    const blob=await r.blob();const url=URL.createObjectURL(blob);const a=document.createElement("a");
    a.href=url;a.download=`${dataset}-${kind}.${fmt}`;a.click();URL.revokeObjectURL(url);
  }

  async function validate(){
    if(!file)return;
    setBusy(true);setError("");setConfirmed(false);
    const form=new FormData();form.set("dataset",dataset);form.set("file",file);
    const r=await apiFetch("/data-exchange/validate/",{method:"POST",body:form});
    const body=await r.json().catch(()=>({}));
    if(!r.ok){setPlan(null);setError("اعتبارسنجی فایل ناموفق بود. ستون‌ها، مقادیر و مجوزها را بررسی کنید.");}
    else setPlan(body as Plan);
    setBusy(false);
  }

  async function commit(){
    if(!file||!plan?.validation_token||!confirmed)return;
    setBusy(true);setError("");
    const form=new FormData();form.set("dataset",dataset);form.set("validation_token",plan.validation_token);form.set("file",file);
    const r=await apiFetch("/data-exchange/commit/",{method:"POST",body:form});
    const body=await r.json().catch(()=>({}));
    if(!r.ok){setError("اعمال فایل متوقف شد؛ dry-run را دوباره اجرا کنید.");setPlan(null);}
    else {setPlan(body as Plan);setConfirmed(false);}
    setBusy(false);
  }

  const errors=useMemo(()=>plan?.results.filter(x=>Object.keys(x.errors||{}).length>0)??[],[plan]);

  return <main className="adminPage" dir="rtl">
    <div className="pageHead">
      <div><Link href="/admin/onboarding">بازگشت به راه‌اندازی Tenant</Link><h1>ورود و خروج داده مشتری</h1><p>انتقال کنترل‌شده داده‌های اولیه با dry-run، validation و ثبت Audit</p></div>
    </div>

    <section className="panel">
      <label>مجموعه داده
        <select value={dataset} onChange={e=>{setDataset(e.target.value);setFile(null);setPlan(null);setConfirmed(false)}}>
          {Object.entries(datasets).map(([key,value])=><option key={key} value={key}>{value.label}</option>)}
        </select>
      </label>
      <div className="headActions" style={{marginTop:12}}>
        <button type="button" className="secondaryButton" onClick={()=>download("template","xlsx")}>قالب XLSX</button>
        <button type="button" className="secondaryButton" onClick={()=>download("template","csv")}>قالب CSV</button>
        <button type="button" className="secondaryButton" onClick={()=>download("export","xlsx")}>خروجی XLSX</button>
        <button type="button" className="secondaryButton" onClick={()=>download("export","csv")}>خروجی CSV</button>
      </div>
      {dataset==="users"&&<p className="muted">فایل کاربران عمداً password و Role ندارد. کاربر جدید با رمز غیرقابل‌استفاده ایجاد می‌شود و تخصیص Role/Scope باید جداگانه و Audit‌شده انجام شود.</p>}
      {selected&&<p className="muted">ستون‌ها: <span dir="ltr">{selected.headers.join(", ")}</span></p>}
    </section>

    <section className="panel">
      <h2>۱. Dry-run</h2>
      <input type="file" accept=".csv,.xlsx" onChange={onFile}/>
      <div style={{marginTop:12}}><button type="button" onClick={validate} disabled={!file||busy}>{busy?"در حال پردازش…":"اعتبارسنجی فایل"}</button></div>
      {error&&<div className="message">{error}</div>}
      {plan&&<>
        <div className="kpis" style={{marginTop:16}}>
          <article className="kpi"><span>ردیف</span><strong>{plan.row_count}</strong></article>
          <article className="kpi good"><span>ایجاد</span><strong>{plan.create_count}</strong></article>
          <article className="kpi"><span>به‌روزرسانی</span><strong>{plan.update_count}</strong></article>
          <article className={`kpi ${plan.error_count?"warn":"good"}`}><span>خطا</span><strong>{plan.error_count}</strong></article>
        </div>
        {errors.length>0&&<div className="tableWrap"><table><thead><tr><th>ردیف</th><th>کلید</th><th>خطا</th></tr></thead><tbody>
          {errors.map(x=><tr key={x.row}><td>{x.row}</td><td dir="ltr">{x.key}</td><td><pre>{JSON.stringify(x.errors,null,2)}</pre></td></tr>)}
        </tbody></table></div>}
      </>}
    </section>

    <section className="panel">
      <h2>۲. اعمال نهایی</h2>
      <p className="muted">Commit فقط برای همان فایل دقیقاً اعتبارسنجی‌شده قابل انجام است. تغییر فایل، Tenant یا کاربر، token را نامعتبر می‌کند.</p>
      <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} disabled={!plan?.validation_token}/> تأیید می‌کنم همین فایل اعتبارسنجی‌شده اعمال شود.</label>
      <div style={{marginTop:12}}><button type="button" onClick={commit} disabled={!canCommit}>{busy?"در حال اعمال…":"اعمال فایل"}</button></div>
      {plan&&!plan.validation_token&&plan.error_count===0&&<p className="muted">پس از commit موفق، برای اعمال فایل جدید دوباره dry-run انجام دهید.</p>}
    </section>
  </main>;
}
