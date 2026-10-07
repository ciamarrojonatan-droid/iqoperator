"use client"

import * as React from "react"
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { cn } from "@/lib/utils"
import { ChartTooltip } from "@/components/ui/chart-tooltip"

const BREAKEVEN = 55.56
const THRESHOLD = 53.48
const WINDOW = 10

interface WinratePoint {
  trade: number
  winrate: number
}

function isWin(t: any): boolean {
  const profit = parseFloat(t?.profit)
  return !isNaN(profit) && profit > 0
}

export function WinrateTrend({
  trades,
  className,
}: {
  trades: any[]
  className?: string
}) {
  const data: WinratePoint[] = React.useMemo(() => {
    if (!trades || trades.length === 0) return []
    const chrono = [...trades].reverse()
    return chrono.map((t, i) => {
      const slice = chrono.slice(0, i + 1)
      const wins = slice.filter(isWin).length
      return {
        trade: i + 1,
        winrate: slice.length > 0 ? (wins / slice.length) * 100 : 0,
      }
    })
  }, [trades])

  const current = data.length > 0 ? data[data.length - 1].winrate : 0
  const ok = current >= THRESHOLD

  return (
    <div className={cn("bg-surface border border-border rounded-lg p-4", className)}>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-medium">Evolução do Winrate</h2>
        {data.length > 0 && (
          <span
            className={cn(
              "text-xs font-semibold px-2 py-0.5 rounded font-mono",
              ok ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive"
            )}
            style={{ color: ok ? "#3DD68C" : "#FF5470" }}
          >
            Atual: {current.toFixed(2)}% {ok ? "· ok" : "· atenção"}
          </span>
        )}
      </div>

      {data.length === 0 ? (
        <div className="h-[240px] flex items-center justify-center text-sm text-muted">
          Sem trades para calcular o winrate
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart
            data={data}
            syncId="cockpit-session"
            margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#232A36" />
            <XAxis
              dataKey="trade"
              stroke="#8A8F98"
              tick={{ fontSize: 11 }}
              label={{ value: "trade", position: "insideBottomRight", fontSize: 11, fill: "#8A8F98" }}
            />
            <YAxis
              stroke="#8A8F98"
              tick={{ fontSize: 11 }}
              domain={[0, 100]}
              tickFormatter={(v: number) => `${v}%`}
            />
            <Tooltip
              content={
                <ChartTooltip
                  labelFormatter={(label) => `Trade #${label}`}
                  valueFormatter={(val) => `${Number(val).toFixed(2)}%`}
                />
              }
            />
            <ReferenceLine
              y={BREAKEVEN}
              stroke="#F97316"
              strokeDasharray="5 5"
              label={{ value: `Break-even ${BREAKEVEN}%`, fontSize: 11, fill: "#F97316", position: "insideTopRight" }}
            />
            <ReferenceLine
              y={THRESHOLD}
              stroke="#8A8F98"
              strokeDasharray="3 3"
              label={{ value: `Meta ${THRESHOLD}%`, fontSize: 11, fill: "#8A8F98", position: "insideBottomRight" }}
            />
            <Line
              type="monotone"
              dataKey="winrate"
              name="Winrate"
              stroke="#00D1A0"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      {data.length > 0 && (
        <p className="mt-2 text-[11px] text-muted font-mono">
          Winrate cumulativo total da sessão · break-even {BREAKEVEN}% · meta {THRESHOLD}%
        </p>
      )}
    </div>
  )
}
