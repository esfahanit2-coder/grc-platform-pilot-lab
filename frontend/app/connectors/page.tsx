"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";

type Connector = {
  id: string;
  organization_unit: string | null;
  name: string;
  connector_type: "active_directory" | "fortigate" | "veeam" | "tenable" | string;
  base_url: string;
  username_env_var: string;
  secret_env_var: string;
  secondary_secret_env_var: string;
  verify_tls: boolean;
  is_active: boolean;
  configuration: Record<string, unknown>;
  last_sync_at: string | null;
  last_status: string;
  last_error: string;
  updated_at: string;
};

type ConnectorRun = {
  id: string;
  connector: string;
  triggered_by: number | null;
  status: "running" | "succeeded" | "failed" | string;
  started_at: string;
  finished_at: string | null;
  summary: {
    evidence_id?: string;
    title?: string;
    payload_sha256?: string;
    provider_schema_version?: string | null;
    dataset?: string | null;
    fact_summary?: Record<string, unknown>;
  };
  error: string;
};

type HealthResult = {
  state: "idle" | "running" | "ok" | "failed";
  message?: string;
  checkedAt?: string;
};

const providerLabels: Record<string, string> = {
  active_directory: "Active Directory / LDAP",
  fortigate: "FortiGate REST API",
  veeam: "Veeam Enterprise Manager",
  tenable: "Tenable / Nessus",
};

function listBody<T>(body: { results?: T[] } | T[]): T[] {
  return Array.isArray(body) ? body : body.results ?? [];
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("fa-IR");
}

function safeJson(value: unknown) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return "{}";
  }
}

async function responseMessage(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (typeof body.detail === "string") return body.detail;
  if (typeof body.message === "string") return body.message;
  if (typeof body.error === "string") return body.error;
  if (body && typeof body === "object") {
    const first = Object.values(body)[0];
    if (typeof first === "string") return first;
    if (Array.isArray(first) && typeof first[0] === "string") return first[0];
  }
  return `HTTP ${response.status}`;
}

export default function ConnectorsPage() {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [runs, setRuns] = useState<ConnectorRun[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [health, setHealth] = useState<Record<string, HealthResult>>({});

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [connectorResponse, runResponse] = await Promise.all([
        apiFetch("/connectors/?page_size=200"),
        apiFetch("/connector-runs/?page_size=100"),
      ]);
      if (!connectorResponse.ok) throw new Error(await responseMessage(connectorResponse));
      if (!runResponse.ok) throw new Error(await responseMessage(runResponse));
      const connectorBody = await connectorResponse.json();
      const runBody = await runResponse.json();
      const nextConnectors = listBody<Connector>(connectorBody);
      setConnectors(nextConnectors);
      setRuns(listBody<ConnectorRun>(runBody));
      setSelected((current) => current && nextConnectors.some((item) => item.id === current) ? current : "");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "دریافت وضعیت اتصال‌ها ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function runHealth(connector: Connector) {
    setBusy((value) => ({ ...value, [`health:${connector.id}`]: true }));
    setMessage("");
    setHealth((value) => ({ ...value, [connector.id]: { state: "running" } }));
    try {
      const response = await apiFetch(`/connectors/${connector.id}/health/`, { method: "POST", body: "{}" });
      if (!response.ok) throw new Error(await responseMessage(response));
      const body = await response.json().catch(() => ({}));
      setHealth((value) => ({
        ...value,
        [connector.id]: {
          state: body.ok === false ? "failed" : "ok",
          message: body.ok === false ? "Health check پاسخ ناموفق داد." : "Health check با موفقیت انجام شد.",
          checkedAt: new Date().toISOString(),
        },
      }));
    } catch (exc) {
      setHealth((value) => ({
        ...value,
        [connector.id]: {
          state: "failed",
          message: exc instanceof Error ? exc.message : "Health check ناموفق بود.",
          checkedAt: new Date().toISOString(),
        },
      }));
    } finally {
      setBusy((value) => ({ ...value, [`health:${connector.id}`]: false }));
    }
  }

  async function runSync(connector: Connector) {
    if (!window.confirm(`Sync فقط‌خواندنی برای «${connector.name}» اجرا شود؟`)) return;
    setBusy((value) => ({ ...value, [`sync:${connector.id}`]: true }));
    setMessage("");
    setError("");
    try {
      const response = await apiFetch(`/connectors/${connector.id}/sync/`, { method: "POST", body: "{}" });
      if (!response.ok) throw new Error(await responseMessage(response));
      const body = await response.json();
      setMessage(`Sync تکمیل شد؛ Run ${body.run_id ?? "—"} و Evidence ${body.evidence_id ?? "—"} ایجاد شد.`);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Sync ناموفق بود.");
      await load();
    } finally {
      setBusy((value) => ({ ...value, [`sync:${connector.id}`]: false }));
    }
  }

  const visibleRuns = useMemo(
    () => selected ? runs.filter((run) => run.connector === selected) : runs,
    [runs, selected],
  );

  const stats = useMemo(() => ({
    total: connectors.length,
    active: connectors.filter((item) => item.is_active).length,
    healthyLastSync: connectors.filter((item) => item.last_status === "succeeded").length,
    failedLastSync: connectors.filter((item) => item.last_status === "failed").length,
  }), [connectors]);

  return (
    <main className="adminPage connectorPage">
      <div className="pageHead">
        <div>
          <Link href="/">← داشبورد</Link>
          <h1>Connector Operations</h1>
          <p>Health، Sync فقط‌خواندنی، provenance و تاریخچه اجرا برای اتصال‌های زیرساختی</p>
        </div>
        <div className="headActions">
          <button className="primary" onClick={load} disabled={loading}>{loading ? "در حال بروزرسانی…" : "بروزرسانی"}</button>
        </div>
      </div>

      <div className="securityNotice">
        <strong>مرز امنیتی:</strong>
        <span>این صفحه secret واقعی را نمایش نمی‌دهد و نتیجه Connector به‌تنهایی کنترل یا requirement را compliant/effective اعلام نمی‌کند.</span>
      </div>

      {message && <p className="successBanner">{message}</p>}
      {error && <p className="errorBanner">{error}</p>}

      <div className="connectorStats">
        <article><span>کل اتصال‌ها</span><strong>{loading ? "…" : stats.total}</strong></article>
        <article><span>فعال</span><strong>{loading ? "…" : stats.active}</strong></article>
        <article><span>آخرین Sync موفق</span><strong>{loading ? "…" : stats.healthyLastSync}</strong></article>
        <article><span>آخرین Sync ناموفق</span><strong>{loading ? "…" : stats.failedLastSync}</strong></article>
      </div>

      {!loading && connectors.length === 0 ? (
        <section className="panel emptyPanel">
          <h2>هنوز Connector تعریف نشده است</h2>
          <p>Connector configuration باید توسط کاربر مجاز و با reference به secretهای محیطی ایجاد شود. برای تست live بعدی، credential واقعی داخل UI یا GitHub ثبت نشود.</p>
        </section>
      ) : (
        <section className="connectorGrid">
          {connectors.map((connector) => {
            const healthState = health[connector.id];
            const envRefs = [connector.username_env_var, connector.secret_env_var, connector.secondary_secret_env_var].filter(Boolean);
            return (
              <article key={connector.id} className="connectorCard">
                <div className="connectorCardHead">
                  <div>
                    <span className={`statusDot ${connector.is_active ? "on" : "off"}`} />
                    <strong>{connector.name}</strong>
                    <small>{providerLabels[connector.connector_type] ?? connector.connector_type}</small>
                  </div>
                  <span className={`runStatus ${connector.last_status || "unknown"}`}>{connector.last_status || "never-synced"}</span>
                </div>

                <dl className="connectorMeta">
                  <div><dt>Target</dt><dd className="ltrText">{connector.base_url || String(connector.configuration?.host ?? "—")}</dd></div>
                  <div><dt>TLS verify</dt><dd>{connector.verify_tls ? "فعال" : "غیرفعال"}</dd></div>
                  <div><dt>آخرین Sync</dt><dd>{formatDate(connector.last_sync_at)}</dd></div>
                  <div><dt>Secret references</dt><dd className="ltrText">{envRefs.join(", ") || "—"}</dd></div>
                </dl>

                {connector.last_error && <div className="connectorError"><strong>آخرین خطای ثبت‌شده</strong><span>{connector.last_error}</span></div>}

                {healthState && (
                  <div className={`healthResult ${healthState.state}`}>
                    <strong>{healthState.state === "ok" ? "Health: OK" : healthState.state === "running" ? "Health: checking…" : "Health: failed"}</strong>
                    {healthState.message && <span>{healthState.message}</span>}
                    {healthState.checkedAt && <small>{formatDate(healthState.checkedAt)}</small>}
                  </div>
                )}

                <div className="connectorActions">
                  <button
                    onClick={() => runHealth(connector)}
                    disabled={!connector.is_active || busy[`health:${connector.id}`]}
                  >
                    {busy[`health:${connector.id}`] ? "در حال بررسی…" : "Health check"}
                  </button>
                  <button
                    className="primary"
                    onClick={() => runSync(connector)}
                    disabled={!connector.is_active || busy[`sync:${connector.id}`]}
                  >
                    {busy[`sync:${connector.id}`] ? "در حال Sync…" : "Run read-only sync"}
                  </button>
                </div>
              </article>
            );
          })}
        </section>
      )}

      <section className="panel runHistory">
        <div className="panelHead">
          <div>
            <h2>Connector Run History</h2>
            <p className="muted">آخرین اجراها؛ summary از داده نرمال‌شده provider و بدون secret واقعی</p>
          </div>
          <select value={selected} onChange={(event) => setSelected(event.target.value)}>
            <option value="">همه اتصال‌ها</option>
            {connectors.map((connector) => <option key={connector.id} value={connector.id}>{connector.name}</option>)}
          </select>
        </div>

        {!loading && visibleRuns.length === 0 ? (
          <p className="emptyState">هیچ اجرای ثبت‌شده‌ای در این محدوده وجود ندارد.</p>
        ) : (
          <div className="tableScroll">
            <table className="dataTable">
              <thead>
                <tr>
                  <th>Connector</th>
                  <th>وضعیت</th>
                  <th>شروع</th>
                  <th>پایان</th>
                  <th>Dataset / Schema</th>
                  <th>Evidence</th>
                  <th>Summary / Error</th>
                </tr>
              </thead>
              <tbody>
                {visibleRuns.map((run) => {
                  const connector = connectors.find((item) => item.id === run.connector);
                  return (
                    <tr key={run.id}>
                      <td>{connector?.name ?? run.connector}</td>
                      <td><span className={`runStatus ${run.status}`}>{run.status}</span></td>
                      <td>{formatDate(run.started_at)}</td>
                      <td>{formatDate(run.finished_at)}</td>
                      <td>
                        <strong>{run.summary?.dataset || "—"}</strong>
                        <small className="blockText">schema: {run.summary?.provider_schema_version || "—"}</small>
                      </td>
                      <td>{run.summary?.evidence_id ? <Link href="/evidence">{run.summary.evidence_id.slice(0, 8)}…</Link> : "—"}</td>
                      <td>
                        {run.error ? <span className="inlineError">{run.error}</span> : <pre className="compactJson">{safeJson(run.summary?.fact_summary)}</pre>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
