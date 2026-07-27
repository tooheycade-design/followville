import { publicConfiguration } from "@/lib/supabase/server";

import { ResetPasswordForm } from "./reset-password-form";

export default function ResetPasswordPage() {
  const configuration = publicConfiguration();

  return (
    <div className="auth-page">
      <section className="auth-panel">
        <p className="eyebrow">Private operations</p>
        <h1>Choose a new password</h1>
        <ResetPasswordForm
          supabaseKey={configuration.key}
          supabaseUrl={configuration.url}
        />
      </section>
    </div>
  );
}
