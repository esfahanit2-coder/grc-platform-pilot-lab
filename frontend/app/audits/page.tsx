"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

type Audit={id:string;title:string;audit_type:string;lead_display:string;status:string;start_date?:string|null;organization_name?:string|null;workpapers_count:number;findings_count:number};
const typeLabels:Record<string,string>={internal:"داخلی",framework:"چارچوب",control:"کنترل",process:"فرآیند",follow_up:"پیگیری"};
const statusLabels:Record<string,string>={draft:"پیش‌نویس",planned:"برنامه‌ریزی‌شده",in_progress:"در حال اجرا",review:"بازبینی",completed:"تکمیل‌شده",cancelled:"لغوشده"};

export default function AuditsPage(){
  const[rows,setRows]=useState<Audit[]>([]);const[search,setSearch]=useState("");const[status,setStatus]=useState("");const[type,setType]=useState("");const[loading,setLoading]=useState(true);const[error,setError]=useState("");const[page,setPage]=useState(1);const[count,setCount]=useState(0);
  const load=useCallback(async()=>{setLoading(true);setError("");const q=new URLSearchParams({page:String(page)});if(search.trim())q.set("search",search.trim());if(status)q.set("status",status);if(type)q.set("audit_type",type);const r=await apiFetch("/audits/?"+q.toString());if(!r.ok){setRows([]);setError("دریافت ممیزی‌ها ناموفق بود.");setLoading(false);return;}const b=await r.json();if(Array.isArray(b)){setRows(b);setCount(b.length)}else{setRows(b.results??[]);setCount(b.count??(b.results?.length??0))}setLoading(false)},[search,status,type,page]);
  useEffect(()=>{void load()},[load]);const pageCount=Math.max(1,Math.ceil(count/50));
  return <main className="adminPage" dir="rtl"><div className="pageHead"><div><Link href="/">بازگشت به داشبورد</Link><h1>ممیزی داخلی</h1><p>ماموریت ممیزی، کاربرگ، نتیجه و یافته‌ها</p></div></div>
    {error&&<div className="message">{error}</div>}
    <div className="toolbar"><input value={search} onChange={e=>{setSearch(e.target.value);setPage(1)}} placeholder="جستجو در عنوان، هدف یا دامنه"/><select value={type} onChange={e=>{setType(e.target.value);setPage(1)}}><option value="">همه انواع</option>{Object.entries(typeLabels).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select><select value={status} onChange={e=>{setStatus(e.target.value);setPage(1)}}><option value="">همه وضعیت‌ها</option>{Object.entries(statusLabels).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></div>
    <section className="panel">{loading?<p className="muted">در حال دریافت ممیزی‌ها…</p>:rows.length===0?<div className="emptyState">ممیزی‌ای مطابق فیلترها یافت نشد.</div>:<div className="tableWrap"><table className="dataTable"><thead><tr><th>ممیزی</th><th>نوع</th><th>دامنه</th><th>سرممیز</th><th>شروع</th><th>کاربرگ</th><th>یافته</th><th>وضعیت</th></tr></thead><tbody>{rows.map(a=><tr key={a.id}><td><Link href={"/audits/"+a.id}>{a.title}</Link></td><td>{typeLabels[a.audit_type]??a.audit_type}</td><td>{a.organization_name||"کل سازمان"}</td><td>{a.lead_display}</td><td dir="ltr">{a.start_date??"—"}</td><td>{a.workpapers_count}</td><td>{a.findings_count}</td><td>{statusLabels[a.status]??a.status}</td></tr>)}</tbody></table></div>}{count>50&&<div className="headActions"><button type="button" className="secondaryButton" disabled={page<=1||loading} onClick={()=>setPage(p=>Math.max(1,p-1))}>صفحه قبل</button><span>صفحه {page} از {pageCount} · {count} رکورد</span><button type="button" className="secondaryButton" disabled={page>=pageCount||loading} onClick={()=>setPage(p=>Math.min(pageCount,p+1))}>صفحه بعد</button></div>}</section>
  </main>;
}
