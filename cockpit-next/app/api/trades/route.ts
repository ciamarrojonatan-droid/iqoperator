import fs from "fs";
import path from "path";
export const dynamic="force-dynamic";

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

export async function GET(){
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
  try{ const b=fs.readFileSync(p); return new Response(b,{headers:{"Content-Type":"text/csv"}});}catch{ return new Response("not found",{status:404});}
}
