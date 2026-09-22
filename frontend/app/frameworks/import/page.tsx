"use client";
import Link from "next/link";
import { useState } from "react";
import { apiFetch } from "../../../lib/api";

type Preview={framework?:{code?:string;name?:string};version?:{version_code?:string};requirements?:number;languages?:string[];errors?:unknown[];warnings?:unknown[];imported?:boolean;framework_id?:string};
export default function FrameworkImportPage(){
 const [file,setFile]=useState<File|null>(null); const [preview,setPreview]=useState<Preview|null>(null); const [busy,setBusy]=useState(false); const [message,setMessage]=useState("");
 async function run(dry:boolean){if(!file)return; setBusy(true);setMessage("");const data=new FormData();data.append("file",file);const r=await apiFetch(`/frameworks/import/?dry_run=${dry?"true":"false"}`,{method:"POST",body:data});const body=await r.json();setPreview(body);setMessage(r.ok?(dry?"اعتبارسنجی موفق بود؛ برای ثبت نهایی Commit کنید.":"چارچوب با موفقیت Import شد."):"فایل دارای خطا است.");setBusy(false)}
 return <main className="adminPage narrow"><div className="pageHead"><div><h1>Import Framework</h1><p>Content Packهای JSON یا XLSX ابتدا بدون تغییر دیتابیس Validate می‌شوند.</p></div><Link className="secondaryLink" href="/frameworks">بازگشت</Link></div>
 <article className="panel stack"><label className="uploadBox"><b>Content Pack</b><input type="file" accept=".json,.xlsx" onChange={e=>{setFile(e.target.files?.[0]??null);setPreview(null)}}/><small>پشتیبانی: JSON و Excel (.xlsx)</small></label><div className="headActions"><button disabled={!file||busy} onClick={()=>run(true)}>Preview / Validate</button><button className="primary" disabled={!file||busy||!!preview?.errors?.length} onClick={()=>run(false)}>Commit Import</button></div></article>
 {message&&<p className="message">{message}</p>}{preview&&<article className="panel"><h2>نتیجه</h2><div className="frameworkMeta"><span>Framework: {preview.framework?.code}</span><span>Version: {preview.version?.version_code}</span><span>Requirements: {preview.requirements}</span><span>Languages: {preview.languages?.join(", ")||"—"}</span></div>{preview.errors?.length?<pre className="errorReport">{JSON.stringify(preview.errors,null,2)}</pre>:<p className="successText">✓ ساختار و روابط والد/فرزند معتبر است.</p>}</article>}
 </main>
}
