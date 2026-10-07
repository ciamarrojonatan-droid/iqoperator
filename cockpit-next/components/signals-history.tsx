"use client";

import React, { useState, useEffect } from "react";
import {
  Radio,
  Filter,
  CheckCircle2,
  XCircle,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Clock,
  Layers,
  Percent,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";
export type SignalRecord = {
  id: string;
  time: string;
  timestamp: number;
  asset: string;
  direction: "CALL" | "PUT";
  status: "APPROVED" | "BLOCKED";
  prob: number | null;
  threshold: number;
  payout: number;
  executed: boolean;
  order_id?: string | null;
  details?: string;
  profit?: number | null;
};

export function SignalsHistory({
  className,
  onNewSignal,
}: {
  className?: string;
  onNewSignal?: (signal: SignalRecord) => void;
}) {
  const [signals, setSignals] = useState<SignalRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [approvedCount, setApprovedCount] = useState(0);
  const [blockedCount, setBlockedCount] = useState(0);
  const [executedCount, setExecutedCount] = useState(0);
  const [winCount, setWinCount] = useState(0);
  const [lossCount, setLossCount] = useState(0);
  const [assetsList, setAssetsList] = useState<string[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<string>("ALL");
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastSeenId, setLastSeenId] = useState<string | null>(null);

  async function fetchSignals() {
    try {
      const params = new URLSearchParams();
      if (selectedAsset !== "ALL") params.set("asset", selectedAsset);
      if (selectedStatus !== "ALL") params.set("status", selectedStatus);
      params.set("limit", "150");

      const res = await fetch(`/api/signals?${params.toString()}`);
      if (!res.ok) return;
      const data = await res.json();

      setTotal(data.total || 0);
      setApprovedCount(data.approved_count || 0);
      setBlockedCount(data.blocked_count || 0);
      setExecutedCount(data.executed_count || 0);
      setWinCount(data.win_count || 0);
      setLossCount(data.loss_count || 0);
      if (data.assets?.length) setAssetsList(data.assets);

      const incoming: SignalRecord[] = data.signals || [];
      setSignals(incoming);

      // Detect new signal for sound alert callback
      if (incoming.length > 0) {
        const newest = incoming[0];
        if (lastSeenId && newest.id !== lastSeenId && newest.status === "APPROVED") {
          if (onNewSignal) onNewSignal(newest);
        }
        setLastSeenId(newest.id);
      }
    } catch (e) {
      console.warn("fetchSignals error:", e);
    }
  }

  useEffect(() => {
    fetchSignals();
    const interval = setInterval(fetchSignals, 4000);
    return () => clearInterval(interval);
  }, [selectedAsset, selectedStatus]);

  // Client-side text filter
  const displayedSignals = searchQuery
    ? signals.filter((s) =>
        s.asset.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.direction.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (s.details && s.details.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : signals;

  const approvalRate = total > 0 ? (approvedCount / total) * 100 : 0;
  const latestSignal = signals[0];

  return (
    <div className={cn("bg-surface border border-border rounded-xl p-4 sm:p-5 flex flex-col gap-4 shadow-sm", className)}>
      {/* Header and Quick Stats */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/60 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-accent/10 rounded-lg border border-accent/20 text-accent">
            <Radio size={18} className="animate-pulse" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              Radar & Histórico de Sinais em Tempo Real
              <span className="text-[11px] font-normal px-2 py-0.5 rounded-full bg-surface-elevated text-muted border border-border">
                {displayedSignals.length} registros
              </span>
            </h3>
            <p className="text-xs text-muted">
              Auditoria de detecção de padrões MHI com classificação preditiva do modelo XGBoost
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => {
            setLoading(true);
            fetchSignals().finally(() => setLoading(false));
          }}
          className="self-start sm:self-auto flex items-center gap-1.5 px-2.5 py-1 text-xs text-muted hover:text-foreground bg-surface-elevated border border-border rounded-md transition-colors"
        >
          <RefreshCw size={12} className={cn(loading && "animate-spin")} />
          Atualizar
        </button>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="bg-surface-elevated/70 border border-border rounded-lg p-3">
          <span className="text-[11px] text-muted flex items-center gap-1">
            <Layers size={12} /> Total de Sinais
          </span>
          <p className="text-lg font-bold text-foreground mt-0.5">{total}</p>
        </div>

        <div className="bg-surface-elevated/70 border border-border rounded-lg p-3">
          <span className="text-[11px] text-muted flex items-center gap-1">
            <CheckCircle2 size={12} className="text-emerald-400" /> Aprovados (IA)
          </span>
          <div className="flex items-baseline gap-2 mt-0.5">
            <p className="text-lg font-bold text-emerald-400">{approvedCount}</p>
            <span className="text-xs text-emerald-400/80 font-mono">
              ({approvalRate.toFixed(1)}%)
            </span>
          </div>
        </div>

        <div className="bg-surface-elevated/70 border border-border rounded-lg p-3">
          <span className="text-[11px] text-muted flex items-center gap-1">
            <XCircle size={12} className="text-amber-400" /> Bloqueados (IA)
          </span>
          <div className="flex items-baseline gap-2 mt-0.5">
            <p className="text-lg font-bold text-amber-400">{blockedCount}</p>
            <span className="text-xs text-muted font-mono">
              ({(100 - approvalRate).toFixed(1)}%)
            </span>
          </div>
        </div>

        <div className="bg-surface-elevated/70 border border-border rounded-lg p-3">
          <span className="text-[11px] text-muted flex items-center gap-1">
            <TrendingUp size={12} className="text-blue-400" /> Executados
          </span>
          <div className="flex items-baseline gap-2 mt-0.5">
            <p className="text-lg font-bold text-blue-400">{executedCount}</p>
            {executedCount > 0 && (
              <span className="text-[10px] flex items-center gap-1 font-mono">
                <span className="text-emerald-400">{winCount}W</span>
                <span className="text-muted">/</span>
                <span className="text-rose-400">{lossCount}L</span>
              </span>
            )}
          </div>
        </div>

        <div className="bg-surface-elevated/70 border border-border rounded-lg p-3">
          <span className="text-[11px] text-muted flex items-center gap-1">
            <Clock size={12} /> Último Sinal
          </span>
          {latestSignal ? (
            <div className="flex items-center gap-1.5 mt-0.5">
              <span
                className={cn(
                  "px-1.5 py-0.5 rounded text-[11px] font-bold uppercase",
                  latestSignal.direction === "CALL"
                    ? "bg-emerald-500/15 text-emerald-400"
                    : "bg-rose-500/15 text-rose-400"
                )}
              >
                {latestSignal.direction}
              </span>
              <span className="text-xs font-semibold text-foreground truncate max-w-[80px]">
                {latestSignal.asset}
              </span>
              <span className="text-[10px] text-muted font-mono ml-auto">
                {latestSignal.time.split(" ")[1] || ""}
              </span>
            </div>
          ) : (
            <p className="text-xs text-muted mt-1">Aguardando...</p>
          )}
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col md:flex-row gap-2.5 items-stretch md:items-center justify-between">
        {/* Status Pills */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 md:pb-0 scrollbar-none">
          {[
            { id: "ALL", label: "Todos" },
            { id: "APPROVED", label: "Aprovados (IA)", color: "text-emerald-400" },
            { id: "BLOCKED", label: "Bloqueados", color: "text-amber-400" },
            { id: "CALL", label: "CALL ↑", color: "text-emerald-400" },
            { id: "PUT", label: "PUT ↓", color: "text-rose-400" },
          ].map((pill) => (
            <button
              key={pill.id}
              onClick={() => setSelectedStatus(pill.id)}
              className={cn(
                "px-2.5 py-1 rounded-md text-xs font-medium transition-all whitespace-nowrap",
                selectedStatus === pill.id
                  ? "bg-accent text-white shadow-sm font-semibold"
                  : "bg-surface-elevated text-muted hover:text-foreground border border-border"
              )}
            >
              <span className={cn(selectedStatus === pill.id ? "text-white" : pill.color)}>
                {pill.label}
              </span>
            </button>
          ))}
        </div>

        {/* Asset Selector & Search Filter */}
        <div className="flex items-center gap-2">
          {/* Asset Dropdown */}
          <div className="relative">
            <select
              value={selectedAsset}
              onChange={(e) => setSelectedAsset(e.target.value)}
              aria-label="Filtrar por ativo"
              className="px-2.5 py-1 text-xs bg-surface-elevated border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-accent appearance-none pr-7 cursor-pointer"
            >
              <option value="ALL">Todos os 30 Ativos</option>
              {assetsList.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
            <Filter size={10} className="absolute right-2 top-2.5 text-muted pointer-events-none" />
          </div>

          {/* Quick Search Input */}
          <div className="relative flex-1 md:w-40">
            <input
              type="text"
              placeholder="Buscar..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-7 pr-2.5 py-1 text-xs bg-surface-elevated border border-border rounded-md text-foreground placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-accent"
            />
            <Search size={11} className="absolute left-2.5 top-2 text-muted" />
          </div>
        </div>
      </div>

      {/* Signals Feed List / Table */}
      <div className="overflow-x-auto border border-border/80 rounded-lg">
        {displayedSignals.length === 0 ? (
          <div className="p-8 text-center text-muted text-xs flex flex-col items-center justify-center gap-2">
            <Radio size={24} className="text-muted/40" />
            <p>Nenhum sinal encontrado para os filtros selecionados.</p>
            <span className="text-[11px] text-muted/60">
              O robô escaneia os ativos a cada ciclo de 5s procurando confluências MHI.
            </span>
          </div>
        ) : (
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-elevated text-muted uppercase text-[10px] tracking-wider border-b border-border">
              <tr>
                <th className="py-2.5 px-3 font-semibold">Horário</th>
                <th className="py-2.5 px-3 font-semibold">Ativo</th>
                <th className="py-2.5 px-3 font-semibold">Sinal</th>
                <th className="py-2.5 px-3 font-semibold">Decisão IA</th>
                <th className="py-2.5 px-3 font-semibold">Confiança ML</th>
                <th className="py-2.5 px-3 font-semibold">Payout</th>
                <th className="py-2.5 px-3 font-semibold">Status Execução</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {displayedSignals.map((sig) => {
                const isApproved = sig.status === "APPROVED";
                const isCall = sig.direction === "CALL";
                const probPercent = sig.prob !== null ? Math.round(sig.prob * 100) : null;
                const thresholdPercent = Math.round(sig.threshold * 100);

                return (
                  <tr
                    key={sig.id}
                    className="hover:bg-surface-elevated/50 transition-colors"
                  >
                    {/* Timestamp */}
                    <td className="py-2 px-3 font-mono text-muted whitespace-nowrap">
                      {sig.time.split(" ")[1] || sig.time}
                    </td>

                    {/* Asset Symbol */}
                    <td className="py-2 px-3 font-semibold text-foreground whitespace-nowrap">
                      {sig.asset}
                    </td>

                    {/* Direction: CALL / PUT */}
                    <td className="py-2 px-3 whitespace-nowrap">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 px-2 py-0.5 rounded font-bold uppercase text-[11px]",
                          isCall
                            ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
                            : "bg-rose-500/15 text-rose-400 border border-rose-500/20"
                        )}
                      >
                        {isCall ? (
                          <TrendingUp size={11} />
                        ) : (
                          <TrendingDown size={11} />
                        )}
                        {sig.direction}
                      </span>
                    </td>

                    {/* IA Decision Badge */}
                    <td className="py-2 px-3 whitespace-nowrap">
                      {isApproved ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                          <CheckCircle2 size={10} />
                          APROVADO
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                          <XCircle size={10} />
                          BLOQUEADO
                        </span>
                      )}
                    </td>

                    {/* ML Confidence Score */}
                    <td className="py-2 px-3 min-w-[130px]">
                      {probPercent !== null ? (
                        <div className="flex flex-col gap-1">
                          <div className="flex justify-between text-[10px] font-mono">
                            <span
                              className={cn(
                                "font-semibold",
                                isApproved ? "text-emerald-400" : "text-amber-400"
                              )}
                            >
                              {probPercent}%
                            </span>
                            <span className="text-muted">teto {thresholdPercent}%</span>
                          </div>
                          <div className="w-full bg-border h-1.5 rounded-full overflow-hidden">
                            <div
                              className={cn(
                                "h-full rounded-full transition-all",
                                isApproved ? "bg-emerald-400" : "bg-amber-400"
                              )}
                              style={{ width: `${Math.min(probPercent, 100)}%` }}
                            />
                          </div>
                        </div>
                      ) : (
                        <span className="text-muted text-[11px]">—</span>
                      )}
                    </td>

                    {/* Payout */}
                    <td className="py-2 px-3 whitespace-nowrap font-mono font-medium text-foreground">
                      <span className="px-1.5 py-0.5 rounded bg-surface-elevated border border-border">
                        {Math.round(sig.payout * 100)}%
                      </span>
                    </td>

                    {/* Execution details */}
                    <td className="py-2 px-3 whitespace-nowrap">
                      {sig.executed ? (
                        sig.profit !== undefined && sig.profit !== null ? (
                          sig.profit > 0 ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                              WIN (+R$ {sig.profit.toFixed(2)})
                            </span>
                          ) : sig.profit < 0 ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">
                              LOSS (R$ {sig.profit.toFixed(2)})
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-muted/20 text-muted border border-border">
                              EMPATE
                            </span>
                          )
                        ) : (
                          <span className="text-emerald-400 font-semibold flex items-center gap-1">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                            Em andamento...
                            {sig.order_id && (
                              <span className="text-[10px] text-muted font-mono">
                                #{sig.order_id.slice(-4)}
                              </span>
                            )}
                          </span>
                        )
                      ) : sig.details && (sig.details.includes("Veto") || sig.details.includes("Filtro")) ? (
                        <span className="text-amber-400/90 font-medium text-[11px] flex items-center gap-1">
                          <span className="h-1 w-1 rounded-full bg-amber-400"></span>
                          {sig.details}
                        </span>
                      ) : isApproved ? (
                        <span className="text-muted text-[11px]">
                          {sig.details || "Aguardando Confirmação"}
                        </span>
                      ) : (
                        <span className="text-muted text-[11px]">
                          Filtro ML Rejeitou
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
