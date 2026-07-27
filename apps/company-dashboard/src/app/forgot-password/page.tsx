import Link from "next/link";

import { requestPasswordResetAction } from "../actions";

export default async function ForgotPasswordPage({
  searchParams,
}: {
  searchParams: Promise<{ sent?: string }>;
}) {
  const params = await searchParams;

  return (
    <div className="auth-page">
      <section className="auth-panel">
        <p className="eyebrow">Private operations</p>
        <h1>Reset password</h1>
        {params.sent === "1" ? (
          <>
            <p className="notice">
              Check your email for a password reset link. You can close this
              page after the email arrives.
            </p>
            <Link className="auth-link" href="/login">
              Return to sign in
            </Link>
          </>
        ) : (
          <>
            <p className="auth-help">
              Enter the email address on your Company OS owner account.
            </p>
            <form action={requestPasswordResetAction} className="auth-form">
              <label className="field">
                Email
                <input
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                />
              </label>
              <button type="submit">Send reset link</button>
              <Link className="auth-link" href="/login">
                Return to sign in
              </Link>
            </form>
          </>
        )}
      </section>
    </div>
  );
}
