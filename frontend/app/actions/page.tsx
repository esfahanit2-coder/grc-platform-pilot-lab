"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

type ActionRow={id:string;title:string;owner_display:string;priority:string;due_date?:string|null;progress:number;status:string;source_type:string;organization_name?:string|null};
const priorityLabels:Record<string,string>={low:"کم",medium:"متوسط",high:"زیاد",critical:"بحرانی"};
const statusLabels:Record<string,string>={todo:"برای انجام",in_progress:"در حال انجام",review:"بازبینی",done:"انجام‌شده",cancelled:"لغوشده"};

export default function Actions(){
  const[rows,setRows]=useState<ActionRow[]>([]);
  const[search,setSearch]=useState("");
  const[status,setStatus]=useState("");
  const[priority,setPriority]=useState("");
  const[due,setDue]=useState("");
  const[loading,setLoading]=useState(true);
  const[error,setError]=useState("");
  const[page,setPage]=useState(1);const[count,setCount]=useState(0);

  const load=useCallback(async()=>{
    setLoading(true);setError("");
    const q=new URLSearchParams({page:String(page)});
    if(search.trim())q.set("search",search.trim());if(status)q.set("status",status);if(priority)q.set("priority",priority);if(due)q.set("due",due);
    const r=await apiFetch("/actions/?"+q.toString());
    if(!r.ok){setRows([]);setError("دریافت اقدامات ناموفق بود.");setLoading(false);return;}
    const b=await r.json();if(Array.isArray(b)){setRows(b);setCount(b.length)}else{setRows(b.results??[]);setCount(b.count??(b.results?.length??0))}setLoading(false);
  },[search,status,priority,due,page]);
  useEffect(()=>{void load()},[load]);
  const pageCount=Math.max(1,Math.ceil(count/50));

  return <main className="adminPage" dir="rtl">
    <div className="pageHead"><div><Link href="/">بازگشت به داشبورد</Link><h1>دفتر اقدامات</h1><p>پیگیری اقدام‌های اصلاحی، درمان ریسک و سایر منابع GRC</p></div></div>
    {error&&<div className="message">{error}</div>}
    <div className="toolbar">
      <input value={search} onChange={e=>{setSearch(e.target.value);setPage(1)}} placeholder="جستجو در عنوان یا توضیحات"/>
      <select value={status} onChange={e=>{setStatus(e.target.value);setPage(1)}}><option value="">همه وضعیت‌ها</option>{Object.entries(statusLabels).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select>
      <select value={priority} onChange={e=>{setPriority(e.target.value);setPage(1)}}><option value="">همه اولویت‌ها</option>{Object.entries(priorityLabels).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select>
      <select value={due} onChange={e=>{setDue(e.target.value);setPage(1)}}><option value="">همه سررسیدها</option><option value="overdue">معوق</option><option value="due_soon">۷ روز آینده</option><option value="undated">بدون سررسید</option></select>
    </div>
    <section className="panel">
      {loading?<p className="muted">در حال دریافت اقدامات…</p>:rows.length===0?<div className="emptyState">اقدامی مطابق فیلترها یافت نشد.</div>:<div className="tableWrap"><table className="dataTable"><thead><tr><th>اقدام</th><th>منبع</th><th>مالک</th><th>اولویت</th><th>سررسید</th><th>پیشرفت</th><th>وضعیت</th></tr></thead><tbody>{rows.map(a=><tr key={a.id}><td><Link href={"/actions/"+a.id}>{a.title}</Link></td><td dir="ltr">{a.source_type||"—"}</td><td>{a.owner_display}</td><td>{priorityLabels[a.priority]??a.priority}</td><td dir="ltr">{a.due_date||"—"}</td><td>{a.progress}%</td><td>{statusLabels[a.status]??a.status}</td></tr>)}</tbody></table></div>}
      {count>50&&<div className="headActions"><button type="button" className="secondaryButton" disabled={page<=1||loading} onClick={()=>setPage(p=>Math.max(1,p-1))}>صفحه قبل</button><span>صفحه {page} از {pageCount} · {count} رکورد</span><button type="button" className="secondaryButton" disabled={page>=pageCount||loading} onClick={()=>setPage(p=>Math.min(pageCount,p+1))}>صفحه بعد</button></div>}
    </section>
  </main>;
}
