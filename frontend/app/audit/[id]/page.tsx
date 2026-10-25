import { Suspense } from "react";
import AuditView from "@/components/AuditView";

// Cache Components: params and searchParams are request data, so they're read inside <Suspense>.
export default function AuditPage(props: PageProps<"/audit/[id]">) {
  return (
    <Suspense fallback={<main id="main" className="mx-auto w-full max-w-6xl px-4 py-8"><p className="text-lg">Loading the audit…</p></main>}>
      <AuditLoader params={props.params} searchParams={props.searchParams} />
    </Suspense>
  );
}

async function AuditLoader({
  params,
  searchParams,
}: Pick<PageProps<"/audit/[id]">, "params" | "searchParams">) {
  const { id } = await params;
  const query = await searchParams;
  return <AuditView id={id} replay={query.replay === "1"} print={query.print === "1"} />;
}
