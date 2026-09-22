"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { API_BASE, persistSession } from "../../lib/api";
import { Button, FormField, Input, StatusMessage } from "../../components/ui";

type Step = "password" | "otp" | "enroll" | "enroll_verify" | "done";
type MessageTone = "info" | "success" | "danger";

export default function LoginPage() {
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState<MessageTone>("info");
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<Step>("password");
  const [challenge, setChallenge] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [secret, setSecret] = useState("");
  const [otpUri, setOtpUri] = useState("");

  function clearMessage() {
    setMessage("");
    setMessageTone("info");
  }

  function showError(error: unknown) {
    setMessage(error instanceof Error ? error.message : "خطای نامشخص");
    setMessageTone("danger");
  }

  async function completeLogin(body: { access?: string; refresh?: string; cookie_auth?: boolean }) {
    await persistSession(body);
    setStep("done");
    setMessage("ورود موفق بود. Tenant فعال نیز برای نشست انتخاب شد.");
    setMessageTone("success");
  }

  async function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    clearMessage();
    const data = new FormData(event.currentTarget);
    try {
      const response = await fetch(`${API_BASE}/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username: data.get("username"), password: data.get("password") }),
      });
      const body = await response.json();

      if (response.status === 202 && body.code === "MFA_REQUIRED") {
        setChallenge(body.challenge);
        setStep("otp");
        return;
      }

      if (response.status === 428 && body.code === "MFA_SETUP_REQUIRED") {
        const enroll = await fetch(`${API_BASE}/auth/mfa/enroll`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ challenge: body.challenge }),
        });
        const enrollment = await enroll.json();
        if (!enroll.ok) throw new Error(enrollment.message ?? "راه‌اندازی MFA ناموفق بود");
        setChallenge(enrollment.challenge);
        setDeviceId(enrollment.device_id);
        setSecret(enrollment.secret);
        setOtpUri(enrollment.otpauth_uri);
        setStep("enroll_verify");
        return;
      }

      if (!response.ok) throw new Error(body.message ?? body.detail ?? "ورود ناموفق بود");
      await completeLogin(body);
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  async function submitOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    clearMessage();
    const data = new FormData(event.currentTarget);
    try {
      const endpoint = step === "otp" ? "/auth/mfa/verify-login" : "/auth/mfa/enroll/verify";
      const payload: Record<string, unknown> = { challenge, otp: data.get("otp") };
      if (step === "enroll_verify") payload.device_id = deviceId;

      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.message ?? "کد تأیید معتبر نیست");
      await completeLogin(body);
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="loginPage">
      <div className="loginCard">
        <div className="brandMark large">G</div>
        <h1>ورود به GRC Platform</h1>

        {step === "password" && (
          <form className="stack" onSubmit={submitPassword}>
            <p>احراز هویت و MFA — GRC Platform</p>
            <FormField label="نام کاربری" required>
              <Input name="username" autoComplete="username" required />
            </FormField>
            <FormField label="رمز عبور" required>
              <Input name="password" type="password" autoComplete="current-password" required />
            </FormField>
            <Button type="submit" busy={loading}>ورود</Button>
          </form>
        )}

        {step === "otp" && (
          <form className="stack" onSubmit={submitOtp}>
            <p>کد شش‌رقمی برنامه Authenticator را وارد کنید.</p>
            <FormField label="کد MFA" required>
              <Input name="otp" inputMode="numeric" autoComplete="one-time-code" required dir="ltr" />
            </FormField>
            <Button type="submit" busy={loading}>تأیید و ورود</Button>
          </form>
        )}

        {step === "enroll_verify" && (
          <form className="stack" onSubmit={submitOtp}>
            <p>سازمان شما MFA را اجباری کرده است. Secret زیر را در Authenticator ثبت کنید و سپس کد را وارد کنید.</p>
            <code className="secretBox">{secret}</code>
            <details>
              <summary>نمایش URI فنی</summary>
              <small className="breakText">{otpUri}</small>
            </details>
            <FormField label="کد MFA" required>
              <Input name="otp" inputMode="numeric" autoComplete="one-time-code" required dir="ltr" />
            </FormField>
            <Button type="submit" busy={loading}>فعال‌سازی MFA و ورود</Button>
          </form>
        )}

        {step === "done" && (
          <Link className="uiButton uiButton--primary uiButton--md linkButton" href="/">
            ورود به داشبورد
          </Link>
        )}

        {message && <StatusMessage tone={messageTone}>{message}</StatusMessage>}
        <Link href="/">بازگشت</Link>
      </div>
    </main>
  );
}
