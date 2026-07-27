import { loginAction } from "../actions";
import Link from "next/link";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string }>;
}) {
  const params = await searchParams;
  const next = params.next ?? "/";
  return (
    <div className="auth-page">
      <section className="auth-panel">
        <p className="eyebrow">Private operations</p>
        <h1>Owner sign in</h1>
        {params.error === "invalid_credentials" ? (
          <p className="notice notice--denied">Email or password was not accepted.</p>
        ) : null}
        <form action={loginAction} className="auth-form">
          <label className="field">
            Email
            <input name="email" type="email" autoComplete="email" required />
          </label>
          <label className="field">
            Password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          <input name="next" type="hidden" value={next} />
          <button type="submit">Sign in</button>
          <Link className="auth-link" href="/forgot-password">
            Forgot password?
          </Link>
        </form>
      </section>
    </div>
  );
}
