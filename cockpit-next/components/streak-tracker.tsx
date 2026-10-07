import { Flame, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";

type StreakTrackerProps = {
  trades: any[];
};

function parseProfit(val: any): number {
  if (typeof val === "number") return val;
  if (!val && val !== 0) return NaN;
  const str = String(val).trim();
  const isNegative = str.includes("-") || (str.includes("(") && str.includes(")"));
  const cleaned = str.replace(",", ".").replace(/[^0-9.]/g, "");
  const num = parseFloat(cleaned);
  if (isNaN(num)) return NaN;
  return isNegative ? -Math.abs(num) : num;
}

function isWin(trade: any): boolean {
  if (trade?.won === true || trade?.won === "True" || trade?.won === "true" || trade?.won === 1) return true;
  if (trade?.won === false || trade?.won === "False" || trade?.won === "false" || trade?.won === 0) return false;
  const p = parseProfit(trade?.profit ?? trade?.pnl);
  return !isNaN(p) && p > 0;
}

export function StreakTracker({ trades }: StreakTrackerProps) {
  if (!trades || trades.length === 0) {
    return (
      <div className="bg-surface border border-border rounded-lg p-4">
        <div className="flex items-center gap-2">
          <Flame size={14} className="text-muted" />
          <h3 className="text-sm font-medium">Sequências</h3>
        </div>
        <p className="text-muted text-sm mt-2">Sem trades ainda</p>
      </div>
    );
  }

  // Ordem cronológica: mais antigo -> mais recente
  const chronological = [...trades].reverse();

  // Melhor sequência de wins / pior de losses
  let bestWinStreak = 0;
  let worstLossStreak = 0;
  let runWins = 0;
  let runLosses = 0;

  for (const trade of chronological) {
    if (isWin(trade)) {
      runWins += 1;
      runLosses = 0;
      if (runWins > bestWinStreak) bestWinStreak = runWins;
    } else {
      runLosses += 1;
      runWins = 0;
      if (runLosses > worstLossStreak) worstLossStreak = runLosses;
    }
  }

  // Sequência atual: conta a partir do mais recente (início do array original)
  const lastIsWin = isWin(trades[0]);
  let currentCount = 0;
  for (const trade of trades) {
    if (isWin(trade) === lastIsWin) {
      currentCount += 1;
    } else {
      break;
    }
  }
  const currentLabel = `${currentCount}${lastIsWin ? "W" : "L"}`;

  // Últimos 100 resultados (visual), mais recente à direita
  const lastN = [...trades.slice(0, 100)].reverse();

  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <div className="flex items-center gap-2">
        <Flame size={14} className="text-muted" />
        <h3 className="text-sm font-medium">Sequências</h3>
      </div>

      <div className="grid grid-cols-3 gap-2 mt-3">
        <div>
          <p className="text-muted text-xs">Sequência atual</p>
          <p
            className={cn(
              "text-lg font-semibold",
              lastIsWin ? "text-success" : "text-destructive"
            )}
          >
            {currentLabel}
          </p>
        </div>
        <div>
          <p className="text-muted text-xs">Melhor (wins)</p>
          <p className="text-lg font-semibold text-success">
            {bestWinStreak > 0 ? `${bestWinStreak}W` : "—"}
          </p>
        </div>
        <div>
          <p className="text-muted text-xs">Pior (losses)</p>
          <p className="text-lg font-semibold text-destructive">
            {worstLossStreak > 0 ? `${worstLossStreak}L` : "—"}
          </p>
        </div>
      </div>

      <div className="mt-3">
        <p className="text-muted text-xs mb-2">Últimos {lastN.length}</p>
        <div className="flex items-center gap-1.5 flex-wrap">
          {lastN.map((trade, index) => {
            const win = isWin(trade);
            const profitVal = parseProfit(trade?.profit ?? trade?.pnl);
            const profitLabel = !isNaN(profitVal)
              ? ` (${profitVal >= 0 ? "+" : ""}${profitVal.toFixed(2)})`
              : "";
            return (
              <span
                key={index}
                role="img"
                title={win ? `Vitória / Win${profitLabel}` : `Derrota / Loss${profitLabel}`}
                aria-label={win ? `Vitória${profitLabel}` : `Derrota${profitLabel}`}
                className={cn(
                  "inline-flex items-center justify-center w-5 h-5 text-[11px] font-bold transition-transform hover:scale-110 select-none shadow-sm",
                  win
                    ? "rounded-full bg-success text-background"
                    : "rounded-sm bg-destructive text-white"
                )}
              >
                {win ? (
                  <Check size={11} strokeWidth={3} aria-hidden="true" />
                ) : (
                  <X size={11} strokeWidth={3} aria-hidden="true" />
                )}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
