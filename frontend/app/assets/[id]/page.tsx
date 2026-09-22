"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "../../../lib/api";

type Asset={id:string;code:string;title:string;asset_type:string;organization_unit:string;organization_name:string;description:string;owner:number;owner_display:string;custodian:number|null;custodian_display?:string|null;confidentiality:number;integrity:number;availability:number;cia_score:number;criticality:string;status:string};
type OptionUnit={id:string;code:string;name:string};
type OptionUser={id:number;username:string;display:string};
type Options={organization_units:OptionUnit[];users:OptionUser[]};
type Dependency={id:string;parent_asset:string;parent_code:string;parent_title:string;child_asset:string;child_code:string;child_title:string;dependency_type:string;critical:boolean};

const typeLabels:Record<string,string>={information:"اطلاعات",hardware:"سخت‌افزار",software:"نرم‌افزار",application:"کاربرد",database:"پایگاه داده",cloud_service:"سرویس ابری",service:"سرویس",process:"فرآیند",person:"فرد",site:"سایت",other:"سایر"};
const statusLabels:Record<string,string>={active:"فعال",retired:"بازنشسته",archived:"آرشیو"};

export default function AssetDetail(){
  const{id}=useParams<{id:string}>();
  const[asset,setAsset]=useState<Asset|null>(null);
  const[options,setOptions]=useState<Options|null>(null);
  const[dependencies,setDependencies]=useState<Dependency[]>([]);
  const[loading,setLoading]=useState(true);
  const[saving,setSaving]=useState(false);
  const[error,setError]=useState("");
  const[message,setMessage]=useState("");

  useEffect(()=>{void (async()=>{
    setLoading(true);setError("");
    const[a,o,d]=await Promise.all([apiFetch("/assets/"+id+"/"),apiFetch("/assets/selector-options/"),apiFetch("/asset-dependencies/?page_size=200&asset="+encodeURIComponent(id))]);
    if(!a.ok){setError("دارایی یافت نشد یا مجوز مشاهده آن را ندارید.");setLoading(false);return;}
    setAsset(await a.json());
    if(o.ok)setOptions(await o.json());
    if(d.ok){const body=await d.json();setDependencies(body.results??body)}
    setLoading(false);
  })()},[id]);

  function patch<K extends keyof Asset>(key:K,value:Asset[K]){setAsset(current=>current?{...current,[key]:value}:current)}

  async function save(event:FormEvent){
    event.preventDefault();if(!asset)return;setSaving(true);setError("");setMessage("");
    const payload={
      organization_unit:asset.organization_unit,asset_type:asset.asset_type,code:asset.code,title:asset.title,
      description:asset.description,owner:asset.owner,custodian:asset.custodian,confidentiality:asset.confidentiality,
      integrity:asset.integrity,availability:asset.availability,criticality:asset.criticality,status:asset.status,
    };
    const r=await apiFetch("/assets/"+id+"/",{method:"PATCH",body:JSON.stringify(payload)});
    if(!r.ok){setError("ذخیره تغییرات ناموفق بود. مجوز و مقادیر را بررسی کنید.");setSaving(false);return;}
    setAsset(await r.json());setMessage("تغییرات دارایی ذخیره شد.");setSaving(false);
  }

  if(loading)return <main className="adminPage" dir="rtl"><p>در حال دریافت دارایی…</p></main>;
  if(!asset)return <main className="adminPage" dir="rtl"><Link href="/assets">بازگشت</Link><div className="message">{error}</div></main>;

  return <main className="adminPage" dir="rtl">
    <div className="pageHead"><div><Link href="/assets">بازگشت به دفتر دارایی‌ها</Link><h1>{asset.title}</h1><p><span dir="ltr">{asset.code}</span> · CIA {asset.cia_score}</p></div></div>
    {error&&<div className="message">{error}</div>}{message&&<div className="message">{message}</div>}
    <section className="panel">
      <h2>مشخصات و مالکیت</h2>
      <form onSubmit={save}>
        <div className="formGrid">
          <label>کد<input dir="ltr" value={asset.code} onChange={e=>patch("code",e.target.value)}/></label>
          <label>عنوان<input value={asset.title} onChange={e=>patch("title",e.target.value)}/></label>
          <label>نوع<select value={asset.asset_type} onChange={e=>patch("asset_type",e.target.value)}>{Object.entries(typeLabels).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
          <label>واحد سازمانی<select value={asset.organization_unit} onChange={e=>patch("organization_unit",e.target.value)} disabled={!options}>{options?.organization_units.map(u=><option key={u.id} value={u.id}>{u.code} — {u.name}</option>)??<option value={asset.organization_unit}>{asset.organization_name}</option>}</select></label>
          <label>مالک<select value={asset.owner} onChange={e=>patch("owner",Number(e.target.value))} disabled={!options}>{options?.users.map(u=><option key={u.id} value={u.id}>{u.display} ({u.username})</option>)??<option value={asset.owner}>{asset.owner_display}</option>}</select></label>
          <label>متولی<select value={asset.custodian??""} onChange={e=>patch("custodian",e.target.value?Number(e.target.value):null)} disabled={!options}><option value="">بدون متولی</option>{options?.users.map(u=><option key={u.id} value={u.id}>{u.display} ({u.username})</option>)}</select></label>
          <label>C<select value={asset.confidentiality} onChange={e=>patch("confidentiality",Number(e.target.value))}>{[1,2,3,4,5].map(v=><option key={v} value={v}>{v}</option>)}</select></label>
          <label>I<select value={asset.integrity} onChange={e=>patch("integrity",Number(e.target.value))}>{[1,2,3,4,5].map(v=><option key={v} value={v}>{v}</option>)}</select></label>
          <label>A<select value={asset.availability} onChange={e=>patch("availability",Number(e.target.value))}>{[1,2,3,4,5].map(v=><option key={v} value={v}>{v}</option>)}</select></label>
          <label>بحرانی‌بودن<input dir="ltr" type="number" step="0.01" value={asset.criticality} onChange={e=>patch("criticality",e.target.value)}/></label>
          <label>وضعیت<select value={asset.status} onChange={e=>patch("status",e.target.value)}>{Object.entries(statusLabels).filter(([v])=>v!=="archived").map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
        </div>
        <label>توضیحات<textarea value={asset.description} onChange={e=>patch("description",e.target.value)}/></label>
        <button type="submit" disabled={saving||!options}>{saving?"در حال ذخیره…":"ذخیره تغییرات"}</button>
      </form>
    </section>
    <section className="panel">
      <h2>وابستگی‌ها</h2>
      {dependencies.length===0?<div className="emptyState">وابستگی ثبت‌شده‌ای برای این دارایی وجود ندارد.</div>:<div className="tableWrap"><table className="dataTable"><thead><tr><th>جهت</th><th>دارایی مرتبط</th><th>نوع وابستگی</th><th>بحرانی</th></tr></thead><tbody>{dependencies.map(d=>{const outgoing=d.parent_asset===id;return <tr key={d.id}><td>{outgoing?"خروجی":"ورودی"}</td><td><Link href={"/assets/"+(outgoing?d.child_asset:d.parent_asset)}><span dir="ltr">{outgoing?d.child_code:d.parent_code}</span> — {outgoing?d.child_title:d.parent_title}</Link></td><td>{d.dependency_type}</td><td>{d.critical?"بله":"خیر"}</td></tr>})}</tbody></table></div>}
    </section>
  </main>;
}
