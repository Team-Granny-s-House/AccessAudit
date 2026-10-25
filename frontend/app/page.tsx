import AuditForm from "@/components/AuditForm";
import RecentAudits from "@/components/RecentAudits";

export default function Home() {
  return (
    <main id="main" className="mx-auto w-full max-w-3xl space-y-10 px-4 py-8">
      <section aria-labelledby="page-title" className="space-y-3">
        <h1 id="page-title" className="text-3xl font-bold text-navy">
          Can a disabled user finish the task?
        </h1>
        <p className="text-lg">
          Page scanners count code errors. AccessAudit tries the real task with only a keyboard, listens to what a
          screen reader would say, and shows exactly where it gets stuck.
        </p>
      </section>

      <section aria-labelledby="new-audit">
        <h2 id="new-audit" className="mb-3 text-xl font-bold text-navy">
          New audit
        </h2>
        <AuditForm />
      </section>

      <section aria-labelledby="recent">
        <h2 id="recent" className="mb-3 text-xl font-bold text-navy">
          Recent audits
        </h2>
        <RecentAudits />
      </section>
    </main>
  );
}
