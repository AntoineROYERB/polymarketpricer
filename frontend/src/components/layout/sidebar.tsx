"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

const navItems = [
  { href: "/leaderboard", label: "Leaderboard", icon: "⊞" },
  { href: "/feed", label: "Feed", icon: "⌖" },
  { href: "/markets", label: "Markets", icon: "⛁" },
  { href: "/follow", label: "Follow", icon: "⟡" },
  { href: "/portfolio", label: "Portfolio", icon: "⛃" },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const { clearApiKey } = useAuth();

  return (
    <aside
      className={cn(
        "flex flex-col bg-surface border-r border-border transition-all duration-200 h-screen sticky top-0",
        collapsed ? "w-16" : "w-56",
      )}
    >
      <div className={cn("flex items-center h-14 border-b border-border", collapsed ? "justify-center px-0" : "px-4")}>
        {!collapsed && (
          <span className="font-heading text-accent-amber tracking-widest text-sm uppercase">Edge Terminal</span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={cn("text-text-muted hover:text-text-primary transition-colors text-xs", collapsed ? "mt-2" : "ml-auto")}
        >
          {collapsed ? "→" : "←"}
        </button>
      </div>

      <nav className="flex-1 py-4 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 py-2 text-sm transition-all duration-150 border-l-2",
                isActive
                  ? "border-accent-amber bg-surface-hover text-text-primary"
                  : "border-transparent text-text-secondary hover:text-text-primary hover:bg-surface-hover",
                collapsed ? "justify-center px-0" : "px-4",
              )}
            >
              <span className="text-base w-5 text-center">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border pt-3 pb-4 space-y-1">
        <div className={cn("flex items-center gap-2 text-xs text-text-muted", collapsed ? "justify-center" : "px-4")}>
          <span className="w-1.5 h-1.5 rounded-full bg-accent-amber" />
          {!collapsed && <span>API Key Set</span>}
        </div>
        {!collapsed && (
          <button onClick={clearApiKey} className="w-full text-left px-4 py-1.5 text-xs text-text-muted hover:text-text-primary transition-colors">
            Logout
          </button>
        )}
      </div>
    </aside>
  );
}
