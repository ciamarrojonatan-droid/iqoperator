# BRIEFING — 2026-09-28T23:38:30-03:00

## Mission
Lead the team to build the Quantitative Research Architecture (Backtest & Signal Engine) for Binary Options (IQ Option) focused on R1 (Regime-Adaptive Engine), R2 (Expiry & Payout Conditional Pipeline with EV & Wilson Lower Bound), and R3 (Out-of-Sample Stability across H001-H008).

## 🔒 My Identity
- Archetype: orchestrator
- Roles: orchestrator, user_liaison, human_reporter, successor
- Working directory: c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\orchestrator_2\
- Original parent: caller (Sentinel)
- Original parent conversation ID: 1729a41f-ff4b-4f6c-b78c-5b2eaef066d7

## 🔒 My Workflow
- **Pattern**: Project
- **Scope document**: c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\PROJECT.md
1. **Decompose**: Survey codebase/specs via 3 Explorers, create feature inventory and milestone breakdown (Implementation + E2E Testing tracks).
2. **Dispatch & Execute**:
   - **Direct (iteration loop)**: For each milestone: Explorer(s) -> Worker -> Reviewers + Challengers + Auditor -> Gate check.
   - **Delegate (sub-orchestrator)**: Spawn sub-orchestrators for milestones or test tracks if needed.
3. **On failure** (in this order):
   - Retry: nudge stuck agent or re-send task
   - Replace: spawn fresh agent with partial progress
   - Skip: proceed without (only if non-essential)
   - Redistribute: split stuck agent's remaining work
   - Redesign: re-partition decomposition
   - Escalate: report to parent (sub-orchestrators only, last resort)
4. **Succession**: At 16 spawns, write handoff.md, spawn successor.
- **Work items**:
  1. Survey and Scope Mapping [in-progress]
  2. Project Architecture & Milestone Decomposition [pending]
  3. Milestone 1 Implementation & Test Track [pending]
  4. Milestones Execution [pending]
  5. E2E Verification & Forensic Integrity Gate [pending]
- **Current phase**: 0 (Survey)
- **Current focus**: Awaiting survey reports from 3 Survey Explorers

## 🔒 Key Constraints
- NEVER write, modify, or create source code files directly.
- NEVER run build/test commands yourself — require workers to do so.
- NEVER investigate or explore the problem at the code level — dispatch Explorers for technical investigation.
- You MAY use file-editing tools ONLY for metadata/state files (.md) in your .agents/teamwork/ folder.
- Hard audit enforcement: Binary veto on integrity violation.
- Zero martingale / irrational asymmetric allocation dependencies.
- Never reuse a subagent after it has delivered its handoff — always spawn fresh.
- URGENT DIRECTIVE (2026-09-29): PROIBIDO usar `cat`, `Get-Content` ou ferramentas de leitura completa de arquivos (`view_file` completo) que gastem muitos tokens. Todos os agentes devem usar preferencialmente o sidecar (daemon) do Hypervisor para auditar e extrair código: `python -m synaptic_hypervisor.sidecar.daemon --action extract_edges --file <arquivo>`.

## Current Parent
- Conversation ID: 1729a41f-ff4b-4f6c-b78c-5b2eaef066d7
- Updated: not yet

## Key Decisions Made
- Heartbeat cron started (task-14).
- Dispatched 3 parallel Survey Explorers for codebase, quantitative formulations, and backtesting/OOS stability.

## Team Roster
| Agent | Type | Work Item | Status | Conv ID |
|-------|------|-----------|--------|---------|
| explorer_survey_iq_1 | teamwork_preview_explorer | Codebase and Data Survey | completed | 701b6540-01c3-4092-baa5-d5082ecd6635 |
| explorer_survey_iq_2 | teamwork_preview_explorer | Quantitative Formulation Survey | completed | 339a64f0-b891-4931-b03b-3a1ce0a90031 |
| explorer_survey_iq_3 | teamwork_preview_explorer | Backtest & OOS Stability Survey | completed | 354c3a86-fcbb-4968-a32b-54387e3a7f8b |
| worker_m1_engine | teamwork_preview_worker | M1 Engine & Pipeline Implementation | completed | 7125b057-5965-47d3-8cf3-4452d0303ad7 |
| test_writer_e2e | teamwork_preview_test_writer | E2E Test Suite & TEST_READY Design | completed | d5db010b-fd79-4c51-9299-d5792e45fa06 |
| reviewer_m1_1 | teamwork_preview_reviewer | R1 Feature Engine Technical Review | in-progress | 9f9087ea-2d09-499b-b84f-44025ce688a5 |
| reviewer_m1_2 | teamwork_preview_reviewer | R2 Payout Pipeline Technical Review | in-progress | c1cf0635-9422-4019-8494-36b88fb253db |
| challenger_m1_1 | teamwork_preview_challenger | R1 Feature Engine Stress Testing | in-progress | d54f0377-b63e-46c5-81e2-63cd7af0279e |
| challenger_m1_2 | teamwork_preview_challenger | R2 Payout Pipeline Stress Testing | in-progress | 34068350-71b7-43d9-a6de-e5637f1342f3 |
| auditor_m1_1 | teamwork_preview_auditor | Forensic Integrity Audit M1 | completed | 6bfedf27-ece2-4a22-8fbb-33490d26fa90 |
| worker_m1_remediation | teamwork_preview_worker | Fix 4 Adversarial Defects M1 | completed | 34bc4889-1e19-4328-887c-a023bbcf737e |
| challenger_m1_1_recheck | teamwork_preview_challenger | Re-verify M1 Adversarial Stress Tests | completed | 4440b8cc-10a4-4551-a6a0-c1192a63c0a3 |
| worker_m2_backtest | teamwork_preview_worker | M2 Backtest Engine & H001-H008 Implementation | completed | 2d80ce05-5920-4a48-a763-67f5efbd17b0 |
| worker_m3_reporting | teamwork_preview_worker | M3 Reporting & Research Runner Implementation | completed | 8ebe1529-6467-4db2-b065-c8c71e1994eb |
| reviewer_m3_1 | teamwork_preview_reviewer | M3 Report Generator Review | in-progress | 02d46499-8ef0-407c-9a9e-93d329cab01b |
| reviewer_m3_2 | teamwork_preview_reviewer | M3 Research Runner Review | in-progress | 07226c05-c917-4e03-863f-994627aa0dc6 |
| challenger_m3_1 | teamwork_preview_challenger | M3 CLI & Pipeline Stress Testing | in-progress | a7cdac95-d75a-4b1c-94b1-cd77ec89562b |
| challenger_m3_2 | teamwork_preview_challenger | M3 Acceptance & E2E Stress Testing | in-progress | e89859be-9006-4967-94d4-56f5f8652c22 |
| auditor_m3_1 | teamwork_preview_auditor | Full Architecture Forensic Audit | completed | d63a5986-5232-4a9d-9a4e-981b39b79e84 |
| worker_m3_final_polish | teamwork_preview_worker | M3 Final Polish (cp1252 & test imports) | in-progress | 6beb15d6-9772-415d-959e-de2a899385d8 |

## Succession Status
- Succession required: no (finishing final polish & closeout directly)
- Spawn count: 20 / 128
- Pending subagents: 6beb15d6-9772-415d-959e-de2a899385d8
- Predecessor: none
- Successor: not needed (final closeout)

## Active Timers
- Heartbeat cron: 5300d532-e3aa-4ce2-bdf4-d9b54031954a/task-14
- Safety timer: pending
- On succession: kill all timers before spawning successor
- On context truncation: run `manage_task(Action="list")` — re-create if missing

## Artifact Index
- c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\ORIGINAL_REQUEST.md — Authoritative User Request
- c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\orchestrator_2\DISPATCH.md — Dispatch log
- c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\orchestrator_2\plan.md — Orchestrator plan
- c:\Users\WDAGUtilityAccount\Downloads\Nova pasta\iqoperator\.agents\teamwork\orchestrator_2\progress.md — Liveness & status checkpoint
