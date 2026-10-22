# Hasil uji aktual

Tanggal: 22 Oktober 2026. Data diambil langsung dari JUnit pytest dan laporan Playwright. Nama fungsi dipertahankan agar setiap hasil dapat ditelusuri ke kode pengujian.

## Desktop Windows

146 lulus; 0 dilewati; 0 gagal.

| Testcase | Hasil | Detik |
|---|---|---:|
| `tests.test_adaptive::test_new_game_does_not_mutate_prior_history` | LULUS | 0.089 |
| `tests.test_adaptive::test_new_game_after_white_opening` | LULUS | 0.091 |
| `tests.test_adaptive::test_knight_repetition_not_mistaken_for_new_game` | LULUS | 0.042 |
| `tests.test_adaptive::test_reset_requires_three_stable_frames` | LULUS | 0.226 |
| `tests.test_adaptive::test_flip_preserves_game_and_returns_new_orientation` | LULUS | 0.182 |
| `tests.test_adaptive::test_prior_game_archive_is_recoverable` | LULUS | 0.023 |
| `tests.test_adaptive::test_hotkey_queue_drains_once` | LULUS | 0.001 |
| `tests.test_adaptive_timing::test_gap_drives_budget[200-0-Mudah]` | LULUS | 0.002 |
| `tests.test_adaptive_timing::test_gap_drives_budget[90-20-Sedang]` | LULUS | 0.002 |
| `tests.test_adaptive_timing::test_gap_drives_budget[50-40-Rumit]` | LULUS | 0.002 |
| `tests.test_adaptive_timing::test_incomplete_probe_does_not_shorten_search` | LULUS | 0.001 |
| `tests.test_adaptive_timing::test_mate_and_black_perspective` | LULUS | 0.001 |
| `tests.test_adaptive_timing::test_off_keeps_original_search_and_on_restores_strength[Maksimal]` | LULUS | 0.003 |
| `tests.test_adaptive_timing::test_off_keeps_original_search_and_on_restores_strength[Human]` | LULUS | 0.003 |
| `tests.test_adaptive_timing::test_off_keeps_original_search_and_on_restores_strength[Menengah]` | LULUS | 0.004 |
| `tests.test_adaptive_timing::test_off_keeps_original_search_and_on_restores_strength[Pemula]` | LULUS | 0.003 |
| `tests.test_adaptive_timing::test_off_keeps_original_search_and_on_restores_strength[Blunder 15%]` | LULUS | 0.003 |
| `tests.test_black_setup::test_setup_after_white_opening_infers_black_turn[e2e4]` | LULUS | 0.002 |
| `tests.test_black_setup::test_setup_after_white_opening_infers_black_turn[d2d4]` | LULUS | 0.002 |
| `tests.test_black_setup::test_setup_after_white_opening_infers_black_turn[g1f3]` | LULUS | 0.002 |
| `tests.test_black_setup::test_setup_after_white_opening_infers_black_turn[c2c4]` | LULUS | 0.002 |
| `tests.test_black_setup::test_white_moves_between_training_and_start` | LULUS | 0.003 |
| `tests.test_black_setup::test_unknown_opening_position_not_guessed` | LULUS | 0.002 |
| `tests.test_black_setup::test_black_overlay_coordinates_all_squares` | LULUS | 0.001 |
| `tests.test_board::test_white_orientation_square_mapping_round_trip` | LULUS | 0.001 |
| `tests.test_board::test_detects_only_legal_visible_move` | LULUS | 0.002 |
| `tests.test_board::test_authoritative_fen_must_match_the_image` | LULUS | 0.001 |
| `tests.test_calibration::test_recalibrate_invalid_existing_coordinates` | LULUS | 0.021 |
| `tests.test_calibration::test_bad_capture_does_not_overwrite_configuration` | LULUS | 0.015 |
| `tests.test_detection::test_detect_board_offset_with_pieces` | LULUS | 0.282 |
| `tests.test_dot_overlay::test_markers_stay_in_correct_square_corner[3-white]` | LULUS | 0.001 |
| `tests.test_dot_overlay::test_markers_stay_in_correct_square_corner[3-black]` | LULUS | 0.001 |
| `tests.test_dot_overlay::test_markers_stay_in_correct_square_corner[5-white]` | LULUS | 0.001 |
| `tests.test_dot_overlay::test_markers_stay_in_correct_square_corner[5-black]` | LULUS | 0.001 |
| `tests.test_dot_overlay::test_markers_stay_in_correct_square_corner[10-white]` | LULUS | 0.001 |
| `tests.test_dot_overlay::test_markers_stay_in_correct_square_corner[10-black]` | LULUS | 0.001 |
| `tests.test_dot_overlay::test_markers_reverse_with_board_orientation` | LULUS | 0.001 |
| `tests.test_dot_overlay::test_invalid_marker_settings_are_rejected[marker_size-2]` | LULUS | 0.008 |
| `tests.test_dot_overlay::test_invalid_marker_settings_are_rejected[marker_size-11]` | LULUS | 0.006 |
| `tests.test_dot_overlay::test_invalid_marker_settings_are_rejected[marker_size-5.5]` | LULUS | 0.019 |
| `tests.test_dot_overlay::test_invalid_marker_settings_are_rejected[marker_opacity-0.01]` | LULUS | 0.007 |
| `tests.test_dot_overlay::test_invalid_marker_settings_are_rejected[marker_opacity-1]` | LULUS | 0.007 |
| `tests.test_dot_overlay::test_invalid_marker_settings_are_rejected[marker_opacity-nan]` | LULUS | 0.022 |
| `tests.test_dot_overlay::test_invalid_marker_settings_are_rejected[overlay_style-unknown]` | LULUS | 0.020 |
| `tests.test_dot_overlay::test_marker_controls_persist_without_changing_board_or_strength` | LULUS | 0.035 |
| `tests.test_dot_overlay::test_legacy_config_keeps_dots_and_shadow_selection_loads` | LULUS | 0.038 |
| `tests.test_fast_coach::test_cache_classifies_only_changed_tiles` | LULUS | 0.002 |
| `tests.test_fast_coach::test_panel_focus_allowed_only_outside_board` | LULUS | 0.001 |
| `tests.test_fast_coach::test_piece_change_invalidates_old_overlay_frame` | LULUS | 0.003 |
| `tests.test_fast_coach::test_engine_reuses_one_process_and_quits` | LULUS | 0.002 |
| `tests.test_fast_coach::test_stale_engine_result_never_reaches_overlay` | LULUS | 0.001 |
| `tests.test_human_style::test_style_prefers_development_only_among_equal_best_and_keeps_full_budget[False]` | LULUS | 0.002 |
| `tests.test_human_style::test_style_prefers_development_only_among_equal_best_and_keeps_full_budget[True]` | LULUS | 0.002 |
| `tests.test_human_style::test_quality_guard_retains_baseline[29-12-False-False]` | LULUS | 0.002 |
| `tests.test_human_style::test_quality_guard_retains_baseline[30-11-False-False]` | LULUS | 0.002 |
| `tests.test_human_style::test_quality_guard_retains_baseline[3-12-True-False]` | LULUS | 0.002 |
| `tests.test_human_style::test_quality_guard_retains_baseline[30-12-False-True]` | LULUS | 0.002 |
| `tests.test_human_style::test_style_off_uses_single_original_search` | LULUS | 0.001 |
| `tests.test_human_style::test_style_retains_mate_and_does_not_run_extra_search` | LULUS | 0.001 |
| `tests.test_human_style::test_style_retains_forced_check_response` | LULUS | 0.001 |
| `tests.test_human_style::test_comparison_must_not_regress_below_original_evaluation` | LULUS | 0.005 |
| `tests.test_human_style::test_castling_preferred_among_equal_moves` | LULUS | 0.002 |
| `tests.test_human_style::test_config_defaults_off_and_round_trips_boolean` | LULUS | 0.080 |
| `tests.test_human_style::test_human_level_can_choose_slightly_weaker_move_but_excludes_large_loss[False-False]` | LULUS | 0.003 |
| `tests.test_human_style::test_human_level_can_choose_slightly_weaker_move_but_excludes_large_loss[False-True]` | LULUS | 0.002 |
| `tests.test_human_style::test_human_level_can_choose_slightly_weaker_move_but_excludes_large_loss[True-False]` | LULUS | 0.002 |
| `tests.test_human_style::test_human_level_can_choose_slightly_weaker_move_but_excludes_large_loss[True-True]` | LULUS | 0.002 |
| `tests.test_human_style::test_human_level_endgame_has_stricter_tolerance` | LULUS | 0.002 |
| `tests.test_human_style::test_human_level_preserves_mate_and_ignores_losing_mate_candidates` | LULUS | 0.002 |
| `tests.test_human_style::test_human_level_retains_baseline_when_extra_search_is_too_shallow` | LULUS | 0.002 |
| `tests.test_licensing::test_signed_grant_valid_and_rotation` | LULUS | 0.021 |
| `tests.test_licensing::test_wrong_claims[changes0]` | LULUS | 0.002 |
| `tests.test_licensing::test_wrong_claims[changes1]` | LULUS | 0.002 |
| `tests.test_licensing::test_wrong_claims[changes2]` | LULUS | 0.002 |
| `tests.test_licensing::test_wrong_claims[changes3]` | LULUS | 0.002 |
| `tests.test_licensing::test_wrong_claims[changes4]` | LULUS | 0.002 |
| `tests.test_licensing::test_wrong_claims[changes5]` | LULUS | 0.002 |
| `tests.test_licensing::test_tampered_payload_forgery_and_expired` | LULUS | 0.002 |
| `tests.test_licensing::test_offline_startup_and_subscription_cap` | LULUS | 0.002 |
| `tests.test_licensing::test_activation_timeout_invalid_key_and_no_first_offline_access` | LULUS | 0.001 |
| `tests.test_licensing::test_valid_activation_cache_and_revocation` | LULUS | 0.002 |
| `tests.test_licensing::test_clock_rollback_requires_online_then_monotonic_expiry` | LULUS | 0.002 |
| `tests.test_licensing::test_invalid_cached_grant[cache0]` | LULUS | 0.001 |
| `tests.test_licensing::test_invalid_cached_grant[cache1]` | LULUS | 0.001 |
| `tests.test_licensing::test_device_mismatch_cache` | LULUS | 0.001 |
| `tests.test_licensing::test_device_fallback_is_stable_and_product_scoped` | LULUS | 0.001 |
| `tests.test_licensing::test_windows_dpapi_roundtrip_and_corruption` | LULUS | 0.650 |
| `tests.test_licensing::test_http_timeout_and_redirect_not_followed` | LULUS | 0.001 |
| `tests.test_licensing::test_network_worker_never_dispatches_tk` | LULUS | 0.002 |
| `tests.test_licensing::test_expired_entitlement_blocks_coach_start_and_submission` | LULUS | 0.001 |
| `tests.test_licensing_tk::test_tk_heartbeat_remains_responsive_during_network_timeout` | LULUS | 1.193 |
| `tests.test_live_recommendations::test_player_colour_follows_orientation_unless_explicit[black-auto-False]` | LULUS | 0.001 |
| `tests.test_live_recommendations::test_player_colour_follows_orientation_unless_explicit[white-auto-True]` | LULUS | 0.001 |
| `tests.test_live_recommendations::test_player_colour_follows_orientation_unless_explicit[black-white-True]` | LULUS | 0.001 |
| `tests.test_live_recommendations::test_player_colour_follows_orientation_unless_explicit[white-black-False]` | LULUS | 0.001 |
| `tests.test_live_recommendations::test_black_recommendations_follow_both_players_automatically` | LULUS | 0.012 |
| `tests.test_live_recommendations::test_stale_search_immediately_replaced_after_two_missed_plies` | LULUS | 0.099 |
| `tests.test_live_recommendations::test_ignoring_advice_continues_from_actual_moves[white]` | LULUS | 0.071 |
| `tests.test_live_recommendations::test_ignoring_advice_continues_from_actual_moves[black]` | LULUS | 0.103 |
| `tests.test_live_recommendations::test_old_search_failure_does_not_stop_after_alternative_move` | LULUS | 0.091 |
| `tests.test_live_recommendations::test_strength_change_persists_and_discards_pending_advice[Pemula]` | LULUS | 0.015 |
| `tests.test_live_recommendations::test_strength_change_persists_and_discards_pending_advice[Human]` | LULUS | 0.013 |
| `tests.test_live_recommendations::test_human_style_toggle_persists_and_discards_pending_advice` | LULUS | 0.027 |
| `tests.test_live_recommendations::test_human_style_save_failure_restores_toggle` | LULUS | 0.005 |
| `tests.test_live_recommendations::test_auto_colour_changes_after_detected_board_flip` | LULUS | 0.120 |
| `tests.test_live_recommendations::test_start_catches_up_from_learned_black_to_move_position` | LULUS | 0.040 |
| `tests.test_live_recommendations::test_legacy_config_defaults_to_auto_and_preserves_explicit_colour` | LULUS | 0.024 |
| `tests.test_live_recommendations::test_select_auto_preserves_concrete_board_orientation` | LULUS | 0.007 |
| `tests.test_live_recommendations::test_training_auto_recognizes_black_orientation` | LULUS | 0.040 |
| `tests.test_live_recommendations::test_training_auto_requires_templates_before_labelling` | LULUS | 0.001 |
| `tests.test_live_recommendations::test_autostart_does_not_override_manual_pause` | LULUS | 0.001 |
| `tests.test_live_recommendations::test_discovery_commits_black_board_and_starts_capture` | LULUS | 0.001 |
| `tests.test_live_recommendations::test_discovery_retries_and_discards_results_after_pause` | LULUS | 0.001 |
| `tests.test_live_recommendations::test_terminal_board_then_new_match_with_colour_swap` | LULUS | 0.097 |
| `tests.test_live_recommendations::test_adaptive_timing_toggle_persists_and_discards_pending_advice` | LULUS | 0.019 |
| `tests.test_live_recommendations::test_adaptive_timing_save_failure_restores_toggle` | LULUS | 0.003 |
| `tests.test_midgame::test_auto_waits_for_move_then_knows_turn_and_tracks_actual_position` | LULUS | 0.014 |
| `tests.test_midgame::test_explicit_turn_bootstraps_immediately_without_invented_rights[white]` | LULUS | 0.001 |
| `tests.test_midgame::test_explicit_turn_bootstraps_immediately_without_invented_rights[black]` | LULUS | 0.001 |
| `tests.test_midgame::test_check_can_prove_the_turn` | LULUS | 0.001 |
| `tests.test_midgame::test_invalid_board_never_bootstraps` | LULUS | 0.001 |
| `tests.test_midgame::test_orientation_from_home_pawns_and_explicit_endgame_override` | LULUS | 0.004 |
| `tests.test_midgame::test_coach_joins_screenshot_position_then_recommends_after_opponent_move` | LULUS | 0.975 |
| `tests.test_midgame::test_coach_explicit_turn_requires_stable_frames_and_preserves_followup` | LULUS | 0.561 |
| `tests.test_midgame::test_existing_synced_game_never_replaced_by_arbitrary_midgame` | LULUS | 0.414 |
| `tests.test_midgame::test_discovery_accepts_midgame_without_matching_initial_fen` | LULUS | 0.100 |
| `tests.test_portable::test_portable_paths_follow_config_after_move` | LULUS | 0.307 |
| `tests.test_portable::test_relaunch_preserves_preferences_and_learned_templates` | LULUS | 0.144 |
| `tests.test_portable::test_retry_interrupted_initialization_and_restore_missing_engine` | LULUS | 0.081 |
| `tests.test_portable::test_learned_template_round_trip_in_unicode_portable_folder` | LULUS | 0.414 |
| `tests.test_recovery_latency::test_animation_grace_and_scan_cooldown` | LULUS | 0.001 |
| `tests.test_recovery_latency::test_scan_queue_does_not_block_vision_queue` | LULUS | 0.003 |
| `tests.test_recovery_latency::test_normal_frame_change_never_triggers_periodic_scan` | LULUS | 0.001 |
| `tests.test_recovery_latency::test_same_geometry_does_not_clear_cache` | LULUS | 0.001 |
| `tests.test_recovery_latency::test_stale_scan_result_discarded` | LULUS | 0.001 |
| `tests.test_strength::test_strength_uses_played_move_and_matching_evaluation[False-Menengah-10]` | LULUS | 0.003 |
| `tests.test_strength::test_strength_uses_played_move_and_matching_evaluation[False-Pemula-0]` | LULUS | 0.003 |
| `tests.test_strength::test_strength_uses_played_move_and_matching_evaluation[True-Menengah-10]` | LULUS | 0.003 |
| `tests.test_strength::test_strength_uses_played_move_and_matching_evaluation[True-Pemula-0]` | LULUS | 0.003 |
| `tests.test_strength::test_blunder_probability_boundary_and_legal_weaker_move[0.149-a2a3]` | LULUS | 0.003 |
| `tests.test_strength::test_blunder_probability_boundary_and_legal_weaker_move[0.15-e2e4]` | LULUS | 0.002 |
| `tests.test_strength::test_blunder_probability_boundary_and_legal_weaker_move[0.99-e2e4]` | LULUS | 0.002 |
| `tests.test_strength::test_invalid_strength_is_rejected` | LULUS | 0.002 |
| `tests.test_tracker::test_missed_two_plies_preserve_metadata` | LULUS | 0.036 |
| `tests.test_tracker::test_initial_mismatch_does_not_invent_turn` | LULUS | 0.001 |
| `tests.test_tracker::test_castling_and_promotion` | LULUS | 0.004 |

## Backend PostgreSQL 17

19 lulus; 0 dilewati; 0 gagal.

| Testcase | Hasil | Detik |
|---|---|---:|
| `tests.test_grants::test_real_server_grant_signature_canonicalization_and_expiry_cap` | LULUS | 1.097 |
| `tests.test_lifecycle::test_generation_hides_key_and_first_activation` | LULUS | 0.829 |
| `tests.test_lifecycle::test_renew_active_and_idempotency` | LULUS | 1.005 |
| `tests.test_lifecycle::test_renew_expired_from_confirmation` | LULUS | 0.898 |
| `tests.test_lifecycle::test_denied_state_rejects_validation_and_renewal[revoke-REVOKED]` | LULUS | 0.756 |
| `tests.test_lifecycle::test_denied_state_rejects_validation_and_renewal[suspend-SUSPENDED]` | LULUS | 0.972 |
| `tests.test_lifecycle::test_device_limit_reset_and_deactivate` | LULUS | 1.049 |
| `tests.test_lifecycle::test_invalid_key_product_and_device` | LULUS | 0.821 |
| `tests.test_lifecycle::test_immutable_history_and_database_constraints` | LULUS | 1.000 |
| `tests.test_lifecycle::test_expiry_filter_and_plan_update_preserves_purchase` | LULUS | 0.922 |
| `tests.test_postgres::test_parallel_activation_cannot_exceed_device_limit` | LULUS | 0.807 |
| `tests.test_postgres::test_parallel_renewal_is_idempotent` | LULUS | 0.793 |
| `tests.test_proxy::test_forwarded_ip_only_from_trusted_proxy` | LULUS | 0.001 |
| `tests.test_security::test_admin_auth_csrf_session_and_logout` | LULUS | 0.760 |
| `tests.test_security::test_session_expiration` | LULUS | 0.523 |
| `tests.test_security::test_role_and_device_reset_authorization` | LULUS | 0.575 |
| `tests.test_security::test_rate_limit_activation_and_login` | LULUS | 0.597 |
| `tests.test_security::test_validation_response_does_not_echo_secret` | LULUS | 0.505 |
| `tests.test_validation::test_password_preserves_intentional_whitespace` | LULUS | 0.001 |

## Backend SQLite

17 lulus; 2 dilewati; 0 gagal.

| Testcase | Hasil | Detik |
|---|---|---:|
| `tests.test_grants::test_real_server_grant_signature_canonicalization_and_expiry_cap` | LULUS | 0.506 |
| `tests.test_lifecycle::test_generation_hides_key_and_first_activation` | LULUS | 0.459 |
| `tests.test_lifecycle::test_renew_active_and_idempotency` | LULUS | 0.435 |
| `tests.test_lifecycle::test_renew_expired_from_confirmation` | LULUS | 0.515 |
| `tests.test_lifecycle::test_denied_state_rejects_validation_and_renewal[revoke-REVOKED]` | LULUS | 0.620 |
| `tests.test_lifecycle::test_denied_state_rejects_validation_and_renewal[suspend-SUSPENDED]` | LULUS | 0.494 |
| `tests.test_lifecycle::test_device_limit_reset_and_deactivate` | LULUS | 0.549 |
| `tests.test_lifecycle::test_invalid_key_product_and_device` | LULUS | 0.491 |
| `tests.test_lifecycle::test_immutable_history_and_database_constraints` | LULUS | 0.521 |
| `tests.test_lifecycle::test_expiry_filter_and_plan_update_preserves_purchase` | LULUS | 0.531 |
| `tests.test_postgres::test_parallel_activation_cannot_exceed_device_limit` | DILEWATI — khusus PostgreSQL | 0.428 |
| `tests.test_postgres::test_parallel_renewal_is_idempotent` | DILEWATI — khusus PostgreSQL | 0.352 |
| `tests.test_proxy::test_forwarded_ip_only_from_trusted_proxy` | LULUS | 0.001 |
| `tests.test_security::test_admin_auth_csrf_session_and_logout` | LULUS | 0.404 |
| `tests.test_security::test_session_expiration` | LULUS | 0.380 |
| `tests.test_security::test_role_and_device_reset_authorization` | LULUS | 0.511 |
| `tests.test_security::test_rate_limit_activation_and_login` | LULUS | 0.600 |
| `tests.test_security::test_validation_response_does_not_echo_secret` | LULUS | 0.365 |
| `tests.test_validation::test_password_preserves_intentional_whitespace` | LULUS | 0.001 |

## Browser dan runtime

Playwright terhadap Compose: 1 skenario lulus; 0 gagal. Durasi runner 9.43 detik.

Alur: login → pelanggan → kunci sekali → aktivasi → perpanjangan → reset perangkat → penolakan kredensial lama → pencabutan → paket 30 hari → audit → tema/seluler → logout.

TypeScript dan build Next.js lokal/container berhasil. Audit npm produksi melaporkan 0 kerentanan. Seluruh health check Compose sehat. Migrasi selesai kode 0.

Lifecycle Tk jaringan nyata:

```json
{
  "activation": true,
  "stockfish": true,
  "capture_vision_overlay": true,
  "revocation_stops_premium": true,
  "heartbeat_count": 192,
  "ok": true
}
```

EXE Windows: runtime Stockfish 19 dan 13 kelompok template berhasil; legalitas langkah, Human, gaya ON/OFF, kedua overlay, tanpa Python di PATH, lokasi kerja berbeda, perpindahan folder non-ASCII, dan preferensi tersimpan berhasil. Hasil overall: `True`.

Pemeriksaan arsip: LULUS, 1.186 entri, tidak ada private key, kredensial database, .env, atau modul server. Bundel CA publik certifi diizinkan untuk koneksi TLS.

Peringatan yang masih ada: deprecation Starlette TestClient terkait httpx. Tidak ada pengujian lama yang dihapus. Rincian percobaan awal yang diperbaiki dan batas verifikasi ada dalam LAPORAN-IMPLEMENTASI.md.
