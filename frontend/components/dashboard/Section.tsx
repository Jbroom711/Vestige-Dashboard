/**
 * Visual section wrapper used by the three dashboard rows. Just a heading
 * and a content slot — keeps the page file readable.
 */
export default function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <header className="flex items-baseline justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          {title}
        </h2>
        {subtitle ? (
          <span className="text-xs text-zinc-400">{subtitle}</span>
        ) : null}
      </header>
      {children}
    </section>
  );
}
