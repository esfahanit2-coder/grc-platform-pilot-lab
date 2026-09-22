import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

function classes(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  busy?: boolean;
};

export function Button({
  variant = "primary",
  size = "md",
  busy = false,
  className,
  disabled,
  type = "button",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      type={type}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={classes("uiButton", `uiButton--${variant}`, `uiButton--${size}`, className)}
    >
      {busy ? <span className="uiSpinner" aria-hidden="true" /> : null}
      <span>{children}</span>
    </button>
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={classes("uiControl", className)} />;
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={classes("uiControl", "uiSelect", className)} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={classes("uiControl", "uiTextarea", className)} />;
}

type FormFieldProps = {
  label: ReactNode;
  children: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  htmlFor?: string;
  required?: boolean;
  className?: string;
};

export function FormField({
  label,
  children,
  hint,
  error,
  htmlFor,
  required = false,
  className,
}: FormFieldProps) {
  return (
    <label className={classes("uiField", className)} htmlFor={htmlFor}>
      <span className="uiFieldLabel">
        {label}
        {required ? <span className="uiRequired" aria-hidden="true"> *</span> : null}
      </span>
      {children}
      {hint ? <small className="uiFieldHint">{hint}</small> : null}
      {error ? <small className="uiFieldError" role="alert">{error}</small> : null}
    </label>
  );
}

export type MessageTone = "info" | "success" | "warning" | "danger";

export function StatusMessage({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: MessageTone;
  title?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={classes("uiMessage", `uiMessage--${tone}`, className)} role={tone === "danger" ? "alert" : "status"}>
      {title ? <strong>{title}</strong> : null}
      <span>{children}</span>
    </div>
  );
}

export function Surface({
  children,
  className,
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return <section className={classes("uiSurface", padded && "uiSurface--padded", className)}>{children}</section>;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  leading,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  leading?: ReactNode;
}) {
  return (
    <header className="uiPageHeader">
      <div className="uiPageHeaderMain">
        {leading ? <div className="uiPageHeaderLeading">{leading}</div> : null}
        <div>
          {eyebrow ? <div className="uiEyebrow">{eyebrow}</div> : null}
          <h1>{title}</h1>
          {description ? <p>{description}</p> : null}
        </div>
      </div>
      {actions ? <div className="uiPageHeaderActions">{actions}</div> : null}
    </header>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="uiEmptyState">
      <strong>{title}</strong>
      {description ? <p>{description}</p> : null}
      {action ? <div className="uiEmptyStateAction">{action}</div> : null}
    </div>
  );
}

export function TechnicalText({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <span className={classes("uiTechnical", className)}>{children}</span>;
}
