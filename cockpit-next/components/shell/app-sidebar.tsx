"use client";

import * as React from "react";
import {
  LayoutDashboard,
  ChartCandlestick,
  Trophy,
  ShieldAlert,
  Zap,
  History,
  BarChart3,
  ChevronsLeft,
  ChevronsRight,
  Radio,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Brand, LogoMark } from "@/components/brand/logo";

const NAV = [
  { href: "#visao-geral", label: "Visão geral", Icon: LayoutDashboard },
  { href: "#equity", label: "Equity", Icon: ChartCandlestick },
  { href: "#operacao", label: "Operação", Icon: Zap },
  { href: "#desempenho", label: "Desempenho", Icon: Trophy },
  { href: "#analise", label: "Ativos", Icon: BarChart3 },
  { href: "#sinais", label: "Radar de Sinais", Icon: Radio },
  { href: "#risco", label: "Risco", Icon: ShieldAlert },
  { href: "#historico", label: "Histórico", Icon: History },
] as const;

export function AppSidebar({ alive }: { alive: boolean }) {
  const [collapsed, setCollapsed] = React.useState(false);

  return (
    <aside
      className={cn(
        "hidden lg:flex flex-col shrink-0 sticky top-0 h-screen border-r border-border bg-[#0B0E14]/90 backdrop-blur transition-all duration-300",
        collapsed ? "w-[72px]" : "w-[240px]"
      )}
    >
      {/* Topo */}
      <div
        className={cn(
          "flex items-center border-b border-border/60",
          collapsed ? "justify-center px-2 py-5" : "px-5 py-5"
        )}
      >
        {collapsed ? <LogoMark size={32} /> : <Brand compact />}
      </div>

      {/* Nav */}
      <nav className={cn("flex-1 py-4", collapsed ? "px-2" : "px-3")}>
        <ul className="flex flex-col gap-1">
          {NAV.map(({ href, label, Icon }) => (
            <li key={href}>
              <a
                href={href}
                title={collapsed ? label : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted transition-colors hover:bg-muted/10 hover:text-foreground",
                  collapsed && "justify-center px-0"
                )}
              >
                <Icon className="h-5 w-5 shrink-0" />
                {!collapsed && <span className="truncate">{label}</span>}
              </a>
            </li>
          ))}
        </ul>

        {/* Colapsar */}
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          title={collapsed ? "Expandir menu" : "Recolher menu"}
          className={cn(
            "mt-4 flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-muted transition-colors hover:bg-muted/10 hover:text-foreground",
            collapsed ? "justify-center px-0 w-full" : "w-full"
          )}
        >
          {collapsed ? (
            <ChevronsRight className="h-4 w-4 shrink-0" />
          ) : (
            <>
              <ChevronsLeft className="h-4 w-4 shrink-0" />
              <span>Recolher</span>
            </>
          )}
        </button>
      </nav>

      {/* Footer */}
      <div className="border-t border-border/60 p-4">
        <div
          className={cn(
            "flex items-center gap-2.5 rounded-lg border border-border bg-[#151A23] px-3 py-2.5",
            collapsed && "justify-center px-0"
          )}
          title={alive ? "BOT VIVO" : "OFFLINE"}
        >
          <span className="relative flex h-2.5 w-2.5 shrink-0">
            {alive && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#3DD68C] opacity-60" />
            )}
            <span
              className={cn(
                "relative inline-flex h-2.5 w-2.5 rounded-full",
                alive ? "bg-[#3DD68C]" : "bg-muted"
              )}
            />
          </span>
          {!collapsed && (
            <span
              className={cn(
                "text-xs font-bold tracking-wider",
                alive ? "text-success" : "text-muted"
              )}
            >
              {alive ? "BOT VIVO" : "OFFLINE"}
            </span>
          )}
        </div>
        {!collapsed && (
          <p className="mt-3 px-1 text-[11px] font-medium tracking-wide text-muted">
            v1.0 microfactx
          </p>
        )}
      </div>
    </aside>
  );
}
