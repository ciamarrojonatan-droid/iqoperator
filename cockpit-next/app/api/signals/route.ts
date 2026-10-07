import fs from "fs";
import path from "path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

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

function clean(s?: string | null): string {
  return (s || "").trim();
}

function resolve(p: string) {
  p = clean(p);
  if (!p) return p;
  if (path.isAbsolute(p)) return p;
  const cand = [
    path.join(process.cwd(), p),
    path.join(process.cwd(), "..", p),
    path.join("/app", p),
  ];
  for (const c of cand) {
    if (fs.existsSync(c)) return c;
  }
  return cand[1];
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const assetFilter = searchParams.get("asset")?.toUpperCase();
    const statusFilter = searchParams.get("status")?.toUpperCase();
    const limit = Math.min(Math.max(parseInt(searchParams.get("limit") || "100", 10), 1), 500);

    let target = clean(process.env.SIGNALS_LOG);
    if(!target){
      const tradeLog = clean(process.env.TRADE_LOG);
      if(tradeLog && tradeLog.includes("lab")){
        target = "data/signals_log_lab.json";
      } else {
        const pLab = resolve("data/signals_log_lab.json");
        const pProd = resolve("data/signals_log.json");
        if(fs.existsSync(pLab) && fs.existsSync(pProd)){
          try {
            const mLab = fs.statSync(pLab).mtimeMs;
            const mProd = fs.statSync(pProd).mtimeMs;
            target = mLab > mProd ? "data/signals_log_lab.json" : "data/signals_log.json";
          } catch {
            target = "data/signals_log.json";
          }
        } else if (fs.existsSync(pLab)) {
          target = "data/signals_log_lab.json";
        } else {
          target = "data/signals_log.json";
        }
      }
    }
    const logPath = resolve(target);
    if (!fs.existsSync(logPath)) {
      return NextResponse.json({
        total: 0,
        approved_count: 0,
        blocked_count: 0,
        signals: [],
        assets: [],
      });
    }

    const raw = fs.readFileSync(logPath, "utf-8");
    const allSignals: SignalRecord[] = JSON.parse(raw);
    if (!Array.isArray(allSignals)) {
      return NextResponse.json({
        total: 0,
        approved_count: 0,
        blocked_count: 0,
        signals: [],
        assets: [],
      });
    }

    const total = allSignals.length;
    const approved_count = allSignals.filter((s) => s.status === "APPROVED").length;
    const blocked_count = allSignals.filter((s) => s.status === "BLOCKED").length;

    let executed_count = 0;
    let win_count = 0;
    let loss_count = 0;

    for (const s of allSignals) {
      if (s.executed) {
        executed_count++;
        if (s.profit !== undefined && s.profit !== null) {
          if (s.profit > 0) win_count++;
          else if (s.profit < 0) loss_count++;
        }
      }
    }

    // Unique assets list from signals
    const assets = Array.from(new Set(allSignals.map((s) => s.asset))).sort();

    // Filter in reverse chronological order (newest first)
    let filtered = [...allSignals].reverse();

    if (assetFilter && assetFilter !== "ALL") {
      filtered = filtered.filter((s) =>
        s.asset.toUpperCase().includes(assetFilter)
      );
    }

    if (statusFilter && statusFilter !== "ALL") {
      if (statusFilter === "APPROVED" || statusFilter === "BLOCKED") {
        filtered = filtered.filter((s) => s.status === statusFilter);
      } else if (statusFilter === "CALL" || statusFilter === "PUT") {
        filtered = filtered.filter((s) => s.direction === statusFilter);
      }
    }

    const sliced = filtered.slice(0, limit);

    return NextResponse.json({
      total,
      approved_count,
      blocked_count,
      executed_count,
      win_count,
      loss_count,
      signals: sliced,
      assets,
    });
  } catch (error: any) {
    return NextResponse.json(
      {
        total: 0,
        approved_count: 0,
        blocked_count: 0,
        signals: [],
        assets: [],
        error: String(error?.message || error),
      },
      { status: 500 }
    );
  }
}
