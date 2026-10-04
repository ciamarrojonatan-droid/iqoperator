"use client";

import * as React from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import {
  LayoutDashboard,
  ChartCandlestick,
  Trophy,
  ShieldAlert,
  Zap,
  History,
  BarChart3,
  Radio,
  ArrowUpRight,
  ArrowDownRight,
  Copy,
  RefreshCw,
  Search,
  CornerDownLeft,
} from "lucide-react";
import { cn } from "@/lib/utils";

type Sig = "call" | "put";

type NavItem = {
  label: string;
  hash: string;
  icon: React.ComponentType<{ className?: string }>;
};

const NAV_ITEMS: NavItem[] = [
  { label: "Visão geral", hash: "#visao-geral", icon: LayoutDashboard },
  { label: "Equity", hash: "#equity", icon: ChartCandlestick },
  { label: "Operação", hash: "#operacao", icon: Zap },
  { label: "Desempenho", hash: "#desempenho", icon: Trophy },
  { label: "Ativos & Deep-Dive", hash: "#analise", icon: BarChart3 },
  { label: "Radar de Sinais", hash: "#sinais", icon: Radio },
  { label: "Risco", hash: "#risco", icon: ShieldAlert },
  { label: "Histórico", hash: "#historico", icon: History },
];

function goTo(hash: string) {
  if (typeof window !== "undefined") {
    if (window.location.hash === hash) {
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    } else {
      window.location.hash = hash;
    }
    setTimeout(() => {
      document.querySelector(hash)?.scrollIntoView({ behavior: "smooth" });
    }, 60);
  }
}

async function buildSessionSummary(): Promise<string> {
  try {
    const res = await fetch("/api/status", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const lines: string[] = ["IQOperator — resumo da sessão"];
    const push = (k: string, v: unknown) => {
      if (v !== undefined && v !== null && v !== "") lines.push(`${k}: ${String(v)}`);
    };
    if (typeof data === "object" && data !== null) {
      for (const [k, v] of Object.entries(data)) {
        push(k, typeof v === "object" ? JSON.stringify(v) : v);
      }
    } else {
      lines.push(String(data));
    }
    lines.push(`Gerado em: ${new Date().toLocaleString("pt-BR")}`);
    return lines.join("\n");
  } catch (err) {
    return `IQOperator — resumo da sessão\nFalha ao buscar /api/status: ${err instanceof Error ? err.message : String(err)}\nGerado em: ${new Date().toLocaleString("pt-BR")}`;
  }
}

export function CommandMenuHint() {
  return (
    <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border border-border bg-surface px-1.5 font-mono text-[10px] font-medium text-muted opacity-100">
      <span className="text-xs">⌘</span>K
    </kbd>
  );
}

export function CommandMenu({ onManual }: { onManual: (sig: Sig) => void }) {
  const [open, setOpen] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const run = React.useCallback((fn: () => void) => {
    setOpen(false);
    fn();
  }, []);

  const handleCopy = React.useCallback(async () => {
    const text = await buildSessionSummary();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }, []);

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content
          className="fixed left-1/2 top-[20vh] z-50 w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-surface shadow-2xl outline-none"
          onEscapeKeyDown={() => setOpen(false)}
        >
          <Dialog.Title className="sr-only">Menu de comandos</Dialog.Title>
          <Command
            label="Menu de comandos"
            className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-2 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-muted"
          >
            <div className="flex items-center gap-2 border-b border-border px-3">
              <Search className="h-4 w-4 shrink-0 text-muted" />
              <Command.Input
                placeholder="Buscar comando ou seção…"
                className="h-12 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted"
              />
              <kbd className="hidden items-center gap-1 rounded border border-border bg-surface px-1.5 py-0.5 font-mono text-[10px] text-muted sm:inline-flex">
                <CornerDownLeft className="h-3 w-3" />
              </kbd>
            </div>

            <Command.List className="max-h-[320px] overflow-y-auto p-2">
              <Command.Empty className="py-6 text-center text-sm text-muted">
                Nenhum comando encontrado.
              </Command.Empty>

              <Command.Group heading="Navegar">
                {NAV_ITEMS.map((item) => (
                  <Command.Item
                    key={item.hash}
                    value={item.label}
                    onSelect={() => run(() => goTo(item.hash))}
                    className="flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-foreground aria-selected:bg-white/5 data-[selected=true]:bg-white/5"
                  >
                    <item.icon className="h-4 w-4 text-muted" />
                    <span>{item.label}</span>
                    <span className="ml-auto font-mono text-[10px] text-muted">{item.hash}</span>
                  </Command.Item>
                ))}
              </Command.Group>

              <Command.Group heading="Operação">
                <Command.Item
                  value="Enviar CALL manual"
                  onSelect={() => run(() => onManual("call"))}
                  className="flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-foreground aria-selected:bg-white/5 data-[selected=true]:bg-white/5"
                >
                  <span className="flex h-7 w-7 items-center justify-center rounded-md border border-emerald-500/30 bg-emerald-500/10">
                    <ArrowUpRight className="h-4 w-4 text-emerald-400" />
                  </span>
                  <span>Enviar CALL manual</span>
                </Command.Item>
                <Command.Item
                  value="Enviar PUT manual"
                  onSelect={() => run(() => onManual("put"))}
                  className="flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-foreground aria-selected:bg-white/5 data-[selected=true]:bg-white/5"
                >
                  <span className="flex h-7 w-7 items-center justify-center rounded-md border border-rose-500/30 bg-rose-500/10">
                    <ArrowDownRight className="h-4 w-4 text-rose-400" />
                  </span>
                  <span>Enviar PUT manual</span>
                </Command.Item>
              </Command.Group>

              <Command.Group heading="Sistema">
                <Command.Item
                  value="Copiar resumo da sessão"
                  onSelect={() => run(handleCopy)}
                  className="flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-foreground aria-selected:bg-white/5 data-[selected=true]:bg-white/5"
                >
                  <Copy className="h-4 w-4 text-muted" />
                  <span>{copied ? "Resumo copiado!" : "Copiar resumo da sessão"}</span>
                </Command.Item>
                <Command.Item
                  value="Recarregar dados"
                  onSelect={() => run(() => location.reload())}
                  className={cn(
                    "flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-foreground",
                    "aria-selected:bg-white/5 data-[selected=true]:bg-white/5"
                  )}
                >
                  <RefreshCw className="h-4 w-4 text-muted" />
                  <span>Recarregar dados</span>
                </Command.Item>
              </Command.Group>
            </Command.List>

            <div className="flex items-center gap-4 border-t border-border px-4 py-2.5 text-[11px] text-muted">
              <span className="flex items-center gap-1.5">
                <kbd className="rounded border border-border bg-surface px-1 font-mono">↑↓</kbd>
                navegar
              </span>
              <span className="flex items-center gap-1.5">
                <kbd className="rounded border border-border bg-surface px-1 font-mono">↵</kbd>
                executar
              </span>
              <span className="flex items-center gap-1.5">
                <kbd className="rounded border border-border bg-surface px-1 font-mono">esc</kbd>
                fechar
              </span>
            </div>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
