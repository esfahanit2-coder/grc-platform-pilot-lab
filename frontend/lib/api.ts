export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1";

export function getAccessToken() {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("grc_access_token");
}

export function getTenantId() {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("grc_tenant_id");
}

function getCookie(name: string) {
  if (typeof document === "undefined") return null;
  const row = document.cookie.split("; ").find(x => x.startsWith(`${name}=`));
  return row ? decodeURIComponent(row.slice(name.length + 1)) : null;
}

function buildHeaders(init: RequestInit) {
  const headers = new Headers(init.headers ?? {});
  const token = getAccessToken(); const tenant = getTenantId();
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (tenant) headers.set("X-Tenant-ID", tenant);
  const method=(init.method??"GET").toUpperCase();
  if (!["GET","HEAD","OPTIONS","TRACE"].includes(method)) { const csrf=getCookie("csrftoken"); if(csrf) headers.set("X-CSRFToken",csrf); }
  return headers;
}

async function refreshAuthentication() {
  const refresh = typeof window !== "undefined" ? sessionStorage.getItem("grc_refresh_token") : null;
  const headers = new Headers({"Content-Type":"application/json"}); const csrf=getCookie("csrftoken"); if(csrf) headers.set("X-CSRFToken",csrf);
  const response=await fetch(`${API_BASE}/auth/token/refresh`,{method:"POST",headers,credentials:"include",body:JSON.stringify(refresh?{refresh}:{})});
  if(!response.ok) return false;
  const body=await response.json().catch(()=>({}));
  if(body.access) sessionStorage.setItem("grc_access_token",body.access);
  if(body.refresh) sessionStorage.setItem("grc_refresh_token",body.refresh);
  return true;
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  let response = await fetch(`${API_BASE}${path}`, { ...init, headers: buildHeaders(init), credentials: "include" });
  if (response.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/")) {
    if (await refreshAuthentication()) response = await fetch(`${API_BASE}${path}`, { ...init, headers: buildHeaders(init), credentials: "include" });
    else { sessionStorage.removeItem("grc_access_token"); sessionStorage.removeItem("grc_refresh_token"); }
  }
  return response;
}

export async function persistSession(tokens: { access?: string; refresh?: string; cookie_auth?: boolean }) {
  if (tokens.cookie_auth) { sessionStorage.removeItem("grc_access_token"); sessionStorage.removeItem("grc_refresh_token"); }
  else { if (tokens.access) sessionStorage.setItem("grc_access_token", tokens.access); if (tokens.refresh) sessionStorage.setItem("grc_refresh_token", tokens.refresh); }
  const headers: Record<string,string> = {}; if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  const response = await fetch(`${API_BASE}/tenants/mine`, { headers, credentials: "include" });
  if (response.ok) { const body = await response.json(); const first = Array.isArray(body) ? body[0] : body.results?.[0]; if (first?.tenant?.id) sessionStorage.setItem("grc_tenant_id", first.tenant.id); }
}
