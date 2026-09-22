# پلتفرم GRC — نقشه قابلیت‌ها (فارسی)

وضعیت‌ها: **پیاده‌سازی‌شده**، **پیاده‌سازی‌شده / اثبات واقعی باقی مانده**، **در حال انجام**، **برنامه‌ریزی‌شده قبل از v1**، **وابسته به محتوا/مجوز**، **Post-v1**.

| حوزه | قابلیت | چرا وجود دارد / هدف محصول | وضعیت |
|---|---|---|---|
| Tenant | جداسازی چند Tenant | مرزبندی داده و مجوز بین سازمان‌ها | پیاده‌سازی‌شده |
| سازمان | سلسله‌مراتب واحدهای سازمانی | Scope واقعی برای Control، Risk، Assessment و Evidence | پیاده‌سازی‌شده |
| Identity | Role/Permission و RBAC مبتنی بر Organization Scope | اعمال Least Privilege فراتر از عضویت ساده در Tenant | پیاده‌سازی‌شده |
| Identity | MFA و Browser Security Policy | احراز هویت سازمانی و کنترل امنیتی قابل Audit | پیاده‌سازی‌شده |
| Framework | Framework / Version / Requirement | مدل‌کردن استانداردها و مقررات به‌صورت داده نسخه‌دار | پیاده‌سازی‌شده |
| Framework | Requirement سلسله‌مراتبی | حفظ ساختار واقعی استانداردها و Control Setها | پیاده‌سازی‌شده |
| Framework | Translation | نمایش فارسی/انگلیسی بدون دوپلیکیت منطق برنامه | Foundation پیاده‌سازی‌شده |
| Framework | Import/Export + Provenance/Licensing | ورود امن محتوای Customer/Licensed با حفظ منبع و وضعیت حقوقی | پیاده‌سازی‌شده |
| Framework | Requirement Crosswalk | اتصال Requirementهای مشابه/مرتبط در چند چارچوب | Foundation پیاده‌سازی‌شده؛ نیازمند Human Approval |
| Content | Workflow محتوای مجاز افتا | پشتیبانی Tenant-scoped بدون بازتوزیع غیرمجاز | پیاده‌سازی‌شده / وابسته به مجوز محتوا |
| Content | ISMS/ISO 27001 Pack مجاز | تکمیل محتوای واقعی ISMS و Crosswalk نهایی | وابسته به محتوا/مجوز |
| Controls | Common Control Library | استفاده مجدد از یک تعریف کنترل در چند Framework | پیاده‌سازی‌شده |
| Controls | Mapping کنترل به Requirement | اجرای «Implement once, comply many» | پیاده‌سازی‌شده |
| Controls | Control Implementation | ثبت نحوه پیاده‌سازی واقعی کنترل در واحد سازمانی | پیاده‌سازی‌شده |
| Controls | Control Testing و Test Run تاریخی | تفکیک ادعای پیاده‌سازی از سنجش Effectiveness | پیاده‌سازی‌شده |
| Assets | Asset Inventory/Context | ایجاد Context برای Risk، Evidence و Control | پیاده‌سازی‌شده |
| Processes | Process Context | اتصال فرآیندهای کسب‌وکار به Risk/Assurance | Foundation / نیازمند گسترش |
| Risk | Risk Register و Category | مدیریت هویت و سناریوی ریسک | پیاده‌سازی‌شده |
| Risk | Methodology/Scale | مدل امتیازدهی ریسک قابل تنظیم برای Tenant | پیاده‌سازی‌شده |
| Risk | Inherent/Current/Residual/Target Evaluation | حفظ تاریخچه امتیازها بدون overwrite Risk | پیاده‌سازی‌شده |
| Risk | Treatment + Action | تبدیل تصمیم ریسک به اقدام قابل پیگیری | پیاده‌سازی‌شده |
| Risk | خروجی RTP | تولید Risk Treatment Plan | پیاده‌سازی‌شده |
| Risk | Appetite/Tolerance | تعیین مرز پذیرش و Escalation ریسک | نیاز محصول؛ بلوغ UX/Policy بیشتر لازم است |
| Risk | FAIR / Monte Carlo | تحلیل کمی پیشرفته ریسک | Post-v1 |
| Assessment | ساخت Assessment از Framework Version | شروع ارزیابی از محتوای قفل‌شده و نسخه‌دار | پیاده‌سازی‌شده |
| Assessment | Snapshot Requirement | حفظ چیزی که واقعاً در زمان ارزیابی سنجیده شده | پیاده‌سازی‌شده |
| Assessment | Compliance/Maturity/Score/Status | ثبت نتیجه Human-reviewed | پیاده‌سازی‌شده |
| Assessment | Review/Complete Control | جلوگیری از تکمیل خودکار و بی‌ردپا | پیاده‌سازی‌شده |
| Evidence | Evidence مستقل و Reusable | جمع‌آوری یک‌بار و استفاده مجدد در روابط معتبر | پیاده‌سازی‌شده |
| Evidence | Source/Scope/Time/Hash/Provenance | Auditability و Integrity | پیاده‌سازی‌شده |
| Evidence | Object Storage Abstraction | نگهداری فایل خارج از DB رابطه‌ای | Foundation پیاده‌سازی‌شده |
| Evidence | Upload Quarantine / Clean-state Gate | Fail-closed قبل از Download فایل مشکوک | پیاده‌سازی‌شده؛ Malware Scanner واقعی باقی مانده |
| Findings | Finding / NCR | ثبت Gap و Non-Conformity | پیاده‌سازی‌شده |
| CAPA | Action / Remediation / Verification | رساندن Finding و Treatment به Closure | پیاده‌سازی‌شده |
| Audit | Internal Audit Engagement | Planning/Execution رسمی Audit | Foundation پیاده‌سازی‌شده |
| Audit | Workpaper | نگهداری Evidence و منطق اجرای Audit | پیاده‌سازی‌شده |
| Audit | Audit Report | تولید خروجی رسمی Audit | پیاده‌سازی‌شده |
| Documents | Versioning/Approval اسناد | Lifecycle کنترل‌شده Policy/Procedure/Document | Foundation پیاده‌سازی‌شده |
| Reports | SoA | تولید Statement of Applicability از داده GRC | پیاده‌سازی‌شده |
| Reports | RTP | تولید Risk Treatment Plan | پیاده‌سازی‌شده |
| Reports | Management/Compliance/Risk/Audit Reports | تبدیل داده به خروجی مدیریتی و عملیاتی | Foundation پیاده‌سازی‌شده؛ توسعه UI/Report ادامه دارد |
| Reports | جهت خروجی DOCX/PDF/XLSX/CSV/JSON | پوشش نیازهای عملیاتی و مدیریتی در قالب سند و داده ساختاریافته | Foundation جزئی؛ پوشش کامل‌تر برنامه‌ریزی‌شده |
| Reports | Template Designer قابل تنظیم | کنترل Layout و Template گزارش/سند بدون Hard-code کردن هر قالب | هدف محصول / بلوغ Post-v1 |
| Workflow | Assignment/Due Date/Approval عمومی | Orchestration مشترک بین ماژول‌ها | Foundation پیاده‌سازی‌شده |
| Workflow | Task Inbox / Work Center بین‌ماژولی | نمایش یکپارچه Review، Approval، Action و Due Work برای کاربر | هدف حفظ‌شده UX؛ هنوز کامل نیست |
| Workflow | Workflow/Indicator/Model قابل تنظیم | پشتیبانی از فرآیندهای Governance و Indicatorهای خاص هر سازمان | Foundation موجود؛ توسعه بیشتر برنامه‌ریزی‌شده |
| Notification | اعلان رویداد و کار | رساندن وظیفه و هشدار به کاربر | Foundation پیاده‌سازی‌شده |
| Integration | REST API | اتصال سیستم‌ها و ابزارهای مجاز با همان مدل Authorization | Foundation پیاده‌سازی‌شده |
| Integration | MCP / Tool Adapter | Orchestration ابزار و AI بدون دورزدن RBAC/Audit | جهت حفظ‌شده / برنامه‌ریزی‌شده |
| AI | AI Gateway مستقل از Provider | جلوگیری از Vendor Lock-in و پشتیبانی AI محلی | پیاده‌سازی‌شده |
| AI | Ollama/vLLM/OpenAI-compatible | Cloud/Private/Air-gapped AI | Foundation پیاده‌سازی‌شده / تست Host واقعی باقی مانده |
| AI | AISuggestion + Human Review | جلوگیری از Authority پیدا کردن AI | اصل و Flowهای پشتیبان پیاده‌سازی‌شده |
| RAG | Permission-safe Retrieval | جلوگیری از نشت Cross-tenant/Scope قبل از Prompt | Foundation پیاده‌سازی‌شده |
| RAG | pgvector + Lexical Fallback | Retrieval معنایی همراه fallback قابل‌پیش‌بینی | Pilot پیاده‌سازی‌شده |
| AI | Draft/Summary/Mapping/Remediation Suggestion | افزایش سرعت کار GRC بدون حذف مسئولیت انسانی | Foundation پیاده‌سازی‌شده / توسعه تدریجی |
| Connectors | AD/LDAP Read-only | جمع‌آوری Factهای Identity/Account | پیاده‌سازی‌شده / Live Proof باقی مانده |
| Connectors | FortiGate Read-only | جمع‌آوری Factهای Security/Network | پیاده‌سازی‌شده / Live Proof باقی مانده |
| Connectors | Veeam Read-only | جمع‌آوری Factهای Backup/Assurance | پیاده‌سازی‌شده / Live Proof باقی مانده |
| Connectors | Tenable/Nessus Read-only | دریافت Fact و Evidence آسیب‌پذیری از Scanner خارجی؛ خود GRC اسکنر نیست | پیاده‌سازی‌شده / Live Proof باقی مانده |
| Connectors | Normalized Evidence Contract | قابل‌استفاده و Auditable کردن داده چند Provider | پیاده‌سازی‌شده |
| Connectors | Health/Sync/Run History UI | عملیات Connector بدون نمایش Secret | پیاده‌سازی‌شده |
| Dashboard | Management Dashboard با داده واقعی | حذف داده Demo از Production | پیاده‌سازی‌شده |
| Dashboard | Indicator/KPI مدیریتی قابل تنظیم | ساخت نماهای مدیریتی Traceable از داده Authoritative | جهت حفظ‌شده / نیازمند توسعه |
| Security | Auth Throttling / TOTP Anti-replay / CSRF | کاهش Brute Force/Replay/Browser Attack | پیاده‌سازی‌شده |
| Security | Cross-tenant IDOR Test | اثبات اینکه UUID باعث دورزدن Scope نمی‌شود | پیاده‌سازی‌شده |
| Security | Report SSRF/Local-file Boundary | جلوگیری از دسترسی Renderer به Network/File | پیاده‌سازی‌شده |
| Security | SAST/Secret/Container Scan/SBOM Gate | جلوگیری از Release با Risk شناخته‌شده | پیاده‌سازی‌شده |
| Deployment | Docker Pilot | Foundation استقرار On-Prem قابل تکرار | پیاده‌سازی‌شده |
| Deployment | TLS Reverse Proxy | مرز امنیت Browser/Production | Foundation پیاده‌سازی‌شده / Real-host Proof باقی مانده |
| Deployment | S3-compatible Local Storage | File Storage مستقل و Sovereign | Foundation پیاده‌سازی‌شده |
| Deployment | Local AI Profile | Runtime اختیاری AI بدون اینترنت | Foundation پیاده‌سازی‌شده / No-egress Proof باقی مانده |
| Deployment | سیاست صریح External Egress | جلوگیری از فرض اینکه داده مشتری مجاز است از محیط On-Prem/Air-gapped خارج شود | نیاز محصول/Deployment |
| Operations | Backup/Restore Tooling | بازیابی DB/Object/Config پس از Failure | Foundation پیاده‌سازی‌شده / Drill واقعی باقی مانده |
| Operations | RPO/RTO Measurement | سنجش Recoverability به‌جای فرض‌کردن | Real-world Proof باقی مانده |
| Performance | Query Amplification/N+1 Regression | جلوگیری از کندشدن List API با افزایش ردیف | در حال انجام (#20) |
| Performance | HTTP Load Harness | اندازه‌گیری p50/p95/Error Rate روی Host واقعی | در حال انجام (#20) |
| HA/DR | Reference Topology | طراحی Availability و Disaster Recovery | قبل از v1 (#21) |
| Upgrade | Upgrade/Rollback Rehearsal | اثبات امکان برگشت عملیاتی | قبل از v1 (#21) |
| Release | Deterministic Offline Bundle | نصب/آپدیت محیط Disconnect | قبل از v1 (#22) |
| Support | Operator/Support Handbook | Runbook اجرایی برای تیم استقرار و پشتیبانی | قبل از v1 (#22) |
| Validation | Independent Pentest | اعتبارسنجی خارجی قبل از Production | Real-world Proof باقی مانده (#8) |
| TPRM | Vendor/Third-party Risk Portal | گسترش GRC به Supplier Assurance | Post-v1 |
| BCM | BIA / Continuity | مدیریت تاب‌آوری و Business Impact | Post-v1 |
| Incidents | Incident Management | اتصال Incident به Risk/Control/Action | Post-v1 |
| CCM | Continuous Control Monitoring | حرکت از Assurance مقطعی به سیگنال مستمر | Post-v1 |
| Mobile | PWA/Mobile Approval | Review/Approval سبک روی موبایل | Post-v1 |
