import { redirect } from "next/navigation";

export default function Home() {
  // proxy.ts will send unauthenticated users to /login and pending users to /pending
  redirect("/dashboard");
}
