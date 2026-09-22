"use client";
import Link from "next/link";
import {useEffect,useState} from "react";
import {apiFetch} from "../../lib/api";

type Source={id:string;title:string;source_type:string};
export default function AIPage(){
  const[q,setQ]=useState("");const[answer,setAnswer]=useState("");const[sources,setSources]=useState<Source[]>([]);const[busy,setBusy]=useState(false);const[msg,setMsg]=useState("");
  async function ask(){setBusy(true);setMsg("");setAnswer("");const r=await apiFetch('/ai/assist/rag/',{method:'POST',body:JSON.stringify({query:q,classification:'internal'})});const b=await r.json().catch(()=>({}));if(r.ok){setAnswer(b.answer??'');setSources(b.sources??[])}else setMsg(b.message??b.detail??JSON.stringify(b));setBusy(false)}
  async function draft(){setBusy(true);const r=await apiFetch('/ai/assist/document-draft/',{method:'POST',body:JSON.stringify({title:'پیش‌نویس سیاست',purpose:q||'یک پیش‌نویس عمومی GRC با محل‌های مشخص برای اطلاعات تاییدنشده بساز'})});const b=await r.json().catch(()=>({}));if(r.ok){setAnswer(b.suggestion?.proposed_value?.content??'پیشنهاد در Inbox ایجاد شد');setMsg('پیشنهاد AI ثبت شد و نیاز به تایید انسانی دارد.')}else setMsg(b.message??JSON.stringify(b));setBusy(false)}
  return <main className="adminPage"><div className="pageHead"><div><Link href="/">← داشبورد</Link><h1>دستیار هوشمند GRC</h1><p>پاسخ مبتنی بر داده مجاز، پیشنهادهای قابل بررسی و بدون تغییر خودکار داده نهایی</p></div><div className="headActions"><Link className="secondaryLink" href="/ai/suggestions">پیشنهادهای AI</Link><Link className="secondaryLink" href="/settings/ai">تنظیم Provider</Link></div></div>
  <section className="panel aiWorkspace"><label>پرسش یا زمینه کاری<textarea value={q} onChange={e=>setQ(e.target.value)} placeholder="مثلاً سه ریسک اصلی مرتبط با دسترسی را بر اساس داده موجود خلاصه کن" /></label><div className="headActions"><button className="primary" disabled={busy||!q.trim()} onClick={ask}>{busy?'در حال پردازش…':'پرسش از RAG'}</button><button className="secondaryLink" disabled={busy} onClick={draft}>ایجاد پیش‌نویس سند</button></div>{msg&&<p className="message">{msg}</p>}{answer&&<article className="aiAnswer"><h2>پاسخ / پیشنهاد</h2><pre>{answer}</pre>{sources.length>0&&<><h3>منابع مجاز</h3><ul>{sources.map(s=><li key={s.id}>{s.title} <small>({s.source_type})</small></li>)}</ul></>}</article>}</section>
  <section className="panel"><h2>Guardrail</h2><p className="muted">خروجی AI فقط پیشنهاد است. وضعیت انطباق، پذیرش ریسک، بستن Finding، اثربخشی کنترل و تأیید سند بدون اقدام انسانی تغییر نمی‌کند.</p></section></main>
}
