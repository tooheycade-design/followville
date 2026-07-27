import { logoutAction } from "../actions";

export default function UnauthorizedPage() {
  return (
    <div className="auth-page">
      <section className="auth-panel">
        <p className="eyebrow">Access denied</p>
        <h1>Owner membership required</h1>
        <p>This account is signed in but is not an active Company OS owner.</p>
        <form action={logoutAction}>
          <button type="submit">Sign out</button>
        </form>
      </section>
    </div>
  );
}
