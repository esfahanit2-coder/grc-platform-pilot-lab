# پلتفرم GRC — سفرهای اصلی کاربر (فارسی)

این سند تجربه End-to-End مورد انتظار محصول را مشخص می‌کند. کامل بودن هر Screen از `FEATURE_MAP_FA.md` و Roadmap تبعیت می‌کند.

## پرسونای ۱ — مدیر برنامه GRC / ISMS

**هدف:** ایجاد ساختار سازمانی، ورود Frameworkهای مجاز و ساخت یک مدل مشترک Control/Compliance.

مسیر:
1. ایجاد Tenant و ساختار واحدهای سازمانی.
2. تعریف Membership، Role، Permission و Organization Scope.
3. Import یک Framework/Content Pack مجاز همراه Source/Licensing Metadata.
4. بازبینی و Lock/Active کردن Framework Version مناسب.
5. ساخت یا استفاده مجدد از Common Controlها.
6. Mapping کنترل‌ها به Requirementها؛ Mappingهای Imported/AI تا Human Review تأییدشده محسوب نمی‌شوند.
7. ایجاد Control Implementation برای واحد و Owner واقعی.
8. شروع Assessment، Audit یا Risk Work بر پایه همان Control/Evidence مشترک.

**نتیجه مورد انتظار:** سازمان به‌جای Spreadsheet و سیستم جدا برای هر استاندارد، یک مدل GRC مشترک دارد.

## پرسونای ۲ — Control Owner / Operator

**هدف:** ثبت و نگهداری نحوه اجرای واقعی یک Control در یک بخش سازمان.

مسیر:
1. مشاهده Control Implementationهای تخصیص‌یافته در Scope مجاز.
2. ثبت توضیح اجرا، Owner/Operator، Status و Review Date.
3. اتصال Evidence موجود یا Upload Evidence جدید.
4. اجرای Control Test یا مشارکت در آن.
5. مشاهده Test Runهای تاریخی و Findingها.
6. انجام Actionهای اصلاحی بدون تغییر تعریف Global/Common Control.

**نتیجه مورد انتظار:** ادعای پیاده‌سازی به Scope، Evidence و Test History قابل‌ردیابی است.

## پرسونای ۳ — ارزیاب / Reviewer انطباق

**هدف:** ارزیابی یک Framework Version با استفاده مجدد از Control و Evidence موجود.

مسیر:
1. ساخت Assessment از Framework Version قفل‌شده.
2. دریافت Assessment Item با Snapshot Requirement.
3. بررسی Controlهای Map‌شده و Evidence موجود.
4. ثبت Compliance/Maturity/Applicability و Comment.
5. درخواست یا اتصال Evidence مفقود.
6. ایجاد Finding/NCR برای Gapها.
7. Reviewer نتیجه را بازبینی کرده و تنها پس از رفع وضعیت‌های Unassessed/نامعتبر Assessment را Complete می‌کند.
8. تولید گزارش مدیریتی/انطباق و در صورت نیاز SoA.

**نتیجه مورد انتظار:** نتیجه ارزیابی Historical و Reviewable است و روی تعریف Requirement overwrite نمی‌شود.

## پرسونای ۴ — Risk Owner / Risk Manager

**هدف:** شناسایی، ارزیابی، Treatment و پایش Risk با حفظ تاریخچه Score.

مسیر:
1. ثبت Risk در Context مربوط به Asset/Process/Organization.
2. انتخاب Risk Methodology Tenant.
3. ثبت Inherent/Current/Residual/Target به‌صورت RiskEvaluationهای مستقل.
4. اتصال Control Implementationهای موجود.
5. انتخاب Treatment Strategy و ساخت Actionهای مسئولیت‌دار.
6. پایش Treatment و Evidence مربوط به Residual Risk.
7. تولید Risk Treatment Plan.
8. استفاده از Appetite/Tolerance برای Acceptance/Escalation با بلوغ بیشتر این بخش.

**نتیجه مورد انتظار:** تاریخچه دفاع‌پذیر Risk داریم، نه یک Score واحد قابل overwrite.

## پرسونای ۵ — Internal Auditor

**هدف:** اجرای Audit با استفاده از داده مشترک سازمان، Control و Evidence.

مسیر:
1. تعریف Audit Engagement و Scope.
2. ساخت Workpaper و ارجاع به Control/Requirement/Evidence مرتبط.
3. انجام Test و ثبت منطق و نتیجه Audit.
4. ایجاد Finding با Severity، Owner، Due Date و Remediation Link.
5. پیگیری Action و Verification.
6. تولید Audit Report.

**نتیجه مورد انتظار:** Audit بخشی از Traceability Chain مشترک GRC است و در Document Silo جدا نمی‌ماند.

## پرسونای ۶ — اپراتور Evidence / Infrastructure

**هدف:** تأمین Evidence معتبر بدون اختیار تصمیم‌گیری درباره Compliance.

مسیر:
1. Upload Evidence مجاز یا Configure کردن Connector Read-only.
2. استفاده از Secret Reference محیطی به‌جای ذخیره Credential در Repo/Product.
3. اجرای Health Check یا Read-only Sync.
4. مشاهده ConnectorRun، Dataset/Schema و Errorهای Redacted.
5. ایجاد Evidence با Scope/Source/Time/Hash/Provenance توسط سیستم.
6. کاربر GRC تعیین می‌کند Evidence چگونه در Test یا Assessment استفاده شود.

**نتیجه مورد انتظار:** Automation هزینه Collection را کم می‌کند ولی Authority در فرآیند Human Assurance باقی می‌ماند.

## پرسونای ۷ — Document / Policy Owner

**هدف:** تولید سند و Report کنترل‌شده از داده ساختاریافته GRC.

مسیر:
1. Draft یا Update سند/Policy/Procedure.
2. استفاده از AI Assistance برای Draft/Summary در صورت فعال بودن، با برچسب Non-authoritative.
3. ارسال در مسیر Review/Approval/Versioning.
4. تولید SoA، RTP، Audit Report یا گزارش دیگر از داده Authoritative.
5. حفظ Version و Approval History.

**نتیجه مورد انتظار:** AI سرعت تولید متن را بالا می‌برد ولی Governance سند دور زده نمی‌شود.

## پرسونای ۸ — مدیر / Executive Viewer

**هدف:** مشاهده وضعیت واقعی GRC بدون داده ساختگی یا خارج از Scope.

مسیر:
1. باز کردن Management Dashboard.
2. مشاهده شاخص‌های واقعی و Tenant-scoped در Compliance، Residual Risk، Finding/Action و Assessment.
3. Drill-down به رکوردهای مجاز و منبع داده.
4. استفاده از Report مدیریتی برای Prioritization و Review.

**نتیجه مورد انتظار:** مدیریت داده جاری و قابل‌ردیابی می‌بیند و محدودیت داده شفاف است.

## پرسونای ۹ — GRC Analyst با AI

**هدف:** افزایش سرعت تحلیل با AI بدون شکستن Boundary داده و Authority انسانی.

مسیر:
1. درخواست کمک روی داده/محتوای مجاز.
2. Permission Filtering قبل از RAG Retrieval.
3. Context بازیابی‌شده به‌عنوان Untrusted Data در نظر گرفته می‌شود.
4. Routing به Provider تنظیم‌شده OpenAI-compatible/Ollama/vLLM/Private.
5. AI Draft/Summary/Mapping/Remediation Suggestion تولید می‌کند.
6. خروجی Consequential قبل از تغییر Business State بازبینی می‌شود.

**نتیجه مورد انتظار:** AI سرعت و Consistency را بالا می‌برد بدون Autonomous Compliance Decision.

## سفرهای Post-v1

- Onboarding و Assurance شخص ثالث/Vendor در TPRM.
- Business Impact Analysis و Continuity Planning در BCM/BIA.
- Workflow Incident به Risk/Control/Remediation.
- Continuous Control Monitoring و Escalation.
- Review/Approval موبایل و PWA.
