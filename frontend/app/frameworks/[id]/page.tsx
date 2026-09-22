"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../../lib/api";

type Framework = { id:string; code:string; name:string; publisher:string; status:string; is_global:boolean; license_type:string; description:string };
type Version = { id:string; version_code:string; title:string; status:string; is_locked:boolean; checksum:string; requirement_count:number };
type Requirement = { id:string; code:string; title:string; body:string; guidance:string; assessable:boolean; mandatory:boolean; parent_code?:string|null; children?:Requirement[] };

function ReqNode({row, selected, onSelect}:{row:Requirement; selected:string|null; onSelect:(r:Requirement)=>void}) {
  return <div><button className={`reqNode ${selected===row.id?"selected":""}`} onClick={()=>onSelect(row)}><b>{row.code}</b><span>{row.title}</span></button>{row.children?.length ? <div className="reqChildren">{row.children.map(child=><ReqNode key={child.id} row={child} selected={selected} onSelect={onSelect}/>)}</div>:null}</div>
}

export default function FrameworkDetailPage(){
 const params=useParams<{id:string}>(); const id=params.id;
 const [framework,setFramework]=useState<Framework|null>(null); const [versions,setVersions]=useState<Version[]>([]); const [versionId,setVersionId]=useState("");
 const [tree,setTree]=useState<Requirement[]>([]); const [selected,setSelected]=useState<Requirement|null>(null); const [message,setMessage]=useState(""); const [newCode,setNewCode]=useState(""); const [newTitle,setNewTitle]=useState("");
 async function loadFramework(){const r=await apiFetch(`/frameworks/${id}/`); if(r.ok)setFramework(await r.json());}
 async function loadVersions(){const r=await apiFetch(`/framework-versions/?framework=${id}`); if(!r.ok)return; const b=await r.json(); const list=b.results??b; setVersions(list); if(list.length && !versionId)setVersionId(list[0].id);}
 async function loadTree(v:string){if(!v)return; const r=await apiFetch(`/requirements/tree/?framework_version=${v}`); if(r.ok){const b=await r.json(); setTree(b); setSelected(b?.[0]??null);}}
 useEffect(()=>{loadFramework();loadVersions();},[id]); useEffect(()=>{loadTree(versionId)},[versionId]);
 const current=useMemo(()=>versions.find(v=>v.id===versionId),[versions,versionId]);
 async function lockVersion(){if(!versionId)return; if(!confirm("پس از قفل شدن، Requirementهای این نسخه قابل ویرایش نیستند. ادامه؟"))return; const r=await apiFetch(`/framework-versions/${versionId}/lock/`,{method:"POST",body:"{}"}); setMessage(r.ok?"نسخه قفل شد.":"قفل نسخه ناموفق بود."); if(r.ok){await loadVersions();await loadTree(versionId)}}
 async function addRequirement(){if(!versionId||!newCode||!newTitle)return;const r=await apiFetch('/requirements/',{method:'POST',body:JSON.stringify({framework_version:versionId,parent:selected?.id??null,code:newCode,title:newTitle,body:'',guidance:'',assessable:true,mandatory:true,weight:'1',sort_order:0,metadata:{},translations:[]})});if(r.ok){setNewCode('');setNewTitle('');setMessage('Requirement ثبت شد.');await loadTree(versionId);await loadVersions()}else{const b=await r.json().catch(()=>({}));setMessage(`ثبت Requirement ناموفق بود: ${JSON.stringify(b)}`)}}
 async function downloadVersion(format:'json'|'xlsx'){if(!versionId)return;const r=await apiFetch(`/framework-versions/${versionId}/export/?format=${format}`);if(!r.ok){setMessage('Export ناموفق بود.');return}const blob=await r.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`${framework?.code??'framework'}-${current?.version_code??'version'}.${format}`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url)}
 return <main className="adminPage frameworkWorkspace">
  <div className="pageHead"><div><Link href="/frameworks">← کتابخانه</Link><h1>{framework?.name??"Framework"}</h1><p><code>{framework?.code}</code> · {framework?.publisher} · {framework?.license_type}</p></div><div className="headActions"><select value={versionId} onChange={e=>setVersionId(e.target.value)}>{versions.map(v=><option key={v.id} value={v.id}>{v.version_code} {v.is_locked?"🔒":""}</option>)}</select>{current && !current.is_locked && !framework?.is_global && <button className="primary" onClick={lockVersion}>قفل نسخه</button>}</div></div>
  {message&&<p className="message">{message}</p>}
  <div className="threePane">
   <section className="treePane"><div className="paneTitle">Requirements <span>{current?.requirement_count??0}</span></div>{tree.map(r=><ReqNode key={r.id} row={r} selected={selected?.id??null} onSelect={setSelected}/>)}</section>
   <section className="detailPane">{selected?<><div className="detailHead"><div><span className="pill">{selected.assessable?"قابل ارزیابی":"عنوان ساختاری"}</span><h2>{selected.code} — {selected.title}</h2></div>{current?.is_locked&&<span className="locked">🔒 نسخه قفل است</span>}</div><h3>متن الزام</h3><p>{selected.body||"—"}</p><h3>راهنما</h3><p>{selected.guidance||"راهنمایی ثبت نشده است."}</p><div className="frameworkMeta"><span>{selected.mandatory?"Mandatory":"Optional"}</span><span>Parent: {selected.parent_code||"Root"}</span></div></>:<p className="muted">یک Requirement را انتخاب کنید.</p>}</section>
   <aside className="relatedPane"><div className="paneTitle">نسخه</div><dl><dt>Status</dt><dd>{current?.status}</dd><dt>Locked</dt><dd>{current?.is_locked?"Yes":"No"}</dd><dt>Checksum</dt><dd className="hashText">{current?.checksum||"بعد از Lock ساخته می‌شود"}</dd></dl>{current&&<><button className="secondaryLink blockLink" onClick={()=>downloadVersion('json')}>Export JSON</button><button className="secondaryLink blockLink" onClick={()=>downloadVersion('xlsx')}>Export XLSX</button></>}{current&&!current.is_locked&&!framework?.is_global&&<details className="quickRequirement"><summary>+ Requirement</summary><label>Code<input value={newCode} onChange={e=>setNewCode(e.target.value)} placeholder="REQ-1"/></label><label>Title<input value={newTitle} onChange={e=>setNewTitle(e.target.value)} placeholder="Requirement title"/></label><small>{selected?`به عنوان فرزند ${selected.code}`:'در سطح Root ایجاد می‌شود'}</small><button className="primary" disabled={!newCode||!newTitle} onClick={addRequirement}>ثبت</button></details>}</aside>
  </div>
 </main>
}
