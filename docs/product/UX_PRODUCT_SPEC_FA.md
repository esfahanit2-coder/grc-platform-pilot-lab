# پلتفرم GRC — مشخصات تجربه کاربری فارسی/RTL

## هدف

رابط کاربری باید برای استفاده روزمره سازمانی در محیط فارسی‌زبان طراحی شود، نه اینکه صرفاً یک UI انگلیسی باشد که متن‌های آن ترجمه شده‌اند. RTL، اصطلاحات، حجم اطلاعات، Traceability و وضعیت‌های تأیید/پیشنهاد باید در طراحی اصلی دیده شوند.

## اصول پایه

### فارسی‌محور، ولی دو‌زبانه
- متن عمومی و Navigation باید قابلیت فارسی/انگلیسی داشته باشد.
- اصطلاحات تخصصی شناخته‌شده مانند Risk، Control، Evidence، Assessment، SoA، RTP یا نام استانداردها می‌توانند در کنار معادل فارسی نمایش داده شوند تا ابهام کم شود.
- تاریخ، عدد، Code، UUID، IP، URL و JSON باید در محل لازم LTR باقی بمانند حتی در صفحه RTL.

### RTL واقعی
- Sidebar، Breadcrumb، Table Alignment، Form Layout، Pagination، Modal و Icon Direction باید در RTL درست باشند.
- محتوای فنی LTR نباید باعث شکستن Layout شود.
- Responsive Design باید روی نمایشگر کوچک و ارتفاع کم نیز Navigation قابل دسترس نگه دارد.

### داده واقعی، نه Demo
- Production UI نباید KPI، نام کاربر، Risk یا Compliance Score ساختگی نمایش دهد.
- Loading State، Empty State و Error State باید صریح باشند.
- اگر داده‌ای وجود ندارد، UI باید همین موضوع را نشان دهد نه اینکه با Sample Data پر شود.

### Scope و Permission قابل فهم
- کاربر فقط داده‌ای را ببیند که Backend مجاز کرده است.
- در صورت Scope محدود، UI بهتر است Scope فعلی را قابل مشاهده کند.
- Permission denial نباید با Empty Data اشتباه گرفته شود؛ خطا باید قابل فهم باشد.

### Human Review باید در UI واضح باشد
وضعیت‌های زیر باید از هم قابل تشخیص باشند:
- Draft
- Automated/Collected
- AI Suggested
- Pending Review
- Approved/Authoritative
- Rejected/Superseded

کاربر نباید Evidence خودکار یا AI Suggestion را با نتیجه نهایی Compliance اشتباه بگیرد.

## Navigation پیشنهادی بر اساس مدل محصول

Navigation اصلی باید بتواند این حوزه‌ها را بدون شلوغی غیرضروری پوشش دهد:

- Dashboard / نمای مدیریتی
- Work Center / کارهای من
- Organization / ساختار سازمان
- Frameworks / الزامات
- Controls / پیاده‌سازی کنترل
- Assets / Processes
- Risks / RTP
- Assessments / Compliance
- Evidence
- Findings / Actions / CAPA
- Internal Audit / Workpapers
- Documents / Reports
- Connectors / Operations
- AI Assistant در Contextهای مجاز
- Administration / RBAC / Security / Settings

ماژول‌های Post-v1 مثل TPRM، BCM/BIA، Incidents و CCM بعداً می‌توانند به همین Information Architecture اضافه شوند.

## Work Center / Task Inbox

جهت اصلی UX این است که کاربر برای پیدا کردن مسئولیت‌هایش مجبور نباشد تک‌تک ماژول‌ها را باز کند. Work Center باید در بلوغ محصول مواردی مثل این‌ها را یکجا جمع کند:
- Assessment Itemهای Assign‌شده؛
- Review و Approvalهای در انتظار؛
- Risk Treatment Actionها؛
- Finding/CAPA Actionها؛
- Document Review/Approval؛
- Audit Task/Workpaperهای مسئولیت‌دار؛
- موارد Overdue و Due Soon.

هر آیتم باید Source Module، Scope، Priority/Severity، Due Date، Status و لینک مستقیم به رکورد اصلی داشته باشد. Work Center نباید Business State جدید و مستقل بسازد؛ نمای عملیاتی روی Task/Workflowهای مرجع است.

## الگوی صفحه‌های لیست

List Page سازمانی باید تا حد ممکن شامل این موارد باشد:
- عنوان و توضیح کوتاه «این صفحه برای چیست»؛
- Search/Filterهای مهم؛
- Status و Scope واضح؛
- Pagination یا Virtualization مناسب؛
- Empty/Error/Loading State؛
- Actionهای مجاز بر اساس Permission؛
- لینک به Detail/Traceability؛
- Export در صورت نیاز و مجاز بودن؛
- عدم نمایش Secret یا Sensitive Data غیرضروری.

## الگوی صفحه Detail

Detail Page بهتر است پاسخ دهد:
- این رکورد چیست؟
- Owner و Scope آن چیست؟
- وضعیت فعلی چیست؟
- از چه چیزی آمده و به چه چیزهایی متصل است؟
- چه Evidence/Control/Risk/Finding/Actionهایی مرتبط هستند؟
- چه تغییرات/Reviewهایی رخ داده؟
- چه Action بعدی لازم است؟

## Traceability View

یکی از تمایزهای اصلی محصول باید قابلیت دنبال‌کردن زنجیره باشد، برای مثال:

`Requirement -> Common Control -> Control Implementation -> Evidence -> Test -> Assessment Item -> Finding -> Action`

و برای Risk:

`Asset/Process -> Risk -> Evaluation History -> Control -> Treatment -> Action -> RTP`

این روابط باید در UI قابل فهم باشند، نه اینکه کاربر مجبور باشد UUIDها را دستی دنبال کند.

## Dashboard

Dashboard مدیریتی باید:
- فقط داده واقعی و Tenant-scoped نشان دهد؛
- تعداد Finding/Action، Residual Risk، Assessment و Control Effectiveness را از منبع واقعی بگیرد؛
- امکان Drill-down به رکورد منبع داشته باشد؛
- محدودیت داده یا Empty State را شفاف نشان دهد؛
- Indicator/KPI فقط از داده Authoritative و قابل Trace مشتق شود؛
- در آینده Viewهای Role-specific برای Executive، GRC Admin، Risk Owner و Auditor قابل توسعه باشد.

## Assessment UX

Assessment باید Workflow کاربر را هدایت کند:
- Requirement Snapshot و توضیح قابل مشاهده؛
- Status/Maturity/Score واضح؛
- Mapped Controlها؛
- Evidence موجود و Evidence Missing؛
- Finding creation؛
- Assessor vs Reviewer state؛
- Progress کلی Assessment؛
- جلوگیری از Complete شدن وقتی موارد لازم ارزیابی نشده‌اند.

## Risk UX

Risk Detail باید History را برجسته کند:
- Scenario/Cause/Consequence؛
- Asset/Process/Org Context؛
- Inherent/Current/Residual/Target evaluation history؛
- Controlهای متصل؛
- Treatment Strategy و Actionها؛
- RTP generation؛
- Review/Target dates.

نمایش فقط «یک Risk Score» نباید تاریخچه واقعی را پنهان کند.

## Evidence UX

Evidence باید نشان دهد:
- Source؛
- Scope؛
- Collection/Upload time؛
- Automated vs Manual؛
- Connector/Run provenance در صورت وجود؛
- Integrity/hash metadata در صورت نیاز؛
- Scan/Clean/Pending state؛
- لینک‌های استفاده در Control Test/Assessment/Audit.

## Connector Operations UX

برای AD/FortiGate/Veeam/Tenable:
- Active/Inactive؛
- Provider؛
- Target امن؛
- TLS verify؛
- Secret reference name بدون Secret value؛
- Last status/sync/error؛
- Health؛
- Read-only Sync؛
- Run History؛
- Dataset/Schema؛
- Evidence IDs.

هیچ «Green Compliance» صرفاً از موفق بودن Connector تولید نمی‌شود. در مورد Vulnerability نیز GRC نتیجه Scanner خارجی مثل Tenable/Nessus یا معادل را مصرف می‌کند و خودش Scanner Engine نیست.

## AI UX

AI در UI باید همیشه Context و Authority خودش را روشن کند:
- چه کاری انجام می‌دهد؛
- روی چه Scope/Data مجازی کار می‌کند؛
- خروجی Draft/Suggestion است؛
- دکمه Accept/Apply باید Permission و Workflow عادی را رعایت کند؛
- Tool/Agent Action باید قبل از اجرا Permission و Scope واقعی Backend را طی کند؛
- Reject/Supersede قابل ثبت باشد؛
- در صورت Provider unavailable، Workflow اصلی GRC نباید از کار بیفتد.

## Document/Report UX

برای SoA، RTP، Audit Report، NCR/CAPA، Policy/Procedure و گزارش‌های مدیریتی:
- داده ساختاریافته منبع باید مشخص باشد؛
- Generation باید به‌عنوان Export/Generate ثبت شود؛
- جهت محصول باید DOCX/PDF/XLSX/CSV/JSON را بر اساس نوع خروجی پوشش دهد؛
- Template Designer در بلوغ بعدی باید Layout و Template قابل تنظیم ارائه دهد بدون اینکه Business Logic داخل Template منتقل شود؛
- اگر AI Narrative اضافه می‌کند باید قابل Review باشد؛
- Version/Approval History سند حفظ شود.

## API / Integration UX

Integration Configuration در صورت اضافه‌شدن باید:
- Scope و Identity سرویس را واضح نشان دهد؛
- Permissionهای آن قابل مشاهده و حداقلی باشند؛
- Secret Value را نمایش ندهد؛
- REST/MCP/Tool Adapter را به‌عنوان مسیر جایگزین RBAC معرفی نکند؛
- Event/Audit مرتبط با عملیات حساس قابل پیگیری باشد.

## Accessibility و Enterprise Quality

قبل از v1 باید حداقل روی این موارد توجه شود:
- Keyboard navigation برای Flowهای اصلی؛
- Label مناسب Formها؛
- Contrast قابل قبول؛
- Table readability؛
- Error message قابل اقدام؛
- عدم وابستگی معنی صرفاً به رنگ؛
- Responsive behavior حداقل برای Laptop/Tablet و Mobile approvalهای ساده در آینده.

## Definition of Done UX

یک Screen وقتی آماده Pilot محسوب می‌شود که:
- Fake data نداشته باشد؛
- Stateهای Loading/Empty/Error را داشته باشد؛
- RTL/LTR mixed content خراب نشود؛
- Permission/Scope را دور نزند؛
- Action مهم Feedback واضح بدهد؛
- Traceability لازم را نشان دهد یا لینک دهد؛
- Typecheck/Lint/Production Build عبور کند؛
- در صورت تغییر Contract، Feature Map و Docs مرتبط به‌روز شوند.
