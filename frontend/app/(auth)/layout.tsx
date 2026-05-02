export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex-1 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.png" alt="Vestige" width={64} height={64} className="h-16 w-16 rounded-xl" />
          <h1 className="text-2xl font-semibold tracking-tight">Vestige</h1>
        </div>
        {children}
      </div>
    </div>
  );
}
