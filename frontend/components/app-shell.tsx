"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  FlaskConical,
  FolderGit2,
  LayoutDashboard,
  Play,
  Settings,
  Sparkles,
  TestTube2,
  Wand2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { APP_NAME, APP_TAGLINE } from "@/lib/brand";

const nav = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/flows", label: "Flows", icon: FolderGit2 },
  { href: "/generate", label: "Generate", icon: Sparkles },
  { href: "/tests", label: "Tests", icon: TestTube2 },
  { href: "/record", label: "Record fixtures", icon: Play },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex">
      <aside className="w-64 shrink-0 border-r border-zinc-800 bg-zinc-900/80 flex flex-col">
        <div className="p-6 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-indigo-500/20 ring-1 ring-indigo-500/40 flex items-center justify-center">
              <FlaskConical className="h-5 w-5 text-indigo-400" />
            </div>
            <div>
              <div className="font-semibold text-zinc-50">{APP_NAME}</div>
              <div className="text-xs text-zinc-500">{APP_TAGLINE}</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {nav.map(({ href, label, icon: Icon }) => {
            const active =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                  active
                    ? "bg-indigo-500/15 text-indigo-200 ring-1 ring-indigo-500/30"
                    : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-zinc-800 text-xs text-zinc-500">
          <div className="flex items-center gap-2 text-zinc-400">
            <Wand2 className="h-3.5 w-3.5" />
            Streamlit dev UI still available via <code className="text-zinc-300">e2e-dashboard</code>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto p-8">{children}</div>
      </main>
    </div>
  );
}
