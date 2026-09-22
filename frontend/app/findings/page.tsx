"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";

type Finding={id:string;title:string;severity:string;status:string;organization_name?:string|null;owner_display:string;requirement_code?:string|null;due_date?:string|null;actions_count:number};
const severityLabels:Record<string,string>={low:"کم",medium:"متوسط",high:"زیاد",critical:"بحرانی"};
const statusLabels:Record<string,string>={open:"باز",in_remediation:"در اصلاح",verification:"راستی‌آزمایی",closed:"بسته",accepted:"پذیرفته‌شده"};

export default function FindingsPage(){
  const[rows,setRows]=useState<Finding[]>([]);const[search,setSearch]=useState("");const[status,setStatus]=useState("");const[severity,setSeverity]=useState("");const[loading,setLoading]=useState(true);const[error,setError]=useState("");const[page,setPage]=useState(1);const[count,setCount]=useState(0);
  const load=useCallback(async()=>{setLoading(true);setError("");const q=new URLSearchParams({page:String(page)});if(search.trim())q.set("search",search.trim());if(status)q.set("status",status);if(severity)q.set("severity",severity);const r=await apiFetch("/findings/?"+q.toString());if(!r.ok){setRows([]);setError("دریافت یافته‌ها ناموفق بود.");setLoading(false);return;}const b=await r.json();if(Array.isArray(b)){setRows(b);setCount(b.length)}else{setRows(b.results??[]);setCount(b.count??(b.results?.length??0))}setLoading(false)},[search,status,severity,page]);
  useEffect(()=>{void load()},[load]);const pageCount=Math.max(1,Math.ceil(count/50));
  return <main className="adminPage" dir="rtl"><div className="pageHead"><div><Link href="/">بازگشت به داشبورد</Link><h1>دفتر یافته‌ها</h1><p>عدم انطباق، مشاهده، ضعف و پیگیری CAPA</p></div></div>
    {error&&<div className="message">{error}</div>}
    <div className="toolbar"><input value={search} onChange={e=>{setSearch(e.target.value);setPage(1)}} placeholder="جستجو در عنوان، شرح یا علت ریشه‌ای"/><select value={severity} onChange={e=>{setSeverity(e.target.value);setPage(1)}}><option value="">همه شدت‌ها</option>{Object.entries(severityLabels).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select><select value={status} onChange={e=>{setStatus(e.target.value);setPage(1)}}><option value="">همه وضعیت‌ها</option>{Object.entries(statusLabels).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></div>
    <section className="panel">{loading?<p className="muted">در حال دریافت یافته‌ها…</p>:rows.length===0?<div className="emptyState">یافته‌ای مطابق فیلترها یافت نشد.</div>:<div className="tableWrap"><table className="dataTable"><thead><tr><th>یافته</th><th>شدت</th><th>الزام</th><th>دامنه</th><th>مالک</th><th>اقدامات</th><th>سررسید</th><th>وضعیت</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td><Link href={"/findings/"+r.id}>{r.title}</Link></td><td><span className={"riskLevel "+r.severity}>{severityLabels[r.severity]??r.severity}</span></td><td dir="ltr">{r.requirement_code||"—"}</td><td>{r.organization_name||"کل سازمان"}</td><td>{r.owner_display}</td><td>{r.actions_count}</td><td dir="ltr">{r.due_date||"—"}</td><td><span className="pill">{statusLabels[r.status]??r.status}</span></td></tr>)}</tbody></table></div>}{count>50&&<div className="headActions"><button type="button" className="secondaryButton" disabled={page<=1||loading} onClick={()=>setPage(p=>Math.max(1,p-1))}>صفحه قبل</button><span>صفحه {page} از {pageCount} · {count} رکورد</span><button type="button" className="secondaryButton" disabled={page>=pageCount||loading} onClick={()=>setPage(p=>Math.min(pageCount,p+1))}>صفحه بعد</button></div>}</section>
  </main>;
}
