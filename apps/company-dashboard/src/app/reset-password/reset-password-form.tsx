"use client";

import { createBrowserClient } from "@supabase/ssr";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

interface Props {
  supabaseUrl: string;
  supabaseKey: string;
}

export function ResetPasswordForm({ supabaseUrl, supabaseKey }: Props) {
  const client = useMemo(
    () => createBrowserClient(supabaseUrl, supabaseKey),
    [supabaseKey, supabaseUrl],
  );
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState("Checking recovery link...");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;

    async function establishRecoverySession() {
      const fragment = new URLSearchParams(window.location.hash.slice(1));
      const accessToken = fragment.get("access_token");
      const refreshToken = fragment.get("refresh_token");
      const code = new URLSearchParams(window.location.search).get("code");

      let error: Error | null = null;
      if (accessToken && refreshToken) {
        const result = await client.auth.setSession({
          access_token: accessToken,
          refresh_token: refreshToken,
        });
        error = result.error;
      } else if (code) {
        const result = await client.auth.exchangeCodeForSession(code);
        error = result.error;
      } else {
        const result = await client.auth.getSession();
        error = result.error;
        if (!result.data.session) {
          error = new Error("No recovery session was found.");
        }
      }

      if (!active) return;
      window.history.replaceState({}, "", window.location.pathname);
      if (error) {
        setMessage("This reset link is invalid or has expired. Request a new one.");
        return;
      }
      setMessage("");
      setReady(true);
    }

    void establishRecoverySession();
    return () => {
      active = false;
    };
  }, [client]);

  async function updatePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") ?? "");
    const confirmation = String(form.get("confirmation") ?? "");

    if (password.length < 12) {
      setMessage("Use at least 12 characters.");
      return;
    }
    if (password !== confirmation) {
      setMessage("The passwords do not match.");
      return;
    }

    setSaving(true);
    const { error } = await client.auth.updateUser({ password });
    if (error) {
      setMessage(error.message);
      setSaving(false);
      return;
    }

    window.location.assign("/");
  }

  if (!ready) {
    return (
      <>
        <p className={`notice${message.startsWith("This") ? " notice--error" : ""}`}>
          {message}
        </p>
        {message.startsWith("This") ? (
          <Link className="auth-link" href="/forgot-password">
            Request another reset link
          </Link>
        ) : null}
      </>
    );
  }

  return (
    <form className="auth-form" onSubmit={updatePassword}>
      {message ? <p className="notice notice--error">{message}</p> : null}
      <label className="field">
        New password
        <input
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={12}
          required
        />
      </label>
      <label className="field">
        Confirm new password
        <input
          name="confirmation"
          type="password"
          autoComplete="new-password"
          minLength={12}
          required
        />
      </label>
      <button disabled={saving} type="submit">
        {saving ? "Updating..." : "Update password"}
      </button>
    </form>
  );
}
