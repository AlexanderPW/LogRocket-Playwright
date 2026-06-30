import Link from "next/link";
import { FlowsExplorer } from "@/components/flows-explorer";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";

export default function FlowsPage() {
  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-zinc-50">Flows</h1>
          <p className="text-zinc-400 mt-2">
            Generated regression flows and their artifacts. Search and paginate when you have many flows.
          </p>
        </div>
        <Link href="/generate">
          <Button>Generate new flow</Button>
        </Link>
      </div>

      <FlowsExplorer />
    </div>
  );
}
