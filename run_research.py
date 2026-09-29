#!/usr/bin/env python3
"""
run_research.py - Top-Level Orchestrator & CLI for Binary Options Quantitative Research.

Comprehensive entrypoint executing:
1. Historical dataset ingestion and schema validation.
2. Rigid 3-way chronological partitioning (50% IS, 25% VAL, 25% OOS) with boundary purging
   and warmup embargo.
3. Multi-hypothesis empirical evaluation (H001 - H008) across all partitions.
4. Out-of-sample degradation and composite stability scoring (Delta EV, DI, Delta WR, S_comp).
5. Verification audit proving zero martingale / irrational asymmetric allocation dependencies.
6. ASCII summary table display to stdout and dual Markdown/JSON report export.

Usage:
  python run_research.py [--data <path>] [--hypotheses H001,H002,...] [--payout 0.85] [--export-report <path>]
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time
from typing import List, Optional

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from iq_regime_adaptive.pipeline.data_loader import load_csv, DataValidationError
from iq_regime_adaptive.backtest.partitioner import DataPartitioner, PartitionedData
from iq_regime_adaptive.backtest.engine import BacktestEngine, BacktestResult
from iq_regime_adaptive.hypotheses.registry import (
    get_hypothesis,
    list_hypotheses,
    CANONICAL_IDS,
)
from iq_regime_adaptive.reports.generator import (
    QuantitativeReportGenerator,
    HypothesisEvaluation,
    ResearchReport,
)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Binary Options Regime-Adaptive Quantitative Research & Backtest Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data",
        type=str,
        default="data/EURUSD_M5_iq.csv",
        help="Path to historical OHLCV candle CSV dataset",
    )
    parser.add_argument(
        "--hypotheses",
        type=str,
        default="H001,H002,H003,H004,H005,H006,H007,H008",
        help="Comma-separated list of hypothesis IDs to evaluate (e.g. H001,H002 or canonical IDs)",
    )
    parser.add_argument(
        "--payout",
        type=float,
        default=0.85,
        help="Broker payout rate B (e.g. 0.85 for 85%% payout)",
    )
    parser.add_argument(
        "--export-report",
        type=str,
        default="reports/research_report",
        help="Path or base name for exporting Markdown and JSON reports",
    )
    parser.add_argument(
        "--is-ratio",
        type=float,
        default=0.50,
        help="In-Sample partition ratio",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.25,
        help="Validation partition ratio",
    )
    parser.add_argument(
        "--oos-ratio",
        type=float,
        default=0.25,
        help="Out-of-Sample partition ratio",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=60,
        help="Warmup embargo bars per partition",
    )
    parser.add_argument(
        "--initial-balance",
        type=float,
        default=1000.0,
        help="Starting capital for backtest simulation",
    )
    parser.add_argument(
        "--risk-method",
        type=str,
        default="fractional_kelly",
        choices=["fractional_kelly", "fixed", "fixed_percentage"],
        help="Capital allocation method",
    )
    parser.add_argument(
        "--fixed-stake",
        type=float,
        default=10.0,
        help="Stake for fixed allocation method",
    )
    parser.add_argument(
        "--max-risk-cap",
        type=float,
        default=0.02,
        help="Maximum risk cap fraction per trade (e.g. 0.02 for 2%%)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed step-by-step progress logging",
    )

    return parser.parse_args(argv)


def run_pipeline(args: argparse.Namespace) -> ResearchReport:
    """
    Executes the quantitative research and verification pipeline.
    """
    t_start = time.time()
    print("=" * 80)
    print("IQ REGIME-ADAPTIVE: QUANTITATIVE RESEARCH & VERIFICATION ENGINE")
    print("=" * 80)

    # 1. Ingestion
    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = _PROJECT_ROOT / data_path

    if not data_path.exists():
        raise FileNotFoundError(f"Data file does not exist: {data_path}")

    print(f"[1/5] Ingesting candle dataset: {data_path}")
    df = load_csv(data_path)
    total_bars = len(df)
    start_time = df["time"].iloc[0] if "time" in df.columns else "N/A"
    end_time = df["time"].iloc[-1] if "time" in df.columns else "N/A"
    print(f"      Loaded {total_bars:,} bars | Span: {start_time} -> {end_time}")

    # 2. Partitioning
    print(f"[2/5] Executing rigid chronological partitioning ({int(args.is_ratio*100)}/{int(args.val_ratio*100)}/{int(args.oos_ratio*100)})...")
    partitioner = DataPartitioner(
        is_ratio=args.is_ratio,
        val_ratio=args.val_ratio,
        oos_ratio=args.oos_ratio,
        horizon_bars=1,
        warmup_bars=args.warmup,
    )
    partitioned = partitioner.partition(df)
    is_df = partitioned.is_df
    val_df = partitioned.val_df
    oos_df = partitioned.oos_df

    print(f"      IS  partition: {len(is_df):,} bars (tradeable: {partitioned.metadata['IS'].tradeable_bars:,})")
    print(f"      VAL partition: {len(val_df):,} bars (tradeable: {partitioned.metadata['VAL'].tradeable_bars:,})")
    print(f"      OOS partition: {len(oos_df):,} bars (tradeable: {partitioned.metadata['OOS'].tradeable_bars:,})")

    # 3. Resolve Hypotheses
    raw_hyp_ids = [h.strip() for h in args.hypotheses.split(",") if h.strip()]
    if not raw_hyp_ids:
        raw_hyp_ids = ["H001", "H002", "H003", "H004", "H005", "H006", "H007", "H008"]

    print(f"[3/5] Evaluating {len(raw_hyp_ids)} hypotheses across IS, VAL, and OOS partitions (payout={args.payout * 100:.1f}%)...")

    engine = BacktestEngine(
        initial_balance=args.initial_balance,
        risk_method=args.risk_method,
        fixed_stake=args.fixed_stake,
        max_risk_cap=args.max_risk_cap,
    )

    report_gen = QuantitativeReportGenerator(
        payout=args.payout,
        max_risk_cap=args.max_risk_cap,
    )

    evaluations: List[HypothesisEvaluation] = []

    for idx, hyp_id in enumerate(raw_hyp_ids, 1):
        t_hyp = time.time()
        try:
            hyp_instance = get_hypothesis(hyp_id)
        except KeyError:
            print(f"      [WARNING] Unknown hypothesis ID '{hyp_id}', skipping.")
            continue

        if not args.quiet:
            print(f"      [{idx}/{len(raw_hyp_ids)}] Running {hyp_instance.hypothesis_id}...", end="", flush=True)

        # Run on IS
        res_is = engine.run(is_df, hyp_instance, payout=args.payout)
        # Run on VAL
        res_val = engine.run(val_df, hyp_instance, payout=args.payout)
        # Run on OOS
        res_oos = engine.run(oos_df, hyp_instance, payout=args.payout)

        # Build evaluation
        eval_item = report_gen.build_evaluation(
            hypothesis_id=hyp_instance.hypothesis_id,
            is_result=res_is,
            oos_result=res_oos,
            val_result=res_val,
            name=hyp_instance.name,
            family=hyp_instance.family,
            description=hyp_instance.description,
        )
        evaluations.append(eval_item)

        dur = time.time() - t_hyp
        if not args.quiet:
            print(
                f" Done ({dur:.1f}s) | IS Trades: {res_is.metrics.total_trades}, "
                f"OOS Trades: {res_oos.metrics.total_trades} | "
                f"DI: {eval_item.degradation.degradation_index:+.2f} | "
                f"S_comp: {eval_item.degradation.stability_score:.1f} ({eval_item.degradation.verdict})"
            )

    # 4. Generate Quantitative Report & Governance Audit
    print(f"[4/5] Executing Anti-Martingale Governance Audit and compiling report...")
    dataset_metadata = {
        "path": str(data_path.relative_to(_PROJECT_ROOT)) if _PROJECT_ROOT in data_path.parents else str(data_path),
        "totalBars": total_bars,
        "span": {"start": str(start_time), "end": str(end_time)},
        "partitionRatios": {
            "inSample": args.is_ratio,
            "validation": args.val_ratio,
            "outOfSample": args.oos_ratio,
        },
        "warmupBars": args.warmup,
    }

    report = report_gen.generate_report(
        evaluations=evaluations,
        dataset_metadata=dataset_metadata,
    )

    # Display ASCII Table
    print("\n" + "=" * 80)
    print("COMPARATIVE DEGRADATION MATRIX (IN-SAMPLE VS OUT-OF-SAMPLE)")
    print("=" * 80)
    print(report.to_ascii_table())
    print("")

    # Display Attestation & Champion
    print("GOVERNANCE & VERIFICATION ATTESTATION:")
    print(f"  Anti-Martingale Audit : [{report.attestation.anti_martingale_audit}]")
    print(f"  Allocation Compliance : [{report.attestation.allocation_compliance}]")
    print(f"  Audited Trades Count  : {report.attestation.checked_trades_count}")
    print(f"  Audit Passed          : {report.attestation.audit_passed}")

    if report.champion:
        print("\nRECOMMENDED CHAMPION STRATEGY:")
        print(f"  Identifier     : {report.champion.get('canonicalId')} ({report.champion.get('hypothesisId')})")
        print(f"  Stability Score: {report.champion.get('stabilityScore', 0.0):.1f} / 100")
        print(f"  OOS Win Rate   : {report.champion.get('outOfSampleWinRate', 0.0) * 100:.2f}%")
        print(f"  OOS EV         : {report.champion.get('outOfSampleEV', 0.0):+.4f}")
        print(f"  Verdict        : {report.champion.get('verdict')}")
        print(f"  Edge Status    : {report.champion.get('edgeStatus')}")

    # 5. Export Reports
    print(f"\n[5/5] Exporting authoritative research reports...")
    export_target = Path(args.export_report)
    if not export_target.is_absolute():
        export_target = _PROJECT_ROOT / export_target

    if export_target.suffix in (".md", ".json"):
        output_dir = export_target.parent
        base_name = export_target.stem
    else:
        output_dir = export_target.parent if export_target.name != "reports" else export_target
        base_name = export_target.name if export_target.name != "reports" else "research_report"

    md_path, json_path = report.save(output_dir=output_dir, base_name=base_name)
    print(f"      Markdown report saved: {md_path}")
    print(f"      JSON report saved    : {json_path}")

    total_time = time.time() - t_start
    print(f"\nPipeline successfully completed in {total_time:.2f} seconds.")
    print("=" * 80)

    return report


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    args = parse_args()
    try:
        run_pipeline(args)
        sys.exit(0)
    except Exception as e:
        print(f"\n[FATAL ERROR] Research pipeline failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
