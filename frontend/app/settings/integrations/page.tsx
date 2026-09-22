"use client";
import {useEffect,useState} from "react";
import {apiFetch} from "../../../lib/api";

type Connector={id:string;name:string;connector_type:string;base_url:string;last_status:string;last_sync_at:string|null;is_active:boolean};
type ConnectorList={results?:Connector[]};
function errorMessage(error:unknown){return error instanceof Error?error.message:"خطای ناشناخته"}

export default function IntegrationsPage(){
  const [rows,setRows]=useState<Connector[]>([]);const [error,setError]=useState("");
  async function load(){
    try{
      const response=await apiFetch("/connectors/");
      if(!response.ok)throw new Error(`دریافت اتصال‌ها ناموفق بود (${response.status})`);
      const data=(await response.json()) as ConnectorList|Connector[];
      setRows(Array.isArray(data)?data:data.results??[]);
    }catch(err:unknown){setError(errorMessage(err))}
  }
  useEffect(()=>{load()},[]);
  async function run(id:string){
    setError("");
    try{
      const response=await apiFetch(`/connectors/${id}/sync/`,{method:"POST",body:JSON.stringify({})});
      if(!response.ok)throw new Error(`همگام‌سازی ناموفق بود (${response.status})`);
      await load();
    }catch(err:unknown){setError(errorMessage(err))}
  }
  return <main className="page"><div className="pageHeader"><div><h1>یکپارچه‌سازی‌ها</h1><p>اتصال خواندنی و تولید شواهد خودکار از سامانه‌های سازمانی</p></div></div>{error&&<div className="errorBox">{error}</div>}<div className="panel"><table><thead><tr><th>نام</th><th>نوع</th><th>آدرس</th><th>آخرین وضعیت</th><th>آخرین همگام‌سازی</th><th></th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{r.name}</td><td>{r.connector_type}</td><td>{r.base_url||"—"}</td><td>{r.last_status||"—"}</td><td>{r.last_sync_at||"—"}</td><td><button onClick={()=>run(r.id)} disabled={!r.is_active}>جمع‌آوری شواهد</button></td></tr>)}</tbody></table></div></main>}
