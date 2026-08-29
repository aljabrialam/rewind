# Quickstart: Critic Evaluation and Promotion

---

## Run offline

```bash
pytest tests/unit/test_critic.py -q
```

Green, sub-second. `FakeProvider` + a canned/fixture critic — evidence bundle,
verdict rejection → fallback, promotion, write-once record, all-failed totality,
second round, loser releases.

## Live contract (needs DAYTONA_API_KEY + LLM_API_KEY)

```bash
pytest tests/contract/test_critic_contract.py -m live -q
```

Ordered provider calls `branch×1, destroy×(N-1)` match the fake; round completes
within `CRITIC_WAIT` + margin.

## See the loop close

```bash
FAKE=1 python demo.py       # steps → fail → fan-out → JUDGE + PROMOTE → restore
```

The branch beat now prints the verdict reason and whether the fallback was used.

---

## FR / NFR / SC → named-test matrix

Unit in `tests/unit/test_critic.py` (`cr`); live in `tests/contract/test_critic_contract.py` (`live`).

| Requirement | Named test |
|---|---|
| FR-005-01 evidence to the critic, not self-description | `cr::test_bundle_is_evidence_only` (contains exit codes, contains no branch rationale) — SC-001 |
| FR-005-02 structured verdict: chosen + score-per-branch + reason | `cr::test_valid_verdict_accepted`, `cr::test_reason_required` |
| FR-005-03 reject unknown branch / missing score / bad structure / no-snapshot branch | `cr::test_reject_unknown_branch`, `cr::test_reject_missing_score`, `cr::test_reject_no_snapshot_branch`, `cr::test_reject_bad_structure` — SC-002 |
| FR-005-04 promote chosen to head; headless-safe on re-derive failure | `cr::test_winner_becomes_head`, `cr::test_headless_safe_on_rederive_failure` — SC-003 |
| FR-005-05 losers released + marked; idempotent; continue-on-failure; classified | `cr::test_losers_released_and_marked`, `cr::test_release_is_idempotent`, `cr::test_release_continues_after_one_failure` — SC-009 |
| FR-005-06 verdict recorded on the parent, write-once | `cr::test_verdict_recorded_on_parent`, `cr::test_verdict_record_is_write_once` — SC-007 |
| FR-005-07 fallback on unavailable / timeout / rejected; records it | `cr::test_fallback_on_unreachable_critic`, `cr::test_fallback_on_timeout`, `cr::test_fallback_on_rejected_verdict`, `cr::test_fallback_flag_recorded` — SC-005 |
| FR-005-08 promoted head is a valid fan-out origin; loser is not | `cr::test_second_round_from_promoted_head`, `cr::test_fanout_from_loser_refused` — SC-008 |
| FR-005-09 no scoring a still-running branch | `cr::test_still_running_branch_excluded` |
| FR-005-10 empty set refused; single branch promoted without a verdict | `cr::test_empty_set_refused`, `cr::test_single_branch_promoted_no_verdict` |
| NFR-005-01 verdict reproducible from a fixture | `cr::test_replayed_verdict_is_reproducible` — SC-011 |
| NFR-005-02 fallback pure + total (all-failed) | `cr::test_rank_is_total_over_all_failed`, `cr::test_rank_is_pure`, `cr::test_rank_tie_break_is_deterministic` — SC-006 |
| NFR-005-03 critic + fallback within a bounded time | `cr::test_timeout_returns_within_bound` — SC-010 |
| NFR-005-04 identical ordered calls live vs fake | `cr::test_provider_call_counts` + `live::test_call_counts_match_live` |

| Success criterion | Verified by |
|---|---|
| SC-001 | `cr::test_bundle_is_evidence_only` |
| SC-002 | `cr::test_reject_*` |
| SC-003 | `cr::test_winner_becomes_head`, `cr::test_losers_released_and_marked` |
| SC-004 | `cr::test_tree_intact_after_promotion` (integrity `[]`, loser fields preserved) |
| SC-005 | `cr::test_fallback_flag_recorded` |
| SC-006 | `cr::test_rank_is_total_over_all_failed` |
| SC-007 | `cr::test_verdict_record_is_write_once` |
| SC-008 | `cr::test_second_round_from_promoted_head` |
| SC-009 | `cr::test_release_continues_after_one_failure` |
| SC-010 | `cr::test_timeout_returns_within_bound` |
| SC-011 | `cr::test_replayed_verdict_is_reproducible` |

---

## Gate checkpoints

- **G2**: `pytest tests/unit/test_critic.py -q` green; the live contract green within `CRITIC_WAIT` + margin.
- **G3**: re-run the live contract; capture `fixtures/reasoning/critic-*.json`; no further edits to `Engine.evaluate` / `promote` / `rank_by_evidence`.
- **Article IX**: this feature closes the loop — record it in `docs/gates.md`.
