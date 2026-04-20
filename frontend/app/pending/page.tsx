import { createSupabaseServerClient } from "@/lib/supabase/server";
import SignOutButton from "@/components/SignOutButton";

export default async function PendingPage() {
  const supabase = await createSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <div className="flex-1 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm space-y-6 rounded-xl border border-zinc-200 bg-white p-6 text-center shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h1 className="text-xl font-semibold">Waiting for approval</h1>
        <p className="text-sm text-zinc-500">
          Your account{user?.email ? ` (${user.email})` : ""} is pending admin approval. You'll be
          able to sign in to the dashboard once it's granted.
        </p>
        <SignOutButton />
      </div>
    </div>
  );
}
