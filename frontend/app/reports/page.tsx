"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";

type CatalogItem = {title:string; formats:string[]; filters:string[]};
type Preview = {title:string; subtitle?:string; columns:string[]; rows:any[][]; summary?:Record<string,unknown>};

const labels:Record<string,string>={
  soa:"بیانیه کاربردپذیری (SoA)",
  rtp:"برنامه برخورد با ریسک (RTP)",
  audit:"گزارش ممیزی",
  findings:"دفتر یافته‌ها",
  actions:"دفتر اقدامات",
  executive:"خلاصه مدیریتی",
};

export default function ReportsPage(){
  const[catalog,setCatalog]=useState<Record<string,CatalogItem>>({});
  const[type,setType]=useState("executive");
  const[filters,setFilters]=useState<Record<string,string>>({});
  const[preview,setPreview]=useState<Preview|null>(null);
  const[loading,setLoading]=useState(false);
  const[error,setError]=useState("");
  const item=catalog[type];

  useEffect(()=>{
    apiFetch("/reports/catalog/").then(async r=>{
      if(!r.ok){setError("دریافت فهرست گزارش‌ها ناموفق بود.");return;}
      const body=await r.json();setCatalog(body.reports||{});
    });
  },[]);

  const query=useMemo(()=>{
    const q=new URLSearchParams({type});
    Object.entries(filters).forEach(([k,v])=>{if(v)q.set(k,v)});
    return q.toString();
  },[type,filters]);

  async function loadPreview(){
    setLoading(true);setError("");
    try{
      const r=await apiFetch("/reports/preview/?"+query);
      const body=await r.json().catch(()=>({}));
      if(!r.ok){throw new Error(JSON.stringify(body));}
      setPreview(body);
    }catch(e:any){setPreview(null);setError("پیش‌نمایش گزارش ممکن نشد. فیلترها و دسترسی خود را بررسی کنید.");}
    finally{setLoading(false);}
  }

  async function download(fmt:string){
    setError("");
    const r=await apiFetch("/reports/export/?"+query+"&format="+encodeURIComponent(fmt));
    if(!r.ok){setError("تولید خروجی ممکن نشد یا مجوز report.generate ندارید.");return;}
    const blob=await r.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");
    a.href=url;a.download=type+"-report."+fmt;a.click();
    URL.revokeObjectURL(url);
  }

  const set=(key:string,value:string)=>setFilters(v=>({...v,[key]:value}));

  return <main className="adminPage" dir="rtl">
    <Link href="/">بازگشت به داشبورد</Link>
    <header className="pageHeader">
      <div><h1>مرکز گزارش‌ها</h1><p>پیش‌نمایش و خروجی رسمی داده‌های GRC با کنترل دسترسی سازمانی</p></div>
    </header>

    <section className="adminCard">
      <label>نوع گزارش</label>
      <select value={type} onChange={e=>{setType(e.target.value);setFilters({});setPreview(null)}}>
        {Object.keys(catalog).map(k=><option key={k} value={k}>{labels[k]||catalog[k].title}</option>)}
      </select>

      <div className="formGrid">
        {item?.filters.includes("organization_unit")&&<label>شناسه واحد سازمانی<input value={filters.organization_unit||""} onChange={e=>set("organization_unit",e.target.value)} placeholder="UUID — در صورت نیاز"/></label>}
        {item?.filters.includes("assessment")&&<label>شناسه ارزیابی<input value={filters.assessment||""} onChange={e=>set("assessment",e.target.value)} placeholder="UUID ارزیابی"/></label>}
        {item?.filters.includes("engagement")&&<label>شناسه ممیزی<input value={filters.engagement||""} onChange={e=>set("engagement",e.target.value)} placeholder="UUID ممیزی"/></label>}
        {item?.filters.includes("from_date")&&<label>از تاریخ<input type="date" value={filters.from_date||""} onChange={e=>set("from_date",e.target.value)}/></label>}
        {item?.filters.includes("to_date")&&<label>تا تاریخ<input type="date" value={filters.to_date||""} onChange={e=>set("to_date",e.target.value)}/></label>}
        {item?.filters.includes("status")&&<label>وضعیت<input value={filters.status||""} onChange={e=>set("status",e.target.value)} placeholder="اختیاری"/></label>}
        {item?.filters.includes("severity")&&<label>شدت<input value={filters.severity||""} onChange={e=>set("severity",e.target.value)} placeholder="low / medium / high / critical"/></label>}
        {item?.filters.includes("priority")&&<label>اولویت<input value={filters.priority||""} onChange={e=>set("priority",e.target.value)} placeholder="low / medium / high / critical"/></label>}
      </div>

      <div className="buttonRow">
        <button onClick={loadPreview} disabled={loading}>{loading?"در حال دریافت…":"پیش‌نمایش"}</button>
        {item?.formats.map(fmt=><button key={fmt} className="secondaryButton" onClick={()=>download(fmt)}>خروجی {fmt.toUpperCase()}</button>)}
      </div>
      {error&&<p className="errorText">{error}</p>}
    </section>

    <section className="adminCard">
      {!preview&&!loading&&<div className="emptyState">گزارش و فیلترها را انتخاب کنید و «پیش‌نمایش» را بزنید.</div>}
      {preview&&<>
        <h2>{preview.title}</h2>{preview.subtitle&&<p>{preview.subtitle}</p>}
        <div className="tableWrap"><table><thead><tr>{preview.columns.map(c=><th key={c}>{c}</th>)}</tr></thead>
        <tbody>{preview.rows.length?preview.rows.map((row,i)=><tr key={i}>{row.map((v,j)=><td key={j}>{String(v??"")}</td>)}</tr>):<tr><td colSpan={preview.columns.length}>داده‌ای مطابق فیلترها یافت نشد.</td></tr>}</tbody></table></div>
      </>}
    </section>
  </main>;
}
