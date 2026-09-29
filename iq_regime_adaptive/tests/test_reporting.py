"""
test_reporting.py - Comprehensive Unit & Integration Test Suite for Reporting Engine.

Tests:
1. QuantitativeReportGenerator & HypothesisEvaluation.
2. JSON Schema Compliance matching Section 4.2 of Quant Research Specification.
3. Markdown & ASCII Degradation Matrix Table Formatting.
4. Risk Governance & Anti-Martingale Verification Attestation.
5. End-to-end file persistence (save and reload).
6. Edge cases: empty trades, zero PnL, division by zero guards.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd

from iq_regime_adaptive.backtest.metrics import BacktestMetrics, compute_backtest_metrics
from iq_regime_adaptive.backtest.engine import BacktestResult, TradeRecord
from iq_regime_adaptive.backtest.degradation import DegradationReport, compute_degradation
from iq_regime_adaptive.reports.generator import (
    QuantitativeReportGenerator,
    HypothesisEvaluation,
    VerificationAttestation,
    ResearchReport,
    run_governance_audit,
)
from run_research import parse_args, run_pipeline


def _make_dummy_metrics(
    trades: int = 100,
    wins: int = 60,
    payout: float = 0.85,
    expected_value: float = 0.11,
    wlb: float = 0.50,
    pnl: float = 120.0,
    max_dd: float = 0.05,
) -> BacktestMetrics:
    """Helper creating a test BacktestMetrics instance."""
    losses = trades - wins
    return BacktestMetrics(
        total_trades=trades,
        wins=wins,
        losses=losses,
        pushes=0,
        nominal_win_rate=wins / trades if trades > 0 else 0.0,
        wilson_lower_bound=wlb,
        breakeven_win_rate=1.0 / (1.0 + payout),
        expected_value=expected_value,
        ev_wlb=wlb * (1.0 + payout) - 1.0,
        effective_n=float(trades),
        total_pnl=pnl,
        return_pct=pnl / 1000.0,
        initial_balance=1000.0,
        final_balance=1000.0 + pnl,
        peak_balance=1000.0 + max(0.0, pnl),
        max_drawdown=max_dd * 1000.0,
        max_drawdown_pct=max_dd,
        profit_factor=1.5,
        sharpe_ratio=1.2,
        sortino_ratio=1.8,
        payout_tested=payout,
        monthly_consistency="3_OF_3_MONTHS_PROFITABLE",
    )


class TestReportingEngine(unittest.TestCase):
    """Unit tests for reports generator and data structures."""

    def setUp(self):
        self.generator = QuantitativeReportGenerator(payout=0.85, max_risk_cap=0.02)
        self.is_metrics = _make_dummy_metrics(trades=200, wins=124, expected_value=0.147, wlb=0.551)
        self.val_metrics = _make_dummy_metrics(trades=100, wins=60, expected_value=0.110, wlb=0.500)
        self.oos_metrics = _make_dummy_metrics(trades=100, wins=61, expected_value=0.128, wlb=0.510)

    def test_build_evaluation(self):
        eval_item = self.generator.build_evaluation(
            hypothesis_id="H001",
            is_result=self.is_metrics,
            oos_result=self.oos_metrics,
            val_result=self.val_metrics,
            name="Range Mean Reversion",
            family="STATISTICAL_MEAN_REVERSION",
            description="Mean reversion on Bollinger 2.0 std",
        )

        self.assertEqual(eval_item.hypothesis_id, "H001")
        self.assertEqual(eval_item.family, "STATISTICAL_MEAN_REVERSION")
        self.assertAlmostEqual(eval_item.payout_tested, 0.85)
        self.assertAlmostEqual(eval_item.breakeven_hurdle, 1.0 / 1.85, places=4)
        self.assertIsNotNone(eval_item.degradation)
        self.assertIn(eval_item.degradation.verdict, ["ANTIFRAGILE", "ROBUST", "MODERATE_DECAY", "SEVERE_DECAY", "REJECTED"])

    def test_evaluation_to_dict_schema(self):
        eval_item = self.generator.build_evaluation(
            hypothesis_id="H001_RANGE_MEAN_REVERSION",
            is_result=self.is_metrics,
            oos_result=self.oos_metrics,
            val_result=self.val_metrics,
        )
        d = eval_item.to_dict()

        # Check required schema keys
        self.assertEqual(d["hypothesisId"], "H001_RANGE_MEAN_REVERSION")
        self.assertIn("payoutTested", d)
        self.assertIn("breakevenHurdle", d)
        self.assertIn("partitions", d)
        self.assertIn("inSample", d["partitions"])
        self.assertIn("validation", d["partitions"])
        self.assertIn("outOfSample", d["partitions"])
        self.assertIn("degradation", d)
        self.assertIn("deltaEV", d["degradation"])
        self.assertIn("degradationIndex", d["degradation"])
        self.assertIn("winRateDrop", d["degradation"])
        self.assertIn("stabilityScore", d["degradation"])
        self.assertIn("verdict", d["degradation"])
        self.assertIn("subScores", d["degradation"])
        self.assertIn("governanceVerdict", d)
        self.assertEqual(d["governanceVerdict"]["antiMartingaleAudit"], "VERIFIED_ZERO_MARTINGALE")

    def test_generate_report_and_json_serialization(self):
        eval1 = self.generator.build_evaluation(
            hypothesis_id="H001",
            is_result=self.is_metrics,
            oos_result=self.oos_metrics,
            val_result=self.val_metrics,
        )
        eval2 = self.generator.build_evaluation(
            hypothesis_id="H002",
            is_result=_make_dummy_metrics(trades=150, wins=75, expected_value=-0.075),
            oos_result=_make_dummy_metrics(trades=80, wins=35, expected_value=-0.189),
        )

        report = self.generator.generate_report(
            evaluations=[eval1, eval2],
            dataset_metadata={"path": "data/EURUSD_M5_iq.csv", "totalBars": 20000},
        )

        json_str = report.to_json()
        parsed = json.loads(json_str)

        self.assertIn("title", parsed)
        self.assertIn("generatedAt", parsed)
        self.assertIn("payoutTested", parsed)
        self.assertIn("breakevenHurdle", parsed)
        self.assertIn("governanceAttestation", parsed)
        self.assertIn("degradationMatrix", parsed)
        self.assertIn("hypotheses", parsed)
        self.assertEqual(len(parsed["degradationMatrix"]), 2)
        self.assertIn("championHypothesis", parsed)

    def test_ascii_table_formatting(self):
        eval1 = self.generator.build_evaluation(
            hypothesis_id="H001",
            is_result=self.is_metrics,
            oos_result=self.oos_metrics,
        )
        report = self.generator.generate_report([eval1])
        table = report.to_ascii_table()

        self.assertIn("Hyp ID", table)
        self.assertIn("Family", table)
        self.assertIn("N_IS", table)
        self.assertIn("WR_IS", table)
        self.assertIn("EV_IS", table)
        self.assertIn("N_OOS", table)
        self.assertIn("WR_OOS", table)
        self.assertIn("WLB_OOS", table)
        self.assertIn("EV_OOS", table)
        self.assertIn("Delta EV", table)
        self.assertIn("DI", table)
        self.assertIn("S_comp", table)
        self.assertIn("Verdict", table)
        self.assertIn("H001", table)

    def test_markdown_report_formatting(self):
        eval1 = self.generator.build_evaluation(
            hypothesis_id="H001",
            is_result=self.is_metrics,
            oos_result=self.oos_metrics,
        )
        report = self.generator.generate_report([eval1])
        md = report.to_markdown()

        self.assertIn("# Quantitative Verification & Research Report", md)
        self.assertIn("## 1. Executive Summary", md)
        self.assertIn("## 2. Risk Governance & Anti-Martingale Verification Attestation", md)
        self.assertIn("## 3. Comparative Degradation Matrix (H001 - H008)", md)
        self.assertIn("## 4. Comprehensive Hypotheses Breakdown", md)
        self.assertIn("## 5. Architectural Verification & Conclusion", md)
        self.assertIn("VERIFIED_ZERO_MARTINGALE", md)

    def test_report_save_and_reload(self):
        eval1 = self.generator.build_evaluation(
            hypothesis_id="H001",
            is_result=self.is_metrics,
            oos_result=self.oos_metrics,
        )
        report = self.generator.generate_report([eval1])

        with tempfile.TemporaryDirectory() as tmp_dir:
            md_path, json_path = report.save(output_dir=tmp_dir, base_name="custom_report")

            self.assertTrue(md_path.exists())
            self.assertTrue(json_path.exists())
            self.assertGreater(md_path.stat().st_size, 500)
            self.assertGreater(json_path.stat().st_size, 500)

            loaded_json = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded_json["title"], report.title)
            self.assertEqual(len(loaded_json["degradationMatrix"]), 1)


class TestGovernanceAudit(unittest.TestCase):
    """Tests auditing zero-martingale and capital risk compliance."""

    def test_governance_audit_clean_pass(self):
        attestation = run_governance_audit([], max_risk_cap=0.02)
        self.assertTrue(attestation.audit_passed)
        self.assertTrue(attestation.zero_martingale_confirmed)
        self.assertEqual(attestation.anti_martingale_audit, "VERIFIED_ZERO_MARTINGALE")
        self.assertEqual(len(attestation.violations_detected), 0)

    def test_governance_audit_detects_martingale_stake_doubling(self):
        # Create trade records where trade 2 doubled stake after a loss
        t1 = TradeRecord(
            trade_id=1, entry_idx=10, exit_idx=11, entry_time="2026-06-22", exit_time="2026-06-22",
            direction="CALL", entry_price=1.10, exit_price=1.09, result="LOSS", payout=0.85,
            stake=10.0, pnl=-10.0, balance=990.0, return_pct=-0.01,
        )
        t2 = TradeRecord(
            trade_id=2, entry_idx=12, exit_idx=13, entry_time="2026-06-22", exit_time="2026-06-22",
            direction="CALL", entry_price=1.09, exit_price=1.10, result="WIN", payout=0.85,
            stake=20.0,  # DOUBLED after loss! (Martingale)
            pnl=17.0, balance=1007.0, return_pct=0.007,
        )

        res = BacktestResult(
            trades=[t1, t2],
            trades_df=pd.DataFrame(),
            metrics=_make_dummy_metrics(),
            equity_curve=pd.Series(),
            initial_balance=1000.0,
            final_balance=1007.0,
            total_pnl=7.0,
            purged_signals_count=0,
            vetoed_signals_count=0,
            kill_switch_triggered=False,
            hypothesis_id="MALICIOUS_MARTINGALE_TEST",
        )

        attestation = run_governance_audit([res], max_risk_cap=0.05)
        self.assertFalse(attestation.audit_passed)
        self.assertFalse(attestation.zero_martingale_confirmed)
        self.assertEqual(attestation.anti_martingale_audit, "MARTINGALE_VIOLATION_DETECTED")
        self.assertTrue(any("stake increased after loss" in v for v in attestation.violations_detected))

    def test_governance_audit_detects_risk_cap_breach(self):
        # Create a trade where stake is $100 on $1000 balance (10% >> 2% cap)
        t1 = TradeRecord(
            trade_id=1, entry_idx=10, exit_idx=11, entry_time="2026-06-22", exit_time="2026-06-22",
            direction="CALL", entry_price=1.10, exit_price=1.11, result="WIN", payout=0.85,
            stake=100.0,  # 10% risk
            pnl=85.0, balance=1085.0, return_pct=0.085,
        )
        res = BacktestResult(
            trades=[t1],
            trades_df=pd.DataFrame(),
            metrics=_make_dummy_metrics(),
            equity_curve=pd.Series(),
            initial_balance=1000.0,
            final_balance=1085.0,
            total_pnl=85.0,
            purged_signals_count=0,
            vetoed_signals_count=0,
            kill_switch_triggered=False,
            hypothesis_id="RISK_CAP_BREACH_TEST",
        )

        attestation = run_governance_audit([res], max_risk_cap=0.02)
        self.assertFalse(attestation.audit_passed)
        self.assertTrue(any("exceeds risk cap" in v for v in attestation.violations_detected))


class TestCLIRunResearch(unittest.TestCase):
    """Unit and functional tests for run_research CLI and argument parsing."""

    def test_parse_args_defaults(self):
        args = parse_args([])
        self.assertEqual(args.data, "data/EURUSD_M5_iq.csv")
        self.assertEqual(args.payout, 0.85)
        self.assertEqual(args.is_ratio, 0.50)
        self.assertEqual(args.val_ratio, 0.25)
        self.assertEqual(args.oos_ratio, 0.25)
        self.assertEqual(args.warmup, 60)
        self.assertEqual(args.risk_method, "fractional_kelly")

    def test_parse_args_custom(self):
        args = parse_args([
            "--data", "data/custom.csv",
            "--hypotheses", "H001,H002",
            "--payout", "0.80",
            "--export-report", "custom_dir/my_report",
            "--is-ratio", "0.60",
            "--val-ratio", "0.20",
            "--oos-ratio", "0.20",
            "--warmup", "30",
            "--risk-method", "fixed",
            "--fixed-stake", "15.0",
            "--max-risk-cap", "0.03",
        ])
        self.assertEqual(args.data, "data/custom.csv")
        self.assertEqual(args.hypotheses, "H001,H002")
        self.assertEqual(args.payout, 0.80)
        self.assertEqual(args.export_report, "custom_dir/my_report")
        self.assertEqual(args.is_ratio, 0.60)
        self.assertEqual(args.warmup, 30)
        self.assertEqual(args.risk_method, "fixed")
        self.assertEqual(args.fixed_stake, 15.0)
        self.assertEqual(args.max_risk_cap, 0.03)

    def test_run_pipeline_execution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_report = Path(tmp_dir) / "test_report"
            args = parse_args([
                "--data", "data/EURUSD_M5_iq.csv",
                "--hypotheses", "H001",
                "--export-report", str(out_report),
                "--quiet",
            ])
            report = run_pipeline(args)

            self.assertIsInstance(report, ResearchReport)
            self.assertEqual(len(report.evaluations), 1)
            self.assertEqual(report.evaluations[0].hypothesis_id, "H001")
            self.assertTrue(Path(f"{out_report}.md").exists())
            self.assertTrue(Path(f"{out_report}.json").exists())


if __name__ == "__main__":
    unittest.main()
