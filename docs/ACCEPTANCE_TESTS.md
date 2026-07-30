# ACCEPTANCE TESTS

Every mandatory requirement mapped to an executable test or a deterministic
verification procedure. Rule IDs are Appendix E's own numbering
(see [REQUIREMENTS.md](REQUIREMENTS.md)).

**Verification classes.**

| Class | Meaning |
|---|---|
| `AUTO` | pytest test. Must pass in CI-equivalent local run. |
| `MANUAL` | Deterministic procedure a human executes and records. Used where the check is inherently observational (a screenshot, a public URL, a Moodle form). Every `MANUAL` entry states the exact steps and the exact pass condition — no judgement calls. |
| `PROCESS` | An administrative obligation verified by a checklist item before submission. |

**Naming convention** (D-17): test functions carry the rule ID, e.g.
`test_e13_rejects_diagonal_move`, so coverage is greppable.

**Implementation status.** Configuration, game domain, transport and
cryptography are implemented; the names in `§9`–`§12` are real and
runnable. Everything else remains a specification for the phase that will
implement it.

```bash
python -m pytest
```

---

## 9. Implemented — Phase 0 configuration foundation

214 tests, all passing. Files under `tests/config/`.

| Requirement | Test | Class |
|---|---|---|
| Exactly 32 binding parameters, each once | `test_validation.py::test_exactly_32_binding_parameters`, `::test_each_parameter_appears_exactly_once` | `AUTO` |
| Status split is 14 FIXED / 9 MINIMUM / 9 NEGOTIABLE | `test_validation.py::test_status_distribution_matches_appendix_f` | `AUTO` |
| Only three statuses exist (no DEFAULT, no OPTIONAL) | `test_validation.py::test_only_three_statuses_exist` | `AUTO` |
| Shipped config carries every tabulated value | `test_validation.py::test_shipped_config_carries_every_binding_value` | `AUTO` |
| **E-12** every FIXED accepts its binding value | `test_validation.py::test_fixed_parameter_accepts_the_binding_value` (×14) | `AUTO` |
| **E-12** every FIXED rejects a different value | `test_validation.py::test_fixed_parameter_rejects_a_different_value` (×14) | `AUTO` |
| **E-13/E-14** FIXED `move_set` rejects reordering and diagonals | `test_validation.py::test_fixed_move_set_rejects_a_reordering`, `::test_fixed_move_set_rejects_a_diagonal` | `AUTO` |
| **E-12** every MINIMUM accepts the floor | `test_validation.py::test_minimum_parameter_accepts_the_floor` (×9) | `AUTO` |
| **E-12** every MINIMUM accepts a greater value | `test_validation.py::test_minimum_parameter_accepts_a_greater_value` (×9) | `AUTO` |
| **E-12** every MINIMUM rejects a lower value | `test_validation.py::test_minimum_parameter_rejects_a_lower_value` (×9) | `AUTO` |
| **E-12** `grid_size` below 7 rejected | `test_validation.py::test_grid_size_below_seven_is_rejected` | `AUTO` |
| Raised minimums load end to end | `test_validation.py::test_raised_minimums_survive_full_construction` | `AUTO` |
| Every NEGOTIABLE accepts its default and agreed values | `test_validation.py::test_negotiable_parameter_accepts_the_tabulated_default` (×9), `::test_negotiable_parameter_accepts_an_agreed_value` | `AUTO` |
| NEGOTIABLE domain checks | `test_validation.py::test_negotiable_parameter_rejects_an_out_of_domain_value` | `AUTO` |
| Field names are a closed schema (PDF p. 130) | `test_loader.py::test_renamed_field_is_rejected_not_defaulted`, `::test_unknown_top_level_field_is_rejected`, `::test_unknown_nested_field_is_rejected` | `AUTO` |
| Missing mandatory keys rejected | `test_loader.py::test_missing_top_level_section_is_rejected`, `::test_missing_nested_field_is_rejected`, `::test_missing_structural_field_is_rejected` | `AUTO` |
| Duplicate JSON keys rejected | `test_loader.py::test_duplicate_key_is_rejected`, `::test_duplicate_key_in_nested_object_is_rejected`, `::test_duplicate_key_in_shipped_shape_is_rejected` | `AUTO` |
| Wrong types rejected; bool ≠ int | `test_loader.py::test_wrong_type_is_rejected` (×9), `::test_bool_is_not_accepted_where_an_int_belongs` | `AUTO` |
| Malformed JSON / bad UTF-8 / missing file | `test_loader.py::test_malformed_json_raises_parse_error`, `::test_invalid_utf8_raises_parse_error`, `::test_missing_file_raises_not_found` | `AUTO` |
| Config frozen after validation | `test_loader.py::test_loaded_object_is_frozen` | `AUTO` |
| Canonical JSON: key order irrelevant | `test_canonical.py::test_key_order_does_not_affect_output`, `::test_nested_key_order_does_not_affect_output` | `AUTO` |
| Canonical JSON: whitespace irrelevant | `test_canonical.py::test_source_whitespace_does_not_reach_output` | `AUTO` |
| Canonical JSON: arrays keep order | `test_canonical.py::test_array_order_is_preserved` | `AUTO` |
| Canonical JSON: deterministic, UTF-8 | `test_canonical.py::test_repeated_calls_are_stable`, `::test_non_ascii_is_deterministic_utf8` | `AUTO` |
| Canonical JSON: unsupported values rejected | `test_canonical.py::test_unsupported_values_are_rejected` (×10) | `AUTO` |
| **E-11** hash deterministic, lowercase hex | `test_hashing.py::test_digest_is_lowercase_hex_of_length_64`, `::test_digest_is_stable_across_repeated_calls` | `AUTO` |
| **E-11** hash ignores key order and whitespace | `test_hashing.py::test_key_order_does_not_change_the_digest`, `::test_whitespace_does_not_change_the_digest` | `AUTO` |
| **E-11** hash changes when a binding value changes | `test_hashing.py::test_changing_a_shared_value_changes_the_digest` | `AUTO` |
| **E-11** private config does not affect the hash | `test_hashing.py::test_private_configuration_does_not_affect_the_shared_digest`, `test_verify_cli.py::test_private_config_does_not_change_the_printed_hash` | `AUTO` |
| **E-11** known-hash fixture | `test_hashing.py::test_shipped_config_matches_the_pinned_digest` | `AUTO` |
| **E-11** refuse to play on mismatch | `test_hashing.py::test_verify_rejects_a_mismatched_digest`, `test_verify_cli.py::test_expect_hash_mismatch_refuses_to_play` | `AUTO` |
| Private cop/thief configs load | `test_private.py::test_valid_cop_example_loads`, `::test_valid_thief_example_loads` | `AUTO` |
| Invalid role / port / opponent URL rejected | `test_private.py::test_invalid_role_is_rejected`, `::test_invalid_port_is_rejected` (×4), `::test_invalid_opponent_url_is_rejected` (×4), `::test_missing_opponent_url_is_rejected` | `AUTO` |
| **E-45** 8-character group id | `test_private.py::test_invalid_group_id_is_rejected` (×4), `::test_valid_group_id_is_accepted` | `AUTO` |
| **E-39/E-40** examples carry no secrets, paths only | `test_private.py::test_examples_contain_no_secret_values` | `AUTO` |
| **D-5** examples default to `send`, not `draft` | `test_private.py::test_examples_default_to_send_not_draft` | `AUTO` |
| **D-21** private may not shadow a shared key | `test_private.py::test_private_config_may_not_shadow_a_shared_parameter` (×5) | `AUTO` |
| **E-1** role must match the entry point | `test_private.py::test_role_must_match_the_entry_point` | `AUTO` |
| Cross-field: start cell off the board | `test_validation.py::test_start_cell_outside_the_board_is_rejected` (×2), `::test_negative_start_cell_is_rejected` | `AUTO` |
| Cross-field: identical start cells | `test_validation.py::test_identical_start_cells_are_rejected` | `AUTO` |
| Cross-field: survival unreachable | `test_validation.py::test_survival_threshold_above_max_moves_is_rejected` | `AUTO` |
| Cross-field: barrier quota exceeds board | `test_validation.py::test_barrier_quota_beyond_board_capacity_is_rejected` | `AUTO` |
| Cross-field: scent window off the board | `test_validation.py::test_scent_window_wider_than_the_board_is_rejected` | `AUTO` |
| Cross-field: deadline vs watchdog ordering | `test_validation.py::test_response_timeout_not_shorter_than_watchdog_is_rejected` | `AUTO` |
| CLI: valid config, exit 0, prints hash | `test_verify_cli.py::test_valid_config_exits_zero_and_prints_the_hash` | `AUTO` |
| CLI: deterministic output | `test_verify_cli.py::test_output_is_deterministic_across_runs` | `AUTO` |
| CLI: invalid config exits non-zero | `test_verify_cli.py::test_invalid_shared_config_exits_nonzero`, `::test_missing_file_exits_nonzero` | `AUTO` |
| CLI: no credential contents printed | `test_verify_cli.py::test_no_credential_contents_are_printed` | `AUTO` |

---

## 10. Implemented — Phase 1 game domain

171 tests, all passing. Files under `tests/domain/`.

| Requirement | Test | Class |
|---|---|---|
| **E-13** each direction legal from the interior | `test_movement.py::test_each_direction_is_legal_from_the_board_interior` (×5) | `AUTO` |
| **E-13** `STAY` is a legal action | `test_movement.py::test_stay_is_a_legal_action` | `AUTO` |
| **E-14** diagonals have no representation | `test_movement.py::test_diagonals_have_no_representation` | `AUTO` |
| Moves off the board rejected | `test_movement.py::test_moving_off_the_north_edge_is_rejected`, `::test_moving_off_the_south_edge_is_rejected` | `AUTO` |
| Barriers block both roles | `test_movement.py::test_moving_into_a_barrier_is_rejected`, `::test_barriers_block_the_cop_too` | `AUTO` |
| Move set is read from config, not assumed | `test_movement.py::test_move_outside_the_agreed_move_set_is_rejected` | `AUTO` |
| Legal-action order is deterministic | `test_movement.py::test_legal_moves_have_a_fixed_deterministic_order`, `::test_legal_moves_are_stable_across_repeated_calls` | `AUTO` |
| Generated moves are all genuinely legal | `test_movement.py::test_every_generated_move_is_actually_legal` | `AUTO` |
| Board geometry, bounds, axis convention | `test_board.py::test_board_dimensions_come_from_config`, `::test_board_respects_a_nonzero_axis_start_index`, `::test_shift_follows_the_documented_axis_convention` (×5) | `AUTO` |
| No pre-placed static obstacles exist | `test_board.py::test_board_has_no_barriers_initially` | `AUTO` |
| Deterministic neighbour and placement-target order | `test_board.py::test_neighbours_are_in_fixed_nsew_order`, `::test_placement_targets_are_own_cell_then_neighbours` | `AUTO` |
| **E-15** only the cop may place barriers | `test_barriers.py::test_cop_may_place_a_barrier`, `::test_thief_may_not_place_a_barrier`, `::test_thief_barrier_action_is_rejected_by_the_transition` | `AUTO` |
| Placement within one step; beyond rejected | `test_barriers.py::test_placement_within_one_step_is_legal` (×5), `::test_placement_beyond_one_step_is_rejected` (×5) | `AUTO` |
| Placement inside the board; no overlap | `test_barriers.py::test_placement_outside_the_board_is_rejected`, `::test_placement_on_an_existing_barrier_is_rejected` | `AUTO` |
| Quota enforced from config | `test_barriers.py::test_quota_comes_from_configuration`, `::test_quota_is_enforced`, `::test_placement_decrements_the_remaining_quota` | `AUTO` |
| Placement replaces movement | `test_barriers.py::test_placement_replaces_movement`, `::test_barrier_action_is_a_distinct_action_kind` | `AUTO` |
| Barriers are permanent and block both | `test_barriers.py::test_barrier_is_permanent`, `::test_barrier_blocks_the_placing_cop`, `::test_barrier_blocks_the_thief` | `AUTO` |
| **E-15** placement emits a public declaration | `test_barriers.py::test_placement_emits_a_public_declaration_event` | `AUTO` |
| Illegal placement leaves state untouched | `test_barriers.py::test_illegal_placement_leaves_state_untouched` | `AUTO` |
| **Capture 1** cop lands on the thief | `test_capture.py::test_cop_landing_on_the_thief_is_a_capture`; end-to-end `test_headless_sim.py::test_cop_walks_onto_the_thief_and_captures` | `AUTO` |
| No false capture when cells differ | `test_capture.py::test_no_capture_when_cells_differ`, `::test_adjacent_is_not_captured` | `AUTO` |
| **E-46** barrier on the thief's cell | `test_capture.py::test_barrier_on_the_thief_cell_is_a_capture`; end-to-end `test_headless_sim.py::test_barrier_placed_on_the_thief_cell_captures` | `AUTO` |
| **E-47** thief with no legal move | `test_capture.py::test_thief_walled_in_on_four_sides_is_captured`, `::test_board_edges_count_towards_imprisonment`, `::test_stay_does_not_rescue_a_walled_in_thief`; end-to-end `test_headless_sim.py::test_thief_with_no_legal_move_is_captured` | `AUTO` |
| Capture reason is recorded exactly | `test_capture.py::test_capture_terminal_records_reason_winner_and_turn`, `::test_movement_capture_takes_precedence_over_imprisonment` | `AUTO` |
| **Q-2/Q-9** unresolved cases are isolated | `test_capture.py::test_cell_swap_is_not_a_capture_under_the_default_policy`, `::test_entering_a_vacated_cell_is_not_a_capture_under_the_default_policy`, `::test_thief_moving_onto_the_cop_is_a_capture_under_the_default_policy`, `::test_an_alternative_policy_changes_the_outcome` | `AUTO` |
| Survival fires at the configured threshold | `test_terminal_and_scoring.py::test_survival_fires_at_the_configured_threshold`, `::test_survival_threshold_is_read_from_config_not_hard_coded` | `AUTO` |
| Move ceiling fires at `max_moves` | `test_terminal_and_scoring.py::test_move_ceiling_fires_at_max_moves` | `AUTO` |
| Terminal evaluation is deterministic | `test_terminal_and_scoring.py::test_terminal_results_are_deterministic` | `AUTO` |
| No play after a terminal state | `test_terminal_and_scoring.py::test_no_action_is_possible_after_a_terminal_state`; `test_headless_sim.py::test_no_turn_may_follow_a_terminal_state` | `AUTO` |
| **E-48** capture / survival / technical scores from config | `test_terminal_and_scoring.py::test_capture_scores_come_from_config`, `::test_survival_scores_come_from_config`, `::test_technical_loss_zeroes_both_sides`, `::test_max_moves_is_scored_as_survival` | `AUTO` |
| Scoring asymmetry matches the PDF | `test_terminal_and_scoring.py::test_scoring_is_asymmetric_as_the_pdf_intends` | `AUTO` |
| Every terminal reason is scored | `test_terminal_and_scoring.py::test_scoring_rejects_nothing_it_should_score` | `AUTO` |
| Tie rule is match-level, not sub-game | `test_terminal_and_scoring.py::test_tie_rule_awards_tie_score_to_both_sides`, `::test_tie_is_not_a_sub_game_terminal_reason` | `AUTO` |
| Transition determinism and purity | `test_transition.py::test_same_input_produces_the_same_output`, `::test_input_state_is_not_mutated`, `::test_a_sequence_of_transitions_is_reproducible` | `AUTO` |
| Illegal action never partially modifies state | `test_transition.py::test_illegal_action_does_not_partially_modify_state` (×2), `::test_blocked_move_does_not_modify_state` | `AUTO` |
| Events are deterministic and ordered | `test_transition.py::test_events_are_deterministic_and_ordered` | `AUTO` |
| Transition has no opponent parameter | `test_transition.py::test_transition_has_no_opponent_parameter` | `AUTO` |
| **E-9** `LocalState` field set is exhaustive | `test_information_boundary.py::test_local_state_fields_are_exactly_the_legal_set` | `AUTO` |
| **E-9** forbidden field names absent | `test_information_boundary.py::test_forbidden_field_names_are_absent` (×11) | `AUTO` |
| **E-9** attribute cannot be attached at runtime | `test_information_boundary.py::test_opponent_position_attribute_does_not_exist`, `::test_slots_prevent_attaching_an_opponent_position_at_runtime`, `::test_local_state_has_no_dict_to_smuggle_fields_into` | `AUTO` |
| **E-9** serialisation carries no opponent position | `test_information_boundary.py::test_serialisation_contains_no_opponent_position`, `::test_serialised_cop_state_does_not_encode_the_thief_cell`, `::test_serialised_state_exposes_only_legal_keys` | `AUTO` |
| **E-9** public API offers no global truth | `test_information_boundary.py::test_no_domain_function_offers_global_truth`, `::test_capture_functions_are_not_methods_on_local_state` | `AUTO` |
| Barriers are public *legitimately* | `test_information_boundary.py::test_barriers_are_public_and_that_is_legitimate` | `AUTO` |
| Harness omniscience is a separate type | `test_information_boundary.py::test_harness_is_a_distinct_type_from_local_state`, `::test_harness_omniscience_never_enters_either_state`, `::test_sim_package_is_documented_as_test_only` | `AUTO` |
| Leak inspection over a played sub-game | `test_information_boundary.py::test_leak_inspection_over_a_whole_played_sub_game` | `AUTO` |
| Full sub-game completes and terminates | `test_headless_sim.py::test_full_sub_game_completes_and_terminates`, `::test_two_passive_agents_reach_the_survival_threshold` | `AUTO` |
| Simulation is bounded; no infinite loop | `test_headless_sim.py::test_simulation_is_bounded_by_the_configured_ceiling`, `::test_simulation_terminates_on_a_short_configuration` | `AUTO` |
| Every applied action was legal | `test_headless_sim.py::test_every_applied_action_was_legal` | `AUTO` |
| The run is reproducible | `test_headless_sim.py::test_the_run_is_reproducible`, `::test_headless_cli_is_deterministic` | `AUTO` |
| Role states remain separate objects | `test_headless_sim.py::test_states_remain_separate_objects` | `AUTO` |
| Correct final score on capture | `test_headless_sim.py::test_capture_scores_the_configured_amounts` | `AUTO` |

---

## 11. Implemented — Phase 2 transport and handshake

331 tests under `tests/protocol/` and `tests/peer/`. Real-process integration
is demonstrated by `scripts/run_two_peers.py` (READY, delayed start, config
mismatch, peer unavailable) rather than by pytest, since it requires two OS
processes and real sockets.

| Requirement | Test | Class |
|---|---|---|
| Valid envelope round-trips | `test_messages.py::test_valid_message_round_trips` | `AUTO` |
| Closed envelope schema — every key required, none extra | `test_messages.py::test_missing_envelope_field_is_rejected` (×10), `::test_unknown_envelope_field_is_rejected` | `AUTO` |
| Unsupported schema / protocol versions rejected | `test_messages.py::test_unsupported_schema_version_is_rejected`, `::test_incompatible_protocol_version_is_rejected`, `::test_minor_protocol_differences_are_compatible` | `AUTO` |
| Unknown message type / role rejected | `test_messages.py::test_unknown_message_type_is_rejected`, `::test_unknown_role_is_rejected` | `AUTO` |
| Closed payload schemas per type | `test_messages.py::test_unknown_payload_field_is_rejected`, `::test_missing_payload_field_is_rejected`, `::test_wrong_payload_type_is_rejected` | `AUTO` |
| Deterministic canonical encoding; single serialiser | `test_codec.py::test_encoding_is_deterministic`, `::test_encoding_is_canonical_sorted_and_compact`, `::test_codec_uses_the_single_canonical_implementation` | `AUTO` |
| Malformed JSON / UTF-8 rejected; no pickle/eval | `test_codec.py::test_malformed_json_is_rejected`, `::test_non_utf8_is_rejected`, `::test_codec_does_not_deserialise_arbitrary_objects` | `AUTO` |
| **E-29** bounded message size, checked before parsing | `test_codec.py::test_oversized_message_is_rejected_before_parsing`, `::test_oversized_encode_is_rejected` | `AUTO` |
| Action codec: MOVE/STAY/PLACE_BARRIER round-trip, versioned, role-free, closed | `test_action_codec.py` (16 tests incl. `::test_codec_accepts_no_hidden_state_field`) | `AUTO` |
| **E-4** every declared transition accepted | `test_states.py::test_every_declared_transition_is_accepted` (×37) | `AUTO` |
| **E-5** every undeclared transition rejected, state unchanged | `test_states.py::test_every_undeclared_transition_is_rejected` (×119) | `AUTO` |
| Terminal-state immutability; idempotent re-entry; deterministic history | `test_states.py::test_terminal_state_is_immutable`, `::test_repeating_a_transition_is_idempotent_and_does_not_duplicate_history`, `::test_transition_log_is_deterministic_and_timestamped` | `AUTO` |
| No direct state assignment | `test_states.py::test_state_cannot_be_assigned_from_outside` | `AUTO` |
| **E-11** matching hash accepted; both peers agree | `test_orchestrator.py::test_both_peers_reach_ready`, `::test_both_peers_agree_on_the_config_hash` | `AUTO` |
| **E-11** mismatching hash refused; no turns begin | `test_orchestrator.py::test_config_mismatch_is_rejected_and_no_turns_begin`; real-process demo | `AUTO` + `MANUAL` |
| Wrong game id / same-role sender / wrong receiver rejected | `test_orchestrator.py::test_wrong_game_id_is_rejected`, `::test_same_role_opponent_is_rejected`, `::test_message_addressed_elsewhere_is_rejected` | `AUTO` |
| Missing mandatory capability rejected | `test_orchestrator.py::test_missing_mandatory_capability_is_rejected` | `AUTO` |
| Exact duplicate → same acknowledgement; conflict → rejected | `test_orchestrator.py::test_exact_duplicate_returns_the_same_acknowledgement`, `::test_conflicting_duplicate_is_rejected`; unit detail in `test_registry.py` (11 tests) | `AUTO` |
| Registry bounded at `queue_depth`; eviction policy | `test_registry.py::test_registry_is_bounded_and_evicts_oldest_first`, `::test_memory_stays_bounded_under_sustained_load`, `::test_capacity_comes_from_queue_depth` | `AUTO` |
| **E-28** rate limit, concurrency, queue capacity enforced; slot released on exception; fake-clock refill | `test_gatekeeper_and_deadline.py` (12 gatekeeper tests) | `AUTO` |
| **E-6** deadline; bounded retry; backoff; non-retryable not retried; cancellation | `test_gatekeeper_and_deadline.py` (7 deadline tests) | `AUTO` |
| **E-7** watchdog fires once after configured silence | `test_gatekeeper_and_deadline.py` (5 watchdog tests) | `AUTO` |
| Orchestrator lifecycle: READY, failed handshake, unavailable peer, clean shutdown | `test_orchestrator.py` (remaining), `test_server_and_client.py::test_real_client_completes_a_handshake_over_in_memory_transport` | `AUTO` |
| Retries preserve the message id | `test_server_and_client.py::test_retries_preserve_the_message_id` | `AUTO` |
| Server never mutates LocalState | `test_server_and_client.py::test_server_never_mutates_local_state` | `AUTO` |
| **E-9** no wire schema carries a position; none can be smuggled | `test_information_boundary.py::test_no_payload_schema_accepts_a_position`, `::test_a_position_cannot_be_smuggled_into_any_payload` (×9) | `AUTO` |
| **E-9** handshake bytes inspected; LocalState untouched | `test_information_boundary.py::test_no_handshake_message_carries_game_information`, `::test_handshake_does_not_change_local_state` | `AUTO` |
| **E-3** transport imports no game logic; orchestrator no strategy/scoring | `test_information_boundary.py::test_transport_layer_does_not_import_game_logic`, `::test_orchestrator_does_not_import_strategy_or_scoring` | `AUTO` |
| No central referee: nothing outside sim/ holds both states | `test_information_boundary.py::test_no_module_holds_both_peers_states`, `::test_capture_takes_positions_as_parameters_not_stored_state` | `AUTO` |
| Private config never transmitted; hash unaffected by it | `test_information_boundary.py::test_private_configuration_is_never_transmitted`, `::test_private_config_does_not_affect_the_config_hash` | `AUTO` |
| **E-39/E-9** event sink refuses secrets and positions, at depth | `test_information_boundary.py::test_event_sink_refuses_to_log_a_secret`, `::test_event_sink_refuses_to_log_an_opponent_position`, `::test_event_sink_checks_nested_structures` | `AUTO` |
| Two real processes reach READY; delayed start; mismatch; unavailable; clean shutdown | `scripts/run_two_peers.py` runs, recorded in COMPLIANCE evidence | `MANUAL` |

---

Everything below remains a specification for a later phase.

---

## 1. Network architecture and decentralisation

| Rule | Requirement | Class | Verification |
|---|---|---|---|
| E-1 | Cop and thief in two entirely separate processes | `AUTO` + `MANUAL` | **AUTO:** `test_e1_peers_have_no_shared_module_state` — import both role runtimes in one interpreter, instantiate both, mutate one's state, assert the other is unchanged; assert no module-level mutable singletons via a registry scan. **MANUAL:** launch both peers per README; `Get-Process python` shows two distinct PIDs; both play a full sub-game. |
| E-2 | No shared memory or variables between sides | `AUTO` | `test_e2_no_cross_role_imports` — walk `src/police_thief`, assert no module imports another role's runtime and no module holds live game state at module scope. `test_e2_state_objects_are_independent` — deep-compare two role states after divergent mutation. |
| E-3 | Orchestrator is the single entry point | `AUTO` | `test_e3_subsystems_reachable_only_via_orchestrator` — assert the five sub-systems (MCP connector, decision, log, deadline, watchdog) hold no references to each other; assert each is constructed by the orchestrator. |
| E-4 | Game states managed by a proper state machine | `AUTO` | `test_e4_legal_turn_cycle_completes` — drive the full cycle `WAITING_FOR_OPPONENT → COMPUTING_MOVE → COMMITTING → AWAITING_REVEAL → VERIFYING → WAITING_FOR_OPPONENT` and assert each transition is accepted. |
| E-5 | Reject every illegal state transition | `AUTO` | `test_e5_rejects_illegal_transition` — for every (state, target) pair **not** in the transition table, assert it raises and **assert the phase is unchanged after the rejection**. |
| E-6 | Deadline tracking prevents freeze | `AUTO` | `test_e6_request_deadline_expires` — mock a peer that never responds; assert the call aborts at `response_timeout_sec`, retries `max_retries` times with `retry_backoff_sec` spacing, then transitions to `TECHNICAL_LOSS`. Use a fake clock, not `sleep`. |
| E-7 | Watchdog monitors crashes, extracts data | `AUTO` | `test_e7_watchdog_detects_stall` — advance a fake clock past `watchdog_timeout_sec` with no heartbeat; assert controlled shutdown fired and state was persisted. `test_e7_partial_jsonl_is_readable` — truncate a JSONL log mid-line; assert all complete lines still parse. |
| E-8 | Live GUI displays local truth only | `AUTO` | `test_e8_gui_has_no_opponent_truth_handle` — assert the GUI object graph reaches only local-truth and belief modules; assert no path from GUI to the network layer's decoded opponent state. |
| E-9 | Never display the full objective board state | `AUTO` | `test_e9_live_state_has_no_opponent_position` — assert `LocalState` has **no attribute** for the opponent's position (D-9); assert `getattr` raises. `test_e9_render_model_excludes_truth` — snapshot the GUI's render model; assert opponent's true cell appears nowhere. |
| E-10 | Tunnelling tool exposes server publicly | `MANUAL` | Start peer; start tunnel (`ngrok http <port>`); from a **different machine or network**, call the `hello` tool against the public URL and receive `ok:true`. Pass condition: successful handshake from off-host. Record the URL and timestamp in the match declaration. |

---

## 2. Spatial mechanics and board constraints

| Rule | Requirement | Class | Verification |
|---|---|---|---|
| E-11 | Config identical byte-for-byte on both sides | `AUTO` | `test_e11_config_hash_matches` — canonical-hash the same file loaded twice, assert equal. `test_e11_refuses_play_on_mismatch` — handshake with a peer whose `config_sha256` differs by one byte; assert `ERR_CONFIG_MISMATCH` and that **no sub-game starts**. |
| E-12 | Raise minimums only by agreement; never lower | `AUTO` | `test_e12_rejects_lowered_minimum` — parametrised over every MINIMUM parameter; load a config with the value one below the table and assert the validator rejects it. `test_e12_accepts_raised_minimum` — assert a raised value loads. `test_e12_rejects_altered_fixed` — parametrised over every FIXED parameter; assert any change is rejected. |
| — | Field names are a closed schema (PDF p. 130) | `AUTO` | `test_config_rejects_renamed_key` — rename `grid_size` to `gridSize`; assert the loader **rejects** rather than defaulting. `test_config_rejects_unknown_key` — assert an extra key is rejected, not ignored. |
| — | Both sides agree the same transition function (PDF p. 21) | `AUTO` | `test_transition_function_derives_only_from_shared_config` — assert the physics engine reads every rule from the shared config object and holds no private movement state, so equal configs imply identical transitions. |
| E-13 | Move only orthogonally | `AUTO` | `test_e13_accepts_orthogonal_and_stay` — assert all of `move_set` are legal from an interior cell. |
| E-14 | No diagonal moves | `AUTO` | `test_e14_rejects_diagonal_move` — submit a diagonal in `reveal`; assert `ERR_ILLEGAL_MOVE` and that the board state is unchanged. |
| E-15 | Declare every barrier placement openly | `AUTO` | `test_e15_barrier_appears_in_reveal_and_log` — place a barrier; assert the reveal payload carries the exact cell and the log records it. `test_e15_rejects_undeclared_barrier` — assert a board diff showing an undeclared barrier is rejected at audit. |
| E-16 | Never lie about barrier location | `AUTO` | `test_e16_barrier_cell_is_sealed_in_commit` — assert the barrier cell is inside the committed record, so a later inconsistency breaks the hash at audit. |
| E-46 | Barrier on the thief's cell counts as capture | `AUTO` | `test_e46_barrier_on_thief_is_capture` — cop forgoes movement and places on the thief's cell; assert terminal state is capture with `capture_cop` / `capture_thief`. |
| E-47 | Thief with no legal move is captured | `AUTO` | `test_e47_enclosed_thief_is_captured` — construct a board where all four neighbours are barriers/edges; assert capture. Include the board-corner case where edges alone enclose. |
| E-48 | Score every end scenario per the tables | `AUTO` | `test_e48_scoring_matrix` — parametrised over capture / survival / technical loss; assert exact scores from config, never literals. |
| — | Barrier quota respected | `AUTO` | `test_barrier_quota_enforced` — attempt placement number `max_barriers + 1`; assert rejection. |
| — | Barrier is irreversible and blocks both | `AUTO` | `test_barrier_permanent_and_blocks_both` — assert neither role may enter a blocked cell, for the remainder of the sub-game. |
| — | Barrier only within one step, only when forgoing movement | `AUTO` | `test_barrier_placement_constraints` — assert placement two cells away is rejected, and placement combined with a move is rejected. |

---

## 3. Cryptography and log integrity

| Rule | Requirement | Class | Verification |
|---|---|---|---|
| E-17 | Commit-reveal over SHA-256 | `AUTO` | `test_e17_commit_then_reveal_verifies` — full round trip; assert the recomputed canonical hash equals the declared commitment. `test_e17_uses_sha256` — assert digest length 64 hex and matches `hashlib.sha256` of the canonical payload. |
| E-18 | Nonce secret until end of match | `AUTO` | `test_e18_reveal_payload_omits_nonce` — assert the `reveal` schema **rejects** a nonce field and that no nonce appears in any wire payload before `final_reveal`. `test_e18_nonce_is_cryptographic` — assert generation uses `secrets`, not `random`, and is ≥128 bits. |
| E-19 | Technical loss on any audit hash mismatch | `AUTO` | `test_e19_tampered_log_is_rejected` — take a valid log, flip one character of one move; assert audit returns mismatch, the offending entry is identified, and the outcome is technical loss with score 0 for the forger. Parametrise the tamper across move, hint, intent, state and step. |
| E-20 | Replay viewer application exists | `AUTO` + `MANUAL` | **AUTO:** `test_e20_verifier_verified_ok_on_clean_log`, `test_e20_verifier_tampered_on_dirty_log`. **MANUAL:** launch `python -m police_thief replay --log matches/<id>/log_<id>_g01.json`; step forward and backward; observe green `Verified OK`. Pass condition: screenshot captured for the README (also a submission requirement). |
| E-21 | Declare truth only on capture | `AUTO` | `test_e21_thief_must_answer_capture_truthfully` — assert the thief's response is sealed in its commitment, so a false denial breaks the hash at audit. |
| E-22 | Never falsely declare a capture | `AUTO` | `test_e22_false_capture_claim_detected` — cop claims capture while positions differ in the log; assert audit flags it and the outcome is immediate disqualification. |
| E-23 | Cryptographically lock the scent model pre-match | `AUTO` | `test_e23_scent_model_hash_exchanged` — assert `hello` carries `scent_model_sha256` covering formula **and** the numeric example. `test_e23_refuses_on_model_mismatch` — differing ρ ⇒ refuse to play. `test_e23_worked_example` — assert τ=0.9 decays to 0.81 after one turn at ρ=0.10. |
| E-24 | Cryptographic hardware declaration pre-match | `AUTO` | `test_e24_step_zero_precedes_step_one` — assert no `commit` is accepted before both `declare` messages. `test_e24_declaration_sealed` — assert the declaration hash is stable and recorded. |
| E-53 | Step-0 records the commit hash played | `AUTO` | `test_e53_declaration_carries_commit_hash` — assert `github_commit` is present, non-empty, and hex; assert it also lands in `[declaration_file]` and `[result_file]`. |
| — | Canonical serialisation is byte-identical | `AUTO` | `test_canonical_json_is_key_order_independent` — build the same record with keys in different insertion orders; assert identical bytes and identical hash. |
| — | Log carries every mandatory field (PDF p. 94) | `AUTO` | `test_log_record_schema` — assert each step record carries commitment, move, hint, **LLM discussion fields**, nonce slot and hash; assert `llm.tokens_in/out` present even in `template` mode (0, not absent). |
| — | Log is sufficient for independent replay | `AUTO` | `test_log_alone_reconstructs_match` — hand the verifier only the log + config; assert it re-derives both trajectories, the barrier set, the scent field and the outcome, with no field supplying a position directly. |
| — | Live log contains no nonce | `AUTO` | `test_live_log_nonce_null_until_final_reveal` — assert every `nonce` is null in the live JSONL and populated only after `final_reveal` (E-18). |
| — | Scent field is never persisted | `AUTO` | `test_log_has_no_scent_field` — assert no rendered scent grid appears anywhere in the sealed log (D-19: storing it would put global truth in the live path). |

---

## 4. Scent physics

| Requirement | Class | Verification |
|---|---|---|
| Emission window `pheromone_grid_size` with centre `pheromone_center_intensity`, radial falloff | `AUTO` | `test_scent_emission_field_shape` — assert window side equals config, centre equals config, and intensity is non-increasing with Chebyshev/radial distance from centre. |
| Decay rule `τ(t+1) = max(0, (1−ρ)·τ(t) + Δτ)` | `AUTO` | `test_scent_decay_formula` — assert exact arithmetic against hand-computed values; assert the clamp holds (never negative). |
| Decay applied once per **full** turn, after both moves | `AUTO` | `test_scent_decays_once_per_full_turn` — run one full turn; assert exactly one decay pass was applied, not two. |
| Each peer reads only the **opponent's** field | `AUTO` | `test_peer_reads_only_opponent_scent` — assert the observation object exposes the opponent's field and that the peer's own emitted field is not part of its observation input. |
| Scent cannot be forged | `AUTO` | `test_scent_emitted_only_at_own_position` — assert the API offers no way to deposit scent at a non-occupied cell. |

---

## 5. Strategy, language and network protection

| Rule | Requirement | Class | Verification |
|---|---|---|---|
| E-25 (**RECOMMENDED**) | LLM does not decide the move | `AUTO` | `test_e25_move_decided_without_llm` — run a full sub-game with a verbal provider that raises on any call requiring a move; assert the game completes. `test_e25_llm_interface_surface` — assert the verbal module exposes only *produce hint* and *classify hint*. |
| E-26 | Free natural language only | `AUTO` | `test_e26_hint_is_natural_language` — assert generated hints contain no coordinate encodings and are within `hint_max_words`. |
| E-27 | No direct numeric position protocols | `AUTO` | `test_e27_rejects_numeric_position_hint` — parametrised over `"3,4"`, `"(3,4)"`, `"[3,4]"`, `"row=3 col=4"`, `"B4"`; assert `ERR_ILLEGAL_HINT`. `test_e27_wire_schema_has_no_position_field` — assert no protocol message carries the sender's own position. |
| E-28 | Token-bucket rate limiter for Gmail | `AUTO` | `test_e28_token_bucket_rule` — assert `tokens ← min(C, tokens + r·Δt)` and `allow ⟺ tokens ≥ 1` against a fake clock; assert a burst beyond capacity is blocked and recovers after quiet time. |
| E-29 | DOS detector | `AUTO` | `test_e29_dos_detector_locks_pipe` — simulate a send loop; assert the gatekeeper locks and **all** subsequent sends are refused until reset. |
| E-30 | Send-only Gmail permission | `AUTO` | `test_e30_scope_is_send_only` — assert the scope constant is exactly `https://www.googleapis.com/auth/gmail.send` and that no read/modify scope appears anywhere in the source. |
| — | Gatekeeper order: quota → bucket → DOS | `AUTO` | `test_gatekeeper_fail_fast_order` — assert a quota failure short-circuits before the bucket is consulted. |
| — | 429 triggers backoff, not immediate retry | `AUTO` | `test_429_backs_off` — mock a 429; assert the sender waits and does not immediately resend. |

---

## 6. League, reporting and administration

| Rule | Requirement | Class | Verification |
|---|---|---|---|
| E-31 | Minimum matches vs different groups | `PROCESS` | Before submission: `matches/` contains ≥ `min_games_to_pass` completed counting matches against **distinct** `group_id` values. `AUTO`: `test_e31_counting_matches_distinct_opponents` over the artefact directory. |
| E-32 | Automatic result reporting via Gmail | `AUTO` + `MANUAL` | **AUTO:** `test_e32_report_send_invoked_on_completion` — assert match completion triggers exactly one send. **MANUAL:** run a match end-to-end against a test recipient; confirm the message arrives with the JSON attached. |
| E-33 | Report is standard JSON | `AUTO` | `test_e33_result_file_is_valid_json` — assert it parses, validates against the result schema, and contains all mandatory fields (both teams' GitHub links, per-sub-game commit hash, token totals). |
| E-34 | Never free text; JSON attachment only | `AUTO` | `test_e34_report_sent_as_attachment` — assert the MIME message has a JSON attachment and that the body carries no report payload. |
| E-35 | Agree result; each team sends separately | `AUTO` | `test_e35_result_agreement_required_before_send` — assert send is refused until `result_agreement` returns `agreed:true`. `test_e35_contradictory_result_blocks_send` — differing totals ⇒ refuse and log. |
| E-36 | Mutual log audit every match | `AUTO` | `test_e36_audit_runs_before_result_agreement` — assert ordering; assert a failed audit prevents result agreement. |
| E-37 | Declare counted-match count at match start | `AUTO` | `test_e37_hello_carries_games_played` — assert present, integer, and matches the count derivable from `matches/`. |
| E-38 | Never declare falsely | `AUTO` | `test_e38_declared_count_derives_from_artefacts` — assert the value is computed from the artefact store, not hand-set, so it cannot silently diverge. |
| E-39 | Never push secrets | `AUTO` + `PROCESS` | `test_e39_no_secrets_tracked` — assert `git ls-files` matches none of the secret patterns. **PROCESS:** before tagging, run `git log -p | grep` for the patterns across full history. |
| E-40 | Secrets in `.gitignore` | `AUTO` | `test_e40_gitignore_covers_secrets` — assert `.gitignore` matches `credentials.json`, `token.json`, `.env` (via `git check-ignore`, not string search). |
| E-41 | Documented Git tag for submission | `PROCESS` | `git tag -a v1.0-submission -m "…"` then `git push origin v1.0-submission`; verify with `git show v1.0-submission`. Pass condition: annotated tag exists on the remote. |
| E-42 | Comprehensive academic report in repo | `PROCESS` | `README.md` contains all six mandatory components (Ch. 9, PDF p. 97). Checklist in §7 below. |
| E-43 | Moodle form: fill, do not alter fields | `MANUAL` | Download the Word template from Moodle, fill only the data fields, save as PDF, verify no field moved or renamed by diffing against a blank render. |
| E-44 | Each member submits separately in Moodle | `PROCESS` | One Moodle submission per group member, confirmed by each. |
| E-45 | Unique 8-char group code, no spaces | `AUTO` | `test_e45_group_id_format` — assert `len == 8` and `not any(c.isspace())`. |
| E-49 | Two repos, cross-linked, 2 links Moodle, 4 links JSON | `AUTO` + `PROCESS` | `test_e49_result_json_has_four_links` — assert both teams' cop and thief URLs are present. **PROCESS:** verify each repo's README links the other. |
| E-50 | Each repo has README, /config, PRD, PLAN, TODO | `AUTO` | `test_e50_required_repo_files_exist` — assert `README.md`, `prd.md`, `plan.md`, `todo.md`, `config/` (lowercase names, checked on a case-sensitive filesystem). |
| E-51 | Send reports to `[agent_reporting_address]` | `AUTO` | `test_e51_recipient_is_lecturer_address` — assert the configured recipient equals `rmisegal+uoh26finalgame@gmail.com`. |
| E-52 | One counting match per opponent | `AUTO` | `test_e52_one_counting_match_per_opponent` — assert no two counting matches share an opponent `group_id`; assert warm-up matches are flagged and excluded. |
| E-54 | Report total tokens consumed | `AUTO` | `test_e54_tokens_reported` — assert `tokens_used` present per sub-game and in the series total; assert it is 0 in `template` mode rather than absent. |
| E-55 | Self-grade for code quality only | `PROCESS` | Moodle self-grade field reflects code quality; explicitly not derived from match results. |
| — | Config file per match, distinct name, committed | `AUTO` | `test_config_filename_pattern` — assert `config_<game_id>_g<NN>.json` and uniqueness across `matches/`. |
| — | Tie rule | `AUTO` | `test_tie_awards_tie_score_to_both` — equal cumulative totals across all sub-games ⇒ both receive `tie_score`. |

---

## 7. Submission-artefact checklist

`PROCESS`. Mirrors Appendix C table 6 (PDF p. 136) and Ch. 11 (PDF pp. 113–114).
Every line must be *observed*, not intended.

- [ ] Two GitHub repositories (cop, thief), public **or** shared with
      `rmisegal@gmail.com`
- [ ] Cross-link present in **both** READMEs
- [ ] Annotated tag `v1.0-submission` created **and pushed** in both repos
- [ ] `README.md` in **both** repos contains all six mandatory components:
  - [ ] 1. Chosen Dec-POMDP model — state space, observations, uncertainty
  - [ ] 2. FastMCP orchestration dilemmas — turns, network failures, Gatekeeper
        and Orchestrator roles
  - [ ] 3. Strategies implemented — heuristics / belief map / (optional
        Q-Learning)
  - [ ] 4. Learning curves — **only if** RL was used
  - [ ] 5. Screenshots — Live GUI belief map **and** Replay showing
        `Verified OK`
  - [ ] 6. Link to the companion repository
- [ ] **Also in the README:** the documented contradiction choices from
      [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) — where identified, what chosen,
      why (PDF p. 5)
- [ ] `prd.md`, `plan.md`, `todo.md` present in both repos
- [ ] Each match's `config_<game_id>_g<NN>.json` committed
- [ ] ≥ 2 counting matches against **different** groups
- [ ] End-of-match email sent by **both** sides for every counting match
- [ ] No secrets anywhere in git history; `.gitignore` verified
- [ ] Moodle: PDF form filled without altering fields; one submission per member;
      8-character group code; self-grade for code quality only

---

## 8. End-to-end verification scenario

`MANUAL`, run before tagging. Exercises the whole compliance surface in one
pass.

1. Start two peers on separate machines, each behind its own tunnel.
2. Handshake: config hashes match; scent-model hashes match; game counts
   declared.
3. Step zero: both hardware declarations exchanged, each carrying its commit
   hash.
4. Play all `num_games` sub-games to completion. Observe in each peer's GUI:
   belief heatmap updating, turn banner alternating green/grey. Confirm **no**
   window shows the opponent's true position.
5. Force one failure deliberately: kill one peer mid-turn. Confirm the survivor
   hits its deadline, retries, and lands in `TECHNICAL_LOSS` cleanly with a
   readable log rather than hanging.
6. Restart and complete a clean match.
7. Final reveal + mutual audit ⇒ `Verified OK` on both sides.
8. Load each log in the replay viewer ⇒ green `Verified OK`. **Screenshot.**
9. Screenshot the belief map in the Live GUI. **Screenshot.**
10. Tamper with a saved log copy; reload in the viewer ⇒ red `TAMPERED`.
    Confirms the detector actually fires.
11. Result agreement ⇒ both sides email their own `result_<game_id>.json`.
    Confirm both arrive with the JSON attached.
12. Commit all four artefacts under `matches/<game_id>/`.

---

## 12. Implemented — cryptographic turn and audit chain

591 tests under `tests/crypto/`, `tests/audit/` and `tests/peer/test_crypto_turn.py`.

| Requirement | Test | Class |
|---|---|---|
| **E-17** commitment is lowercase-hex SHA-256, deterministic, pinned fixture | `test_sealed_and_commitment.py::test_commitment_is_lowercase_hex_sha256`, `::test_commitment_is_deterministic`, `::test_known_digest_fixture` | `AUTO` |
| **E-17** commitment binds game, sub-game, turn, role, action, hint, intent, nonce | `::test_changing_any_sealed_field_changes_the_commitment` (×9), `::test_commitment_binds_game_turn_role_and_action` | `AUTO` |
| Action not recoverable from the digest | `::test_action_is_not_recoverable_from_the_commitment` | `AUTO` |
| Key order irrelevant; single canonical helper | `::test_source_key_order_does_not_change_the_commitment`, `::test_commitment_uses_the_single_canonical_helper` | `AUTO` |
| Sealed schema closed; no timestamp, no global state | `::test_sealed_key_set_is_closed_and_complete`, `::test_sealed_record_carries_no_timestamp`, `::test_sealed_record_carries_no_global_state`, `::test_state_field_is_a_hash_not_a_position` | `AUTO` |
| Sealed schema rejects unknown/missing/mistyped fields | `::test_unknown_sealed_field_is_rejected`, `::test_missing_sealed_field_is_rejected` (×10), `::test_invalid_sealed_values_are_rejected` (×10) | `AUTO` |
| **E-18** nonce from `secrets`, 128-bit lowercase hex, distinct | `::test_nonce_uses_secrets_not_random`, `::test_nonce_format_is_lowercase_hex_of_fixed_length`, `::test_nonces_are_distinct_across_many_samples` | `AUTO` |
| **E-18** nonce reuse refused | `::test_guard_never_issues_the_same_nonce_twice`, `test_coordinator.py::test_a_nonce_is_never_reused_across_turns` | `AUTO` |
| **E-18** nonce absent from commit and from per-turn reveal | `test_coordinator.py::test_reveal_payload_never_contains_the_nonce`, `::test_local_nonce_never_leaves_the_coordinator_before_final_reveal` | `AUTO` |
| **E-18** reveal message schema has no nonce field | `test_crypto_turn.py::test_reveal_payload_schema_has_no_nonce_field` | `AUTO` |
| Commit payload leaks nothing about the move | `test_coordinator.py::test_commit_payload_contains_only_the_digest`; `test_crypto_turn.py::test_commit_payload_schema_rejects_an_action_field` (×5) | `AUTO` |
| Reveal forbidden before both commitments | `test_coordinator.py::test_reveal_is_forbidden_before_the_opponent_commits`; `test_crypto_turn.py::test_neither_peer_reveals_before_both_have_committed` | `AUTO` |
| Reveal permitted once both commitments exist | `test_coordinator.py::test_reveal_is_allowed_once_both_commitments_exist` | `AUTO` |
| Reveal with no prior commitment rejected | `test_coordinator.py::test_reveal_without_a_prior_opponent_commit_is_rejected` | `AUTO` |
| Duplicate commit/reveal idempotent; conflicts rejected | `test_coordinator.py::test_exact_duplicate_commit_is_idempotent`, `::test_conflicting_commit_is_rejected`, `::test_exact_duplicate_reveal_is_idempotent`, `::test_conflicting_reveal_is_rejected` | `AUTO` |
| Stale / future turn, wrong game / role / sub-game rejected | `test_coordinator.py::test_reveal_for_a_stale_turn_is_rejected`, `::test_reveal_for_a_future_turn_is_rejected`, `::test_reveal_claiming_the_wrong_game_is_rejected`, `::test_reveal_claiming_the_wrong_role_is_rejected`, `::test_reveal_claiming_the_wrong_sub_game_is_rejected` | `AUTO` |
| Commit/reveal must carry a turn number | `test_crypto_turn.py::test_commit_without_a_turn_number_is_rejected` | `AUTO` |
| **E-19** tampered action / nonce / hint / intent detected at audit | `test_coordinator.py::test_tampered_action_is_detected_at_audit`, `::test_tampered_nonce_is_detected_at_audit`, `::test_tampered_hint_is_detected_at_audit`, `::test_final_reveal_disagreeing_with_the_turn_reveal_is_detected` | `AUTO` |
| **E-36** clean match verifies both directions | `test_coordinator.py::test_a_clean_match_verifies`; `test_crypto_turn.py::test_final_reveal_verifies_a_clean_match` | `AUTO` |
| Abandoned turn discards the nonce and cannot resume | `test_coordinator.py::test_abandoning_a_turn_does_not_expose_the_nonce`, `::test_abandoned_turn_cannot_resume_without_a_fresh_seal` | `AUTO` |
| Two peers complete a full turn; mandatory state order | `test_crypto_turn.py::test_two_peers_complete_a_cryptographic_turn`, `::test_state_progression_is_the_mandatory_order`, `::test_several_turns_run_in_sequence` | `AUTO` |
| Turn fails cleanly with no reveal when opponent never commits | `test_crypto_turn.py::test_turn_fails_cleanly_when_the_opponent_never_commits`, `::test_abandoned_turn_does_not_expose_the_nonce` | `AUTO` |
| **E-20** audit chain: genesis, links, deterministic canonical hashing | `test_audit_chain.py::test_first_record_follows_the_explicit_genesis_hash`, `::test_each_record_chains_to_its_predecessor`, `::test_hash_excludes_its_own_field`, `::test_hashing_is_deterministic_and_canonical` | `AUTO` |
| **E-20** modification / deletion / insertion / reordering / duplicate id / malformed line detected | `test_audit_chain.py::test_modified_payload_is_detected`, `::test_modified_timestamp_is_detected`, `::test_modified_turn_number_is_detected`, `::test_deleted_middle_record_is_detected`, `::test_inserted_record_is_detected`, `::test_reordered_records_are_detected`, `::test_duplicate_event_id_is_detected_on_read`, `::test_malformed_line_is_detected` | `AUTO` |
| Append-only; first failure reported | `test_audit_chain.py::test_log_is_append_only`, `::test_verifier_reports_the_first_failure_only` | `AUTO` |
| **E-18** log privacy: no nonce before final reveal, at any depth | `test_audit_chain.py::test_a_nonce_cannot_be_logged_before_the_final_reveal`, `::test_a_nonce_nested_deep_is_still_refused`, `::test_the_final_reveal_may_carry_nonces`, `::test_pre_reveal_log_contains_no_action_or_nonce` | `AUTO` |
| Real-turn audit log verifies and holds no nonce | `test_crypto_turn.py::test_audit_log_records_the_turn_and_verifies`, `::test_audit_log_holds_no_nonce_before_the_final_reveal`, `::test_commit_record_carries_only_the_commitment` | `AUTO` |
| Two real processes: valid turn, tampering, audit tamper detection | `scripts` demonstrations, recorded in the Phase 3 report | `MANUAL` |

---

## 13. Implemented — Q-20 transport regression guards

Two tests added with the Q-20 fix (D-42). Both speak **real HTTP over a real
localhost socket**, unlike the rest of the peer suite, which uses the in-memory
`Client(fastmcp_instance)` or a `LoopbackClient` that skips the transport
entirely. They exist because the fault they guard against is invisible to any
in-process test: it needs an OS pipe and a real server.

| Requirement | Test | Class |
|---|---|---|
| The server keeps accepting fresh connections through repeated session reopens — 40 sequential sessions, a 4-way concurrent burst, then one more fresh connection (45 real HTTP sessions) | `tests/peer/test_http_stress.py::test_stateless_server_survives_repeated_real_http_reconnects` | `AUTO` |
| **Q-20 root cause** — two real peer subprocesses play 12 turns with stdout captured through **undrained** pipes, the exact condition that froze the loop at turn 6; both must exit 0 | `tests/peer/test_stdout_backpressure.py::test_q20_undrained_stdout_pipe_does_not_freeze_two_peers` | `AUTO` |
| The stdout flood is gone — each peer's undrained pipe stays under 16 KiB for a whole game | same test, assertion 2 | `AUTO` |
| Quieting stdout removed nothing from the logs — operational JSONL still records handshake, commits and reveals both ways; both audit chains are non-empty | same test, assertions 3–4 | `AUTO` |
| Play progresses past the old turn-6 wall, with no `send_unacknowledged` | same test, `_max_turn(...) >= 10` | `AUTO` |

The stdout test deliberately does not drain the pipes during the run
(`wait()` reads nothing), so a regression re-blocks a peer and the test fails on
the exit-code assertion rather than passing quietly. It also does not attempt to
make the *old* server fail: that failure was timing-dependent and a test built
on it would be flaky. Both guards are one-directional — the fixed runtime must
survive the churn.

### Q-20 end-to-end proof

`MANUAL`, performed and recorded. Full detail in
[../results/q20_transport_proof.md](../results/q20_transport_proof.md).

| Step | Observed |
|---|---|
| Two OS processes, real loopback FastMCP HTTP (`127.0.0.1:8801` ↔ `127.0.0.1:8802`), `game_id` `real-game-001` | both reached `ready` on `config_sha256` `410066bf…fd0a24d` |
| Play to the configured limit | **35 turns completed**; both processes exited 0 |
| Transport health | no `PeerTimeoutError`, no `send_unacknowledged`, no connection-refused channel restart (`transport_diagnostics`: primary 71 calls / 0 failures / 0 restarts; control 4 / 0 / 0) |
| **E-36** final reveal | all 35 turns verified |
| **E-36** mutual audit | both directions verified |
| **E-19/E-20** audit chains | `Verified OK (179 records)` for each peer, reproducible with `verify_chain_file` |
| **E-20** independent offline replay of both logs | **`VERIFIED OK`** — survival on turn 35, winner thief, cop 5 / thief 10 |

`logs/` is gitignored, so the run's artefacts are local rather than committed.
Where they are present, the last two rows reproduce with:

```bash
python -m police_thief.replay.viewer \
  --cop logs/audit_police_real-game-001.jsonl \
  --thief logs/audit_thief_real-game-001.jsonl
```
