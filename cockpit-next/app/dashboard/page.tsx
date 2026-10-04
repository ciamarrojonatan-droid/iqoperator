"use client";

import { useEffect, useState } from "react";
import {
  Trophy,
  BarChart3,
  ShieldAlert,
  History,
  Layers,
  Sparkles,
  Radio,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { StatisticsCard7 } from "@/components/statistics-card-7";
import { EquityCurveChart } from "@/components/line-charts-9";
import { PerformanceGauge } from "@/components/performance-gauge";
import { SessionSummary } from "@/components/session-summary";
import { RiskPanel } from "@/components/risk-panel";
import { TradesFeed } from "@/components/trades-feed";
import { WinrateTrend } from "@/components/winrate-trend";
import { PayoutStats } from "@/components/payout-stats";
import { TradeTicket } from "@/components/trade-ticket";
import { AssetRanking } from "@/components/asset-ranking";
import { StrategyConfig } from "@/components/strategy-config";
import { DrawdownCard } from "@/components/drawdown-card";
import { BotHealthCard } from "@/components/bot-health-card";
import { TradesHistoryFull } from "@/components/trades-history-full";
import { EquityStats } from "@/components/equity-stats";
import { SignalDistribution } from "@/components/signal-distribution";
import { ProfitBars } from "@/components/profit-bars";
import { StreakTracker } from "@/components/streak-tracker";
import { StakeEvolution } from "@/components/stake-evolution";
import { GoalRing } from "@/components/goal-ring";
import { AlertsBanner } from "@/components/alerts-banner";
import { SessionReport } from "@/components/session-report";
import { PayoutScatter } from "@/components/payout-scatter";
import { Brand } from "@/components/brand/logo";
import { StatusPill } from "@/components/brand/status-pill";
import { SessionClock } from "@/components/brand/session-clock";
import { TickerTape } from "@/components/brand/ticker-tape";
import { SectionHeading } from "@/components/brand/section-heading";
import { AppSidebar } from "@/components/shell/app-sidebar";
import { CommandMenu, CommandMenuHint } from "@/components/shell/command-menu";
import { AudioToggle } from "@/components/audio-toggle";
import { SignalsHistory } from "@/components/signals-history";
import { playCallSound, playPutSound, getAudioEnabled } from "@/lib/audio-alerts";

type S = {
  trades: number;
  wins: number;
  winrate: number;
  profit: number;
  balance: string;
  byAsset: { asset: string; trades: number; wins: number; winrate: number; profit: number }[];
  last: any[];
};

type B = {
  last_tick: string;
  asset: string;
  balance: number;
  balance_type: string;
  strategy: string;
  profit_session: number;
} | null;

type TabKey = "desempenho" | "analise" | "sinais" | "risco" | "historico" | "todos";

export default function Dashboard() {
  const [s, setS] = useState<S>({
    trades: 0,
    wins: 0,
    winrate: 0,
    profit: 0,
    balance: "n/a",
    byAsset: [],
    last: [],
  });

  const [b, setB] = useState<B>(null);
  const [uptime, setUptime] = useState(0);
  const [msg, setMsg] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("desempenho");

  function handleNewSignal(sig: any) {
    if (getAudioEnabled() && sig?.status === "APPROVED") {
      if (sig.direction === "CALL") {
        playCallSound();
      } else if (sig.direction === "PUT") {
        playPutSound();
      }
    }
  }

  async function manual(sig: string) {
    setMsg("enviando...");
    try {
      const r = await fetch("/api/manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signal: sig }),
      })
        .then((x) => x.json())
        .catch(() => null);
      setMsg(r?.error ? String(r.error) : `sinal ${sig} enviado`);
      tick();
    } catch {
      setMsg("falha ao enviar sinal");
    }
  }

  async function tick() {
    const r = await fetch("/api/status").then((x) => x.json()).catch(() => null);
    if (r) setS(r);
    const hb = await fetch("/api/manual").then((x) => x.json()).catch(() => null);
    if (hb && !hb.error) setB(hb);
    const h = await fetch("/api/health").then((x) => x.json()).catch(() => null);
    if (h && typeof h.uptime === "number") setUptime(h.uptime);
  }

  useEffect(() => {
    tick();
    const i = setInterval(tick, 5000);
    return () => clearInterval(i);
  }, []);

  useEffect(() => {
    function activateTabAndScroll(targetId: string) {
      if (
        targetId === "desempenho" ||
        targetId === "analise" ||
        targetId === "sinais" ||
        targetId === "risco" ||
        targetId === "historico" ||
        targetId === "todos"
      ) {
        setActiveTab(targetId as TabKey);
        setTimeout(() => {
          const el = document.getElementById(targetId === "todos" ? "intelligence-hub" : targetId);
          if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        }, 60);
      } else {
        setTimeout(() => {
          const el = document.getElementById(targetId);
          if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        }, 60);
      }
    }

    function syncHash() {
      const rawHash = window.location.hash.replace("#", "");
      if (rawHash) {
        activateTabAndScroll(rawHash);
      }
    }

    function handleGlobalClick(e: MouseEvent) {
      const anchor = (e.target as HTMLElement).closest("a");
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (!href || !href.startsWith("#")) return;
      const targetHash = href.replace("#", "");
      if (targetHash) {
        activateTabAndScroll(targetHash);
      }
    }

    syncHash();
    window.addEventListener("hashchange", syncHash);
    document.addEventListener("click", handleGlobalClick);
    return () => {
      window.removeEventListener("hashchange", syncHash);
      document.removeEventListener("click", handleGlobalClick);
    };
  }, []);

  function handleTabChange(nextTab: TabKey) {
    setActiveTab(nextTab);
    window.history.replaceState(null, "", `#${nextTab}`);
  }

  const alive = b && Date.now() - new Date(b.last_tick).getTime() < 45000;
  const pillStatus = !b ? "offline" : alive ? "online" : "degraded";
  const pillLabel = !b ? "aguardando bot" : alive ? "bot vivo" : "sem heartbeat";

  const tapeItems = [
    { symbol: b?.asset || "BTCUSD", price: `saldo ${b?.balance ?? s.balance}` },
    {
      symbol: "SESSÃO",
      price: `${s.profit >= 0 ? "+" : ""}${s.profit.toFixed(2)}`,
      chg: s.trades ? s.winrate * 100 - 53.48 : 0,
    },
    { symbol: "WINRATE", price: `${(s.winrate * 100).toFixed(1)}%`, chg: s.trades ? s.winrate * 100 - 53.48 : 0 },
    { symbol: "ESTRATÉGIA", price: b?.strategy || "donchian_fade" },
    { symbol: "PAYOUT MÍN", price: "≥ 0.80" },
    { symbol: "TRADES", price: String(s.trades) },
  ];

  // Prepare chart data from last trades equity in chronological order
  const chartData = [...s.last].reverse().map((t: any, i: number) => ({
    trade: i + 1,
    time: t.time || t.timestamp || "",
    profit: parseFloat(t.profit || 0),
    balance: parseFloat(t.balance || s.balance || 0),
  }));

  const tabs: Array<{ id: TabKey; label: string; icon: any; count?: string | number }> = [
    {
      id: "desempenho",
      label: "Desempenho & Metas",
      icon: Trophy,
      count: s.trades ? `${(s.winrate * 100).toFixed(0)}%` : undefined,
    },
    {
      id: "analise",
      label: "Deep-Dive & Ativos",
      icon: BarChart3,
      count: s.byAsset.length ? `${s.byAsset.length} ativos` : undefined,
    },
    {
      id: "sinais",
      label: "Radar de Sinais",
      icon: Radio,
      count: "Tempo Real",
    },
    {
      id: "risco",
      label: "Risco & Auditoria",
      icon: ShieldAlert,
    },
    {
      id: "historico",
      label: "Histórico Ledger",
      icon: History,
      count: s.last.length ? s.last.length : undefined,
    },
    {
      id: "todos",
      label: "Visão Consolidada",
      icon: Layers,
    },
  ];

  return (
    <div className="relative z-10 flex">
      <AppSidebar alive={!!alive} />
      <div className="flex-1 min-w-0">
        <main className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
          {/* Header */}
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <Brand />
              <p className="text-muted text-sm mt-2">
                PRACTICE · donchian_fade · payout ≥0.80{" "}
                {b ? `· ${b.asset} · saldo ${b.balance} · ${b.balance_type}` : ""}
              </p>
              {alive && b && (
                <p className="text-xs mt-1 text-muted">
                  último tick {new Date(b.last_tick).toLocaleTimeString("pt-BR")}
                </p>
              )}
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <AudioToggle />
              <SessionClock />
              <StatusPill status={pillStatus} label={pillLabel} />
              <CommandMenuHint />
            </div>
          </div>
          {msg && <p className="text-xs text-muted">{msg}</p>}

          {/* Ticker Tape */}
          <div className="-mx-4 sm:-mx-6">
            <TickerTape items={tapeItems} />
          </div>

          {/* Alerts Banner */}
          <div>
            <AlertsBanner trades={s.last} winrate={s.winrate} alive={!!alive} />
          </div>

          {/* 1. Hero Bento Viewport (Upper screen / primary viewport) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 xl:gap-6 items-start">
            {/* Analytical Area (8 cols on desktop lg/xl) */}
            <div className="lg:col-span-8 flex flex-col gap-5 min-w-0">
              {/* 4 KPI Cards */}
              <div id="visao-geral" className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4 gap-3.5 scroll-mt-6">
                <StatisticsCard7 title="Total Trades" value={s.trades} subtitle="Sinais gerados" />
                <StatisticsCard7 title="Winrate" value={s.winrate} subtitle="Percentual de acertos" metric="winrate" />
                <StatisticsCard7 title="Lucro Sessão" value={s.profit} subtitle="Em R$" metric="profit" />
                <StatisticsCard7 title="Saldo Atual" value={s.balance} subtitle="Conta IQ Option" metric="balance" />
              </div>

              {/* Equity Curve Chart */}
              <div id="equity" className="scroll-mt-6">
                <EquityCurveChart data={chartData} />
              </div>

              {/* Winrate / Payout / Streak Tracker Core Bento Row */}
              <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3 gap-4">
                <WinrateTrend trades={s.last} />
                <PayoutStats trades={s.last} />
                <StreakTracker trades={s.last} />
              </div>
            </div>

            {/* Command Rail (4 cols on desktop lg/xl) */}
            <div id="operacao" className="lg:col-span-4 flex flex-col gap-4 scroll-mt-6 min-w-0">
              <TradeTicket onExecuted={tick} />
              <BotHealthCard bot={b} uptime={uptime} />
              <StrategyConfig bot={b} />
            </div>
          </div>

          {/* 2. Structured Intelligence / Audit Area */}
          <div id="intelligence-hub" className="space-y-5 pt-2 scroll-mt-6">
            {/* Area Header & Segmented Tab Controls */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-border/60 pb-4">
              <div>
                <h2 className="text-base font-semibold text-foreground tracking-tight flex items-center gap-2">
                  <Sparkles size={16} className="text-accent" />
                  Centro de Inteligência & Auditoria
                </h2>
                <p className="text-xs text-muted mt-0.5">
                  Análise aprofundada de performance, risco, dispersão e ledger da sessão
                </p>
              </div>

              {/* Tab Navigation Pill Bar */}
              <div className="flex items-center gap-1.5 p-1 bg-surface border border-border rounded-lg overflow-x-auto max-w-full">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => handleTabChange(tab.id)}
                      className={cn(
                        "flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all whitespace-nowrap",
                        isActive
                          ? "bg-accent text-white shadow-sm font-semibold"
                          : "text-muted hover:text-foreground hover:bg-surface-elevated"
                      )}
                    >
                      <Icon size={13} className={cn(isActive ? "text-white" : "text-muted")} />
                      <span>{tab.label}</span>
                      {tab.count !== undefined && (
                        <span
                          className={cn(
                            "px-1.5 py-0.5 rounded-full text-[10px] font-mono",
                            isActive
                              ? "bg-white/20 text-white"
                              : "bg-surface-elevated text-muted border border-border"
                          )}
                        >
                          {tab.count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Tab 1: Desempenho & Metas */}
            {(activeTab === "desempenho" || activeTab === "todos") && (
              <div id="desempenho" className="scroll-mt-6 flex flex-col gap-4">
                {activeTab === "todos" && (
                  <SectionHeading
                    icon={Trophy}
                    title="Desempenho & Metas"
                    hint="Resumo da sessão, taxa de acerto e metas financeiras"
                  />
                )}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <PerformanceGauge wins={s.wins} trades={s.trades} />
                  <SessionSummary bot={b} uptime={uptime} />
                  <GoalRing session={s.profit} />
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <DrawdownCard trades={s.last} />
                  <EquityStats trades={s.last} />
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <ProfitBars trades={s.last} />
                  <SignalDistribution trades={s.last} />
                </div>
              </div>
            )}

            {/* Tab 2: Deep-Dive & Ativos */}
            {(activeTab === "analise" || activeTab === "todos") && (
              <div id="analise" className="scroll-mt-6 flex flex-col gap-4">
                {activeTab === "todos" && (
                  <SectionHeading
                    icon={BarChart3}
                    title="Deep-Dive & Ativos"
                    hint="Ranking comparativo por ativo, dispersão de payout e stakes"
                  />
                )}
                <AssetRanking byAsset={s.byAsset} />
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <PayoutScatter trades={s.last} />
                  <StakeEvolution trades={s.last} />
                </div>
              </div>
            )}

            {/* Tab: Radar de Sinais */}
            <div
              id="sinais"
              className={cn(
                "scroll-mt-6 flex flex-col gap-4",
                activeTab !== "sinais" && activeTab !== "todos" && "hidden"
              )}
            >
              {activeTab === "todos" && (
                <SectionHeading
                  icon={Radio}
                  title="Radar de Sinais & Confluências"
                  hint="Auditoria em tempo real de confluências MHI e classificação XGBoost nos 30 ativos"
                />
              )}
              <SignalsHistory onNewSignal={handleNewSignal} />
            </div>

            {/* Tab 3: Risco & Auditoria */}
            {(activeTab === "risco" || activeTab === "todos") && (
              <div id="risco" className="scroll-mt-6 flex flex-col gap-4">
                {activeTab === "todos" && (
                  <SectionHeading
                    icon={ShieldAlert}
                    title="Gestão de Risco & Auditoria"
                    hint="Exposição de banca, Critério de Kelly, feed recente e relatório"
                  />
                )}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <RiskPanel last={s.last} balance={s.balance} />
                  <TradesFeed trades={s.last.slice(0, 8)} />
                </div>
                <SessionReport
                  trades={s.trades}
                  wins={s.wins}
                  winrate={s.winrate}
                  profit={s.profit}
                  balance={s.balance}
                  asset={b?.asset}
                  strategy={b?.strategy}
                  uptime={uptime}
                />
              </div>
            )}

            {/* Tab 4: Histórico Ledger */}
            {(activeTab === "historico" || activeTab === "todos") && (
              <div id="historico" className="scroll-mt-6 flex flex-col gap-4">
                {activeTab === "todos" && (
                  <SectionHeading
                    icon={History}
                    title="Histórico de Ordens"
                    hint="Auditoria completa, filtros avançados e exportação de dados"
                  />
                )}
                <TradesHistoryFull trades={s.last} />
              </div>
            )}
          </div>
        </main>
      </div>
      <CommandMenu onManual={manual} />
    </div>
  );
}