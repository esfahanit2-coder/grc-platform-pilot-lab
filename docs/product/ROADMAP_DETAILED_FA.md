# پلتفرم GRC — رودمپ تفصیلی (فارسی)

این رودمپ فقط فهرست کارها نیست؛ برای هر Gate توضیح می‌دهد چرا وجود دارد، چه چیزی باید اثبات شود و چه زمانی واقعاً Complete محسوب می‌شود.

## اهداف انتشار

- `v0.9.0-pilot`: نسخه Pilot قابل استفاده End-to-End با Workflowهای واقعی GRC و اثبات عملیاتی کنترل‌شده.
- `v1.0.0-rc1`: Release Candidate بعد از تکمیل Hardening مهندسی، امنیت و عملیات قبل از v1.

## Gate 0 — نرمال‌سازی Repo و CI — کامل

**هدف:** قبل از سرعت‌دادن به Feature Development، GitHub باید منبع قابل‌تکرار و قابل‌اعتماد پروژه باشد.

موارد انجام‌شده شامل Repo خصوصی Canonical، package-lock واقعی، CI Backend/Frontend، Migration از DB خالی روی PostgreSQL 18 + pgvector، Full Django Test، Next.js Production Build، SAST، Secret Scan، Container Scan، SBOM و Release Gate است.

**Done یعنی:** Commit یا Release در صورت Failure شدن Gateهای اصلی Build/Security/Runtime نباید عبور کند.

## Gate 1 — Foundation پایلوت داخلی — نرم‌افزار کامل، اثبات Host واقعی باقی مانده (#7)

**هدف:** اثبات اینکه محصول واقعاً می‌تواند On-Prem و Sovereign اجرا شود، نه فقط در محیط Development/CI.

نرم‌افزار فعلی شامل Pilot Compose، TLS Gateway، S3-compatible Local Storage، Local AI اختیاری، Readiness Check، Backup/Restore و Runbook عملیاتی است.

موارد باقی‌مانده:
- استقرار روی Clean Pilot Host؛
- اجرای واقعی و Destructive Backup/Restore Drill؛
- اندازه‌گیری واقعی RPO/RTO؛
- تست Cookie/CSRF روی TLS واقعی؛
- اجرای Ollama/vLLM در شرایط بدون Internet Egress.

**Done یعنی:** یک Operator دیگر بتواند فقط با Artifact و Runbookهای رسمی محصول را Deploy، Restore و Operate کند و Evidence اندازه‌گیری‌شده بازیابی داشته باشیم.

## Gate 2 — Content Pilot — Foundation کامل، Content مجاز باقی مانده (#5)

**هدف:** اثبات مدل Framework-as-Content با محتوای واقعی و قابل استفاده از نظر حقوقی.

انجام‌شده:
- Content Pack نسخه‌دار و Import Model؛
- Licensing/Provenance Metadata؛
- مسیر Tenant-scoped برای Restricted Content؛
- Foundation تبدیل AFTA Customer-provided؛
- مسیر Human Approval برای Mapping/Crosswalk؛
- Internal Example Control Baseline؛
- SoA/RTP/Audit/Report Outputs.

باقی‌مانده:
- منبع مجاز ISMS/ISO 27001؛
- مستندسازی حق استفاده نرم‌افزاری/بازتوزیع در صورت نیاز؛
- حداقل یک Mapping واقعی AFTA ↔ ISMS ↔ Internal/Common-Control با Human Approval.

**Done یعنی:** محصول Multi-framework Reuse را با Content واقعی و بدون نقض حقوق محتوا اثبات کند.

## Gate 3 — Connector Pilot — Implementation و UI کامل، Live Proof باقی مانده (#6)

**هدف:** اثبات اینکه Factهای Infrastructure می‌توانند تبدیل به Evidence قابل Audit و Reusable شوند، بدون اینکه Human Judgment دور زده شود.

Providerهای پیاده‌سازی‌شده:
- AD/LDAP
- FortiGate
- Veeam
- Tenable/Nessus

Boundaryهای پیاده‌سازی‌شده شامل Read-only Collection، Secret Reference، SSRF Restriction، Target Validation، Normalized Dataset، Evidence Provenance/Hash، Failure Diagnostics، Human-review Metadata و Connector Operations UI با Health/Sync/Run History هستند.

باقی‌مانده:
- اجرای Health/Sync واقعی روی سیستم‌های داخلی مجاز؛
- ساخت Evidence واقعی از حداقل سه Connector؛
- ثبت Failure نماینده و اثبات Diagnosability.

**Done یعنی:** سیستم‌های واقعی داخلی همان Contractهایی را اثبات کنند که الان با Offline/Synthetic Testها پوشش داده شده‌اند.

## Gate 4 — Hardening برای v1.0 Release Candidate

### #19 Operational UI — کامل

داده Demo تولیدی از Dashboard حذف شده، Management Metricها Tenant-scoped و واقعی هستند و Connector Operations UI با Loading/Empty/Error State مناسب وجود دارد.

### #20 Performance/Load Readiness — کامل از نظر Software Validation

اعتبارسنجی تکرارپذیر Pre-RC اکنون شامل Regression Test برای N+1/Query Amplification، HTTP Load Harness بدون وابستگی اضافه، خروجی Machine-readable برای Latency/Error/Throughput، Self-test در CI و Engineering Budgetهای موقت و مستند است. این Budgetها SLO قراردادی یا ادعای Production Capacity نیستند و اندازه‌گیری Representative Host همچنان Evidence عملیاتی است.

### #21 HA/DR و Upgrade/Rollback — کامل از نظر Reference و Software Tooling

Repo اکنون شامل موارد زیر است:
- Reference Topology مستند HA/DR و Failure Domainهای صریح؛
- Recovery Ordering برای DB/Object Store/Redis/Application و Decision Pointهای Operator؛
- تحلیل Machine-readable برای ایمنی Django Migration Plan؛
- Migration Rehearsal روی PostgreSQL 18 یک‌بارمصرف از Release مبنا تا Target؛
- Pre-upgrade Backup نسخه‌دار و Quiesced با Source Commit و PostgreSQL Compatibility Check؛
- Upgrade Sequence به‌صورت Fail-closed؛
- Rollback مبتنی بر Backup و Exact Source Commit؛
- Disaster-recovery Restore از Ancestor به نسخه جدید فقط با Approval صریح و Gateهای سازگاری؛
- تفکیک شفاف بین رفتار اثبات‌شده در Repo/CI و Evidence واقعی زیرساختی برای Failover/RPO/RTO.

Replication/Failover واقعی و RPO/RTO اندازه‌گیری‌شده همچنان باید در محیط واقعی و تحت #7 اثبات شوند و CI هیچ ادعایی درباره آن‌ها ندارد.

### #22 Offline Release Bundle و Support — کامل از نظر Software/Tooling Contract

Repo اکنون شامل موارد زیر است:
- Release Manifest قطعی با SHA-256/Size دقیق Payload و ردکردن File اضافه/کم‌شده یا Tamper؛
- امضای Detached با OpenSSL، با Private Key خارج از Git/CI و Trust Anchor عمومی که از کانال مستقل به Operator می‌رسد؛
- Archive دقیق Imageهای Backend/Frontend و Infrastructure Pin‌شده به‌همراه Verification بر اساس Docker Image ID؛
- Git Source Bundle دقیق، CycloneDX SBOM، Migration Inventory و Configuration Schema عمومی؛
- Reference/Digest برای Security Reportهای نگه‌داری‌شده، بدون قراردادن Raw Secret-scan Output در Media توزیع؛
- Install/Update آفلاین که قبل از Mutation امضا را Verify می‌کند و فقط از Imageهای Preloaded با `--no-build` استفاده می‌کند؛
- اتصال Upgrade آفلاین به مسیر Fail-closed و Rollback مبتنی بر Backup/Release Version؛
- Metadata مدل Local AI به‌صورت Reference-only تا Weightهای Third-party توسط این Release Process بازتوزیع نشوند؛
- Operator/Support Handbook یکپارچه و Support Evidence Collector با حداقل‌سازی Secret/Customer Data؛
- Self-test در CI/Release Gate برای Manifest قطعی، امضای Ephemeral، Verification و رد Tamper.

Custody واقعی کلید امضای Production/HSM و مشاهده نصب روی Host واقعاً Disconnect همچنان Evidence سازمان/محیط است و CI چنین ادعایی نمی‌کند.

### #8 Security Validation مستقل — Automated Hardening کامل، External Proof باقی مانده

پوشش فعلی شامل Auth Throttling، TOTP Anti-replay، CSRF Negative Path، Cross-tenant IDOR، Evidence Quarantine و Fail-closed Download، Export Audit، SSRF/Local-file Protection برای Report Renderer، RAG Untrusted-context Guardrail، SAST، Secret Scan، Container Scan و SBOM است.

باقی‌مانده:
- Pentest مستقل؛
- Malware Scanner واقعی یا Substitute عملیاتی رسمی و پذیرفته‌شده؛
- Adversarial Test روی AI Provider واقعی؛
- Security Sign-off و Closure یافته‌ها.

## توسعه Post-v1

اولویت‌های ثبت‌شده برای بعد از v1:
- TPRM/Vendor Portal؛
- BCM/BIA و Continuity Workflow؛
- Incident Management؛
- Continuous Control Monitoring؛
- Connector Packهای بیشتر؛
- FAIR/Quantitative Risk/Monte Carlo؛
- Report/Document Templateهای پیشرفته و regulated؛
- AI Governance مثل ISO 42001 در صورت مجوز؛
- Digital Transformation Maturity Pack؛
- Mobile/PWA Approval.

## انضباط رودمپ

صرف وجود کد باعث Complete شدن Gate نمی‌شود. اگر Acceptance به Host واقعی، Connector واقعی، Content مجاز یا Validation مستقل وابسته است، Issue باید باز بماند تا Evidence واقعی وجود داشته باشد. در مقابل، نبود دسترسی فعلی به زیرساخت مشتری نباید کارهای نرم‌افزاری مستقل و قابل تست آفلاین را متوقف کند.
