import ChangePasswordForm from "@/components/ChangePasswordForm";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export default async function AccountPage() {
  const supabase = await createSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Account</h1>
        <p className="text-sm text-zinc-500">
          Signed in as <span className="font-medium text-zinc-700 dark:text-zinc-300">{user?.email}</span>
        </p>
      </header>

      <section className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="text-base font-semibold">Change password</h2>
        <p className="mt-1 mb-4 text-sm text-zinc-500">
          Sets a new password on your Supabase account. The current session stays signed in.
        </p>
        <ChangePasswordForm />
      </section>
    </div>
  );
}
