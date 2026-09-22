"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "../../../lib/api";

type ActionItem={id:string;organization_unit:string|null;organization_name?:string|null;title:string;description:string;owner:number;owner_display:string;reviewer:number|null;reviewer_display?:string|null;priority:string;start_date:string|null;due_date:string|null;progress:number;status:string;completed_at:string|null;source_type:string;source_id:string|null};
type Unit={id:string;code:string;name:string};type User={id:number;username:string;display:string};type Options={organization_units:Unit[];users:User[]};
const priorityLabels:Record<string,string>={low:"کم",medium:"متوسط",high:"زیاد",critical:"بحرانی"};
const statusLabels:Record<string,string>={todo:"برای انجام",in_progress:"در حال انجام",review:"بازبینی",done:"انجام‌شده",cancelled:"لغوشده"};

export default function ActionDetail(){
  const{id}=useParams<{id:string}>();
  const[item,setItem]=useState<ActionItem|null>(null);const[options,setOptions]=useState<Options|null>(null);
  const[loading,setLoading]=useState(true);const[saving,setSaving]=useState(false);const[error,setError]=useState("");const[message,setMessage]=useState("");
  useEffect(()=>{void (async()=>{const[a,o]=await Promise.all([apiFetch("/actions/"+id+"/"),apiFetch("/actions/selector-options/")]);if(!a.ok){setError("اقدام یافت نشد یا مجوز مشاهده آن را ندارید.");setLoading(false);return;}setItem(await a.json());if(o.ok)setOptions(await o.json());setLoading(false)})()},[id]);
  function patch<K extends keyof ActionItem>(key:K,value:ActionItem[K]){setItem(v=>v?{...v,[key]:value}:v)}
  async function save(e:FormEvent){e.preventDefault();if(!item)return;setSaving(true);setError("");setMessage("");
    const payload={organization_unit:item.organization_unit,title:item.title,description:item.description,owner:item.owner,reviewer:item.reviewer,priority:item.priority,start_date:item.start_date||null,due_date:item.due_date||null,progress:item.progress,status:item.status};
    const r=await apiFetch("/actions/"+id+"/",{method:"PATCH",body:JSON.stringify(payload)});
    if(!r.ok){setError("ذخیره اقدام ناموفق بود. مجوز، پیشرفت و وضعیت را بررسی کنید.");setSaving(false);return;}setItem(await r.json());setMessage("تغییرات اقدام ذخیره شد.");setSaving(false)}
  if(loading)return <main className="adminPage" dir="rtl"><p>در حال دریافت اقدام…</p></main>;
  if(!item)return <main className="adminPage" dir="rtl"><Link href="/actions">بازگشت</Link><div className="message">{error}</div></main>;
  return <main className="adminPage" dir="rtl">
    <div className="pageHead"><div><Link href="/actions">بازگشت به دفتر اقدامات</Link><h1>{item.title}</h1><p>مالک: {item.owner_display}</p></div></div>
    {error&&<div className="message">{error}</div>}{message&&<div className="message">{message}</div>}
    <section className="panel"><form onSubmit={save}>
      <div className="formGrid">
        <label>عنوان<input value={item.title} onChange={e=>patch("title",e.target.value)}/></label>
        <label>واحد<select value={item.organization_unit??""} onChange={e=>patch("organization_unit",e.target.value||null)} disabled={!options}><option value="">کل سازمان</option>{options?.organization_units.map(u=><option key={u.id} value={u.id}>{u.code} — {u.name}</option>)}</select></label>
        <label>مالک<select value={item.owner} onChange={e=>patch("owner",Number(e.target.value))} disabled={!options}>{options?.users.map(u=><option key={u.id} value={u.id}>{u.display} ({u.username})</option>)??<option value={item.owner}>{item.owner_display}</option>}</select></label>
        <label>بازبین<select value={item.reviewer??""} onChange={e=>patch("reviewer",e.target.value?Number(e.target.value):null)} disabled={!options}><option value="">بدون بازبین</option>{options?.users.map(u=><option key={u.id} value={u.id}>{u.display} ({u.username})</option>)}</select></label>
        <label>اولویت<select value={item.priority} onChange={e=>patch("priority",e.target.value)}>{Object.entries(priorityLabels).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
        <label>وضعیت<select value={item.status} onChange={e=>patch("status",e.target.value)}>{Object.entries(statusLabels).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
        <label>شروع<input type="date" value={item.start_date??""} onChange={e=>patch("start_date",e.target.value||null)}/></label>
        <label>سررسید<input type="date" value={item.due_date??""} onChange={e=>patch("due_date",e.target.value||null)}/></label>
        <label>پیشرفت<input type="number" min="0" max="100" value={item.progress} onChange={e=>patch("progress",Number(e.target.value))}/></label>
      </div>
      <label>توضیحات<textarea value={item.description} onChange={e=>patch("description",e.target.value)}/></label>
      <button type="submit" disabled={saving||!options}>{saving?"در حال ذخیره…":"ذخیره تغییرات"}</button>
    </form></section>
    <section className="panel"><h2>ردیابی منبع</h2>{item.source_type&&item.source_id?<p><span dir="ltr">{item.source_type}</span> · <code dir="ltr">{item.source_id}</code></p>:<p className="muted">این اقدام منبع سیستمی ثبت‌شده ندارد.</p>}{item.completed_at&&<p>تکمیل: <span dir="ltr">{item.completed_at}</span></p>}</section>
  </main>;
}
