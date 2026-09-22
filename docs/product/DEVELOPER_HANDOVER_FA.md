# پلتفرم GRC — تحویل به توسعه‌دهنده (فارسی)

## ۱. از کجا شروع کنید

ترتیب مطالعه پیشنهادی:

1. `docs/product/README.md`
2. `docs/product/PRODUCT_BRAIN_FA.md`
3. `docs/product/FEATURE_MAP_FA.md`
4. `docs/product/ROADMAP_DETAILED_FA.md`
5. `docs/product/DECISION_LOG.md`
6. `ARCHITECTURE.md`
7. `SECURITY.md`
8. `VALIDATION.md`
9. `RELEASE_BLOCKERS.md`
10. تست‌ها، Issueها و PRهای مرتبط با ماژول مورد نظر.

رفتار واقعی محصول را کد Merge‌شده روی `main` تعیین می‌کند. Product Brain هدف و چرایی تصمیم‌ها را توضیح می‌دهد.

## ۲. قواعد دامنه‌ای غیرقابل‌چشم‌پوشی

بدون تصمیم رسمی معماری/محصول این قواعد نباید شکسته شوند:

- Frameworkها Content نسخه‌دار هستند، نه Backend Branch اختصاصی برای هر استاندارد.
- Common Control باید در چند Requirement قابل‌استفاده باشد.
- Control Definition و Control Implementation موجودیت‌های جدا هستند.
- نتیجه Assessment روی AssessmentItem است، نه Requirement.
- Score/Stateهای ریسک در RiskEvaluation تاریخی نگهداری می‌شوند.
- Evidence موجودیت مستقل، Reusable، Scoped و Auditable است.
- Tenant و Organization Scope باید در Backend enforce شوند.
- AI حق تصمیم‌گیری نهایی درباره Risk/Compliance/Audit ندارد.
- Permission Filtering باید قبل از RAG Retrieval انجام شود.
- Connectorها Read-oriented و Evidence-focused هستند.
- محتوای محدود استانداردها بدون مجوز وارد Built-in Product نمی‌شود.
- قابلیت On-Prem/Air-Gapped نباید با تصمیم‌های جدید از بین برود.

## ۳. ساختار Repo

- `backend/` — برنامه Django/DRF با معماری Modular Monolith.
- `frontend/` — رابط Next.js/TypeScript.
- `content-packs/` — مثال و Specification محتوا؛ متن محدود بدون مجوز نباید اینجا قرار گیرد.
- `docs/` — مستندات معماری، عملیات، محصول و Validation.
- `scripts/` — ابزارهای Validation/Bootstrap/Ops.
- `.github/workflows/` — CI و Release Gates.

Domainهای اصلی Backend شامل Tenancy، Organization، Identity/RBAC، Framework، Control، Asset، Risk، Assessment، Evidence، Finding/Action، Internal Audit/Workpaper، Document/Reporting، Workflow/Notification، Connector و AI Gateway/RAG است.

## ۴. Definition of Done برای تغییر کد

صرف Compile شدن کافی نیست.

حداقل باید:
- Tenant/Scope Authorization بررسی شده باشد؛
- Mutationهای مهم در صورت نیاز Audit شوند؛
- Negative Pathها مثل Success Path تست شوند؛
- Migration تمیز باشد و `makemigrations --check` عبور کند؛
- Full Django Test در CI عبور کند؛
- در صورت ارتباط، Typecheck/Lint/Production Build فرانت سبز باشد؛
- Static/Security/Release Gate سبز بماند؛
- در صورت تغییر Contract محصول، Docs/Status نیز به‌روز شود.

برای Merge فقط نتیجه آخرین Head SHA معتبر است. سبز بودن Run قدیمی روی Head قبلی ملاک نیست.

## ۵. قانون Real-world Proof

برخی Issueها عمداً حتی بعد از تکمیل نرم‌افزار باز می‌مانند:

- Validation واقعی AD/FortiGate/Veeam/Tenable؛
- Clean-host و Destructive Restore/RPO/RTO؛
- Local AI بدون Egress؛
- Content/Crosswalk واقعی مجاز ISMS/AFTA/Common Control؛
- Pentest مستقل و Security Sign-off.

Fixture یا CI نباید جای این Evidence واقعی را بگیرد.

## ۶. قانون AI

تمام AI Featureها باید از Provider Abstraction عبور کنند و Authorization/Data Classification را رعایت کنند. کاربردهای مجاز شامل Draft، Summary، Mapping Suggestion، Remediation Suggestion، Document/Report Assistance و RAG است.

خروجی Consequential تا زمان Human Review صرفاً Suggestion است. Prompt نباید تنها Boundary مجوز باشد و Context بازیابی‌شده باید Untrusted Data محسوب شود.

## ۷. قانون Connector

Connector باید:
- به‌صورت پیش‌فرض Read-oriented باشد؛
- Secret Reference مجاز استفاده کند، نه Credential Literal؛
- Target/Network Boundary را Validate کند؛
- Fact/Evidence نرمال و Auditable تولید کند؛
- Source/Time/Scope/Run/Integrity Metadata نگه دارد؛
- Failure قابل تشخیص ولی بدون نشت Secret باشد؛
- به‌تنهایی Compliance یا Effectiveness را تعیین نکند.

## ۸. قانون Content Pack

Content Pack باید Framework Metadata، Version، Requirement، Translation/Mapping مجاز، Provenance و Licensing را حمل کند. Customer-provided Restricted Content تا زمانی که Redistribution Right صریح وجود نداشته باشد Tenant-scoped باقی می‌ماند.

## ۹. قانون UI

- فارسی/RTL و انگلیسی نیاز اصلی محصول هستند.
- KPI، User یا Risk ساختگی نباید در مسیر Production قرار گیرد.
- Loading/Empty/Error State باید واقعی و واضح باشد.
- Backend Authorization مرجع اصلی است؛ UI فقط آن را منعکس می‌کند.
- وضعیت Automated/AI/Advisory باید از داده Approved/Authoritative قابل تشخیص باشد.

## ۱۰. تمرکز فعلی رودمپ

تمرکز Pre-RC:
- Performance/Query/Load Validation (#20)
- HA/DR و Upgrade/Rollback (#21)
- Offline Release Bundle و Support Handbook (#22)
- هم‌زمان Issueهای #5/#6/#7/#8 تا زمان رسیدن Environment/Content/Validation واقعی باز می‌مانند.

جهت Post-v1 شامل TPRM، BCM/BIA، Incident Management، Continuous Control Monitoring، Connectorهای بیشتر، FAIR/Quantitative Risk، Documentهای پیشرفته، AI Governance، Digital Transformation Maturity و Mobile/PWA Approval است.

## ۱۱. فرآیند تغییر

GitHub تاریخچه رسمی پروژه است:

`Issue -> Branch از current main -> Implementation/Test/Docs -> Draft PR -> latest-head CI + Release Gate -> Review/Thread Hygiene -> Ready -> Squash Merge -> Post-merge main CI`

برای سبزکردن Branch نباید Security/Test Threshold را پایین آورد. در صورت Failure باید Implementation یا Test غیرواقعی اصلاح شود.
