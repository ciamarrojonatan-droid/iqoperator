import fs from "fs";
import path from "path";
export type Trade = { time:string; asset?:string; signal:string; info:string; payout:string; winrate:string; kelly:string; stake:string; profit:string; balance:string };
export type AssetStat = { asset:string; trades:number; wins:number; winrate:number; profit:number };
function clean(s?: string | null): string {
  return (s || "").trim();
}

function resolve(p:string){
  p = clean(p);
  if(!p) return p;
  if(path.isAbsolute(p)) return p;
  const cand = [path.join(process.cwd(), p), path.join(process.cwd(),"..",p), path.join("/app", p)];
  for(const c of cand) if(fs.existsSync(c)) return c;
  return cand[1];
}
export function readTrades(): Trade[]{
  let target = clean(process.env.TRADE_LOG);
  if(!target){
    const pLab = resolve("data/trades_lab.csv");
    const pProd = resolve("data/trades_live.csv");
    if(fs.existsSync(pLab) && fs.existsSync(pProd)){
      try {
        const mLab = fs.statSync(pLab).mtimeMs;
        const mProd = fs.statSync(pProd).mtimeMs;
        target = mLab > mProd ? "data/trades_lab.csv" : "data/trades_live.csv";
      } catch {
        target = "data/trades_live.csv";
      }
    } else if (fs.existsSync(pLab)) {
      target = "data/trades_lab.csv";
    } else {
      target = "data/trades_live.csv";
    }
  }
  const p = resolve(target);
  try{
    const raw=fs.readFileSync(p,"utf-8").trim();
    if(!raw) return [];
    const lines=raw.split("\n"); const headers=lines[0].split(",");
    return lines.slice(1).filter(Boolean).map(l=>{
      const v=l.split(","); const o:Record<string,string>={};
      headers.forEach((h,i)=>o[h.trim()]=v[i]?.trim()||"");
      return o as Trade;
    });
  }catch{ return []; }
}
export function stats(){
  const rows=readTrades();
  const n=rows.length, wins=rows.filter(r=>parseFloat(r.profit||"0")>0).length;
  const wr=n?wins/n:0, profit=rows.reduce((s,r)=>s+parseFloat(r.profit||"0"),0);
  const bal=rows.at(-1)?.balance ?? "n/a";
  const byMap = new Map<string, {trades:number; wins:number; profit:number}>();
  for(const r of rows){
    const a = r.asset || "—";
    const e = byMap.get(a) || {trades:0, wins:0, profit:0};
    const pf = parseFloat(r.profit||"0") || 0;
    e.trades += 1; if(pf > 0) e.wins += 1; e.profit += pf;
    byMap.set(a, e);
  }
  const byAsset: AssetStat[] = Array.from(byMap.entries()).map(([asset, e])=>({
    asset, trades: e.trades, wins: e.wins,
    winrate: e.trades ? e.wins/e.trades : 0,
    profit: Math.round(e.profit*100)/100,
  })).sort((x,y)=>y.profit-x.profit);
  return { trades:n, wins, winrate:wr, profit:Math.round(profit*100)/100, balance:bal, byAsset, last: [...rows].reverse() };
}
