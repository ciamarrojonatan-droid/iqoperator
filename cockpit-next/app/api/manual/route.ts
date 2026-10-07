import fs from "fs";
import path from "path";
import { NextResponse } from "next/server";
export const dynamic="force-dynamic";
const DEFAULT_ASSETS = ["EURUSD-OTC","GBPUSD-OTC","USDJPY-OTC","AUDUSD-OTC","EURGBP-OTC","USDCAD-OTC"];
function allowedAssets(): string[]{
  const raw = process.env.IQ_ASSETS || "";
  const list = raw.split(",").map(s=>s.trim().toUpperCase()).filter(Boolean);
  return list.length ? list : DEFAULT_ASSETS;
}
function clean(s?: string | null): string {
  return (s || "").trim();
}
function resolve(p:string, forWrite=false){
  p = clean(p);
  if(!p) return p;
  if(path.isAbsolute(p)) return p;
  const cand=[path.join(process.cwd(), p), path.join(process.cwd(),"..",p), path.join("/app",p)];
  if(forWrite) return cand[1].endsWith(".json") ? cand[1] : cand[0];
  for(const c of cand) if(fs.existsSync(c)) return c;
  return cand[1];
}

export async function POST(req: Request){
  const { signal, asset, stake } = await req.json().catch(()=>({}));
  if(signal!=="call" && signal!=="put") return NextResponse.json({error:"signal must be call|put"}, {status:400});
  const assets = allowedAssets();
  const a = asset ? String(asset).toUpperCase() : assets[0];
  if(!assets.includes(a)) return NextResponse.json({error:`asset must be one of ${assets.join(",")}`}, {status:400});
  let st: number | undefined;
  if(stake !== undefined && stake !== null && stake !== ""){
    st = Number(stake);
    if(!Number.isFinite(st) || st <= 0) return NextResponse.json({error:"stake must be > 0"}, {status:400});
  }
  const defaultManual = (clean(process.env.TRADE_LOG).includes("lab")) ? "data/manual_signal_lab.json" : "data/manual_signal.json";
  const p = resolve(clean(process.env.MANUAL_SIGNAL) || defaultManual, true);
  fs.mkdirSync(path.dirname(p), {recursive:true});
  fs.writeFileSync(p, JSON.stringify({signal, asset: a, stake: st, ts: Date.now()/1000}));
  return NextResponse.json({ok:true, signal, asset: a, stake: st});
}
export async function GET(){
  try{
    let target = clean(process.env.BOT_STATUS);
    if(!target){
      const tradeLog = clean(process.env.TRADE_LOG);
      if(tradeLog && tradeLog.includes("lab")){
        target = "data/bot_status_lab.json";
      } else {
        const pLab = resolve("data/bot_status_lab.json", false);
        const pProd = resolve("data/bot_status.json", false);
        if(fs.existsSync(pLab) && fs.existsSync(pProd)){
          try {
            const mLab = fs.statSync(pLab).mtimeMs;
            const mProd = fs.statSync(pProd).mtimeMs;
            target = mLab > mProd ? "data/bot_status_lab.json" : "data/bot_status.json";
          } catch {
            target = "data/bot_status.json";
          }
        } else if (fs.existsSync(pLab)) {
          target = "data/bot_status_lab.json";
        } else {
          target = "data/bot_status.json";
        }
      }
    }
    const p=resolve(target, false);
    const b = JSON.parse(fs.readFileSync(p,"utf-8"));
    return NextResponse.json(b);
  }catch(e: any){ return NextResponse.json({error: String(e?.message || "no status yet")}, {status:404}); }
}
