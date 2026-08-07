from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from analytics.main import cli


class TestCLIHelp:
    def test_cli_group_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Analytics service CLI" in result.output


class TestRunWorker:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["run-worker", "--help"])
        assert result.exit_code == 0
        assert "--interval" in result.output

    def test_invocation_with_mocked_deps(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()
        mock_worker = MagicMock()
        mock_worker.run = AsyncMock()
        mock_worker.shutdown = AsyncMock()

        with (
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch("analytics.main.ensure_schema", AsyncMock()),
            patch("analytics.main.close_pool", AsyncMock()),
            patch("analytics.worker.AnalyticsWorker", return_value=mock_worker),
        ):
            result = runner.invoke(cli, ["run-worker"])
            assert result.exit_code == 0
            mock_worker.run.assert_called_once()
            mock_worker.shutdown.assert_called_once()

    def test_with_interval_option(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()
        mock_worker = MagicMock()
        mock_worker.run = AsyncMock()
        mock_worker.shutdown = AsyncMock()

        with (
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch("analytics.main.ensure_schema", AsyncMock()),
            patch("analytics.main.close_pool", AsyncMock()),
            patch("analytics.worker.AnalyticsWorker", return_value=mock_worker),
            patch("analytics.main.settings") as mock_settings,
        ):
            runner.invoke(cli, ["run-worker", "--interval", "10"])
            assert mock_settings.polling_interval_seconds == 10


class TestReprocess:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["reprocess", "--help"])
        assert result.exit_code == 0
        assert "--start" in result.output
        assert "--end" in result.output
        assert "--trace-id" in result.output

    def test_missing_required_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["reprocess"])
        assert result.exit_code != 0
        assert "Missing option" in result.output

    def test_missing_start(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["reprocess", "--end", "2025-01-01T00:00:00"])
        assert result.exit_code != 0

    def test_missing_end(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["reprocess", "--start", "2025-01-01T00:00:00"])
        assert result.exit_code != 0

    def test_time_range_invocation(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()
        mock_worker = MagicMock()
        mock_worker.process_traces_in_range = AsyncMock(return_value=5)

        with (
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch("analytics.main.ensure_schema", AsyncMock()),
            patch("analytics.main.close_pool", AsyncMock()),
            patch("analytics.worker.AnalyticsWorker", return_value=mock_worker),
        ):
            result = runner.invoke(
                cli,
                ["reprocess", "--start", "2025-01-01T00:00:00", "--end", "2025-01-02T00:00:00"],
            )
            assert result.exit_code == 0
            assert "Reprocessed 5 traces" in result.output

    def test_single_trace_invocation(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()
        mock_worker = MagicMock()
        mock_worker.process_trace = AsyncMock(return_value=True)

        with (
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch("analytics.main.ensure_schema", AsyncMock()),
            patch("analytics.main.close_pool", AsyncMock()),
            patch("analytics.worker.AnalyticsWorker", return_value=mock_worker),
        ):
            result = runner.invoke(
                cli,
                [
                    "reprocess",
                    "--start",
                    "2025-01-01T00:00:00",
                    "--end",
                    "2025-01-02T00:00:00",
                    "--trace-id",
                    "abc123",
                ],
            )
            assert result.exit_code == 0
            assert "Reprocessed trace abc123" in result.output

    def test_trace_not_found(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()
        mock_worker = MagicMock()
        mock_worker.process_trace = AsyncMock(return_value=False)

        with (
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch("analytics.main.ensure_schema", AsyncMock()),
            patch("analytics.main.close_pool", AsyncMock()),
            patch("analytics.worker.AnalyticsWorker", return_value=mock_worker),
        ):
            result = runner.invoke(
                cli,
                [
                    "reprocess",
                    "--start",
                    "2025-01-01T00:00:00",
                    "--end",
                    "2025-01-02T00:00:00",
                    "--trace-id",
                    "nonexistent",
                ],
            )
            assert result.exit_code == 0
            assert "not found" in result.output


class TestRebuild:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["rebuild", "--help"])
        assert result.exit_code == 0
        assert "Re-process every trace" in result.output

    def test_invocation_with_mocked_deps(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()
        mock_worker = MagicMock()
        mock_worker.rebuild_all = AsyncMock(return_value=10)

        with (
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch("analytics.main.ensure_schema", AsyncMock()),
            patch("analytics.main.close_pool", AsyncMock()),
            patch("analytics.worker.AnalyticsWorker", return_value=mock_worker),
        ):
            result = runner.invoke(cli, ["rebuild"])
            assert result.exit_code == 0
            assert "Rebuild complete: 10 traces reprocessed" in result.output


class TestHealth:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "--help"])
        assert result.exit_code == 0
        assert "database connectivity" in result.output.lower()

    def test_health_ok(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()

        with (
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch("analytics.main.health_check", AsyncMock(return_value=True)),
        ):
            result = runner.invoke(cli, ["health"])
            assert result.exit_code == 0
            assert "Health: OK" in result.output

    def test_health_failed(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()

        with (
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch("analytics.main.health_check", AsyncMock(return_value=False)),
        ):
            result = runner.invoke(cli, ["health"])
            assert result.exit_code == 0
            assert "Health: FAILED" in result.output


class TestValidate:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
        assert "--input" in result.output
        assert "--output" in result.output
        assert "--llm-sample" in result.output
        assert "--resume" in result.output
        assert "--diagnose" in result.output

    def test_basic_invocation(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 100,
                "anomaly_count": 5,
                "traces_with_anomalies": 3,
                "anomaly_by_type": {"loop": 3, "retry_storm": 2},
                "suspicious_patterns": {},
                "cross_detector_correlation": {"top_co_fires": []},
                "skipped_detectors": {},
                "detector_errors": {},
            }
        )

        with patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator):
            result = runner.invoke(cli, ["validate"])
            assert result.exit_code == 0
            assert "Traces processed:     100" in result.output
            assert "Anomalies found:      5" in result.output

    def test_with_llm_sample(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 50,
                "anomaly_count": 3,
                "traces_with_anomalies": 2,
                "anomaly_by_type": {
                    "semantic_loop": 2,
                    "hallucination": 1,
                },
                "suspicious_patterns": {},
                "cross_detector_correlation": {"top_co_fires": []},
                "skipped_detectors": {},
                "detector_errors": {},
            }
        )

        with patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator):
            result = runner.invoke(cli, ["validate", "--llm-sample", "20"])
            assert result.exit_code == 0
            assert "LLM sample" in result.output

    def test_with_llm_no_cache_flag(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 10,
                "anomaly_count": 0,
                "traces_with_anomalies": 0,
                "anomaly_by_type": {},
                "suspicious_patterns": {},
                "cross_detector_correlation": {"top_co_fires": []},
                "skipped_detectors": {},
                "detector_errors": {},
            }
        )

        with patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator):
            result = runner.invoke(cli, ["validate", "--llm-sample", "5", "--llm-no-cache"])
            assert result.exit_code == 0

    def test_with_resume_flag(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 10,
                "anomaly_count": 0,
                "traces_with_anomalies": 0,
                "anomaly_by_type": {},
                "suspicious_patterns": {},
                "cross_detector_correlation": {"top_co_fires": []},
                "skipped_detectors": {},
                "detector_errors": {},
            }
        )

        with patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator):
            result = runner.invoke(cli, ["validate", "--resume"])
            assert result.exit_code == 0

    def test_with_diagnose_flag(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run_diagnose = MagicMock(
            return_value={
                "total_traces": 100,
                "total_datasets": 3,
                "total_detectors": 35,
                "global_compatibility_score_pct": 85,
                "corpus_field_coverage": {
                    "gen_ai.agent.name": {"pct": 100, "count": 100},
                    "gen_ai.response.content": {"pct": 45, "count": 45},
                },
            }
        )

        with patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator):
            result = runner.invoke(cli, ["validate", "--diagnose"])
            assert result.exit_code == 0
            assert "TRACE COMPATIBILITY DIAGNOSTIC" in result.output
            assert "Compatibility score:" in result.output

    def test_with_db_flag(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 10,
                "anomaly_count": 0,
                "traces_with_anomalies": 0,
                "anomaly_by_type": {},
                "suspicious_patterns": {},
                "cross_detector_correlation": {"top_co_fires": []},
                "skipped_detectors": {},
                "detector_errors": {},
            }
        )

        with (
            patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator),
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch("analytics.main.ensure_schema", AsyncMock()),
        ):
            result = runner.invoke(cli, ["validate", "--db"])
            assert result.exit_code == 0

    def test_with_db_unavailable_falls_back(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 10,
                "anomaly_count": 0,
                "traces_with_anomalies": 0,
                "anomaly_by_type": {},
                "suspicious_patterns": {},
                "cross_detector_correlation": {"top_co_fires": []},
                "skipped_detectors": {},
                "detector_errors": {},
            }
        )

        with (
            patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator),
            patch(
                "analytics.main.get_pool", AsyncMock(side_effect=RuntimeError("connection refused"))
            ),
        ):
            result = runner.invoke(cli, ["validate", "--db"])
            assert result.exit_code == 0
            assert "file-only validation" in result.output

    def test_with_max_files_and_max_traces(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 5,
                "anomaly_count": 1,
                "traces_with_anomalies": 1,
                "anomaly_by_type": {},
                "suspicious_patterns": {},
                "cross_detector_correlation": {"top_co_fires": []},
                "skipped_detectors": {},
                "detector_errors": {},
            }
        )

        with patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator):
            result = runner.invoke(cli, ["validate", "--max-files", "3", "--max-traces", "50"])
            assert result.exit_code == 0

    def test_with_llm_batch_option(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 30,
                "anomaly_count": 2,
                "traces_with_anomalies": 1,
                "anomaly_by_type": {},
                "suspicious_patterns": {},
                "cross_detector_correlation": {"top_co_fires": []},
                "skipped_detectors": {},
                "detector_errors": {},
            }
        )

        with patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator):
            result = runner.invoke(cli, ["validate", "--llm-sample", "10", "--llm-batch", "5"])
            assert result.exit_code == 0

    def test_with_custom_input_output_dirs(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 10,
                "anomaly_count": 0,
                "traces_with_anomalies": 0,
                "anomaly_by_type": {},
                "suspicious_patterns": {},
                "cross_detector_correlation": {"top_co_fires": []},
                "skipped_detectors": {},
                "detector_errors": {},
            }
        )

        with patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator):
            result = runner.invoke(
                cli,
                ["validate", "--input", "custom/traces", "--output", "custom/reports"],
            )
            assert result.exit_code == 0

    def test_with_suspicious_patterns_output(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 100,
                "anomaly_count": 80,
                "traces_with_anomalies": 70,
                "anomaly_by_type": {"low_output": 80},
                "suspicious_patterns": {"low_output": 80.0},
                "cross_detector_correlation": {"top_co_fires": []},
                "skipped_detectors": {},
                "detector_errors": {},
            }
        )

        with patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator):
            result = runner.invoke(cli, ["validate"])
            assert result.exit_code == 0
            assert "Suspicious" in result.output

    def test_with_cross_detector_correlation_output(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 100,
                "anomaly_count": 5,
                "traces_with_anomalies": 3,
                "anomaly_by_type": {"loop": 3, "retry_storm": 2},
                "suspicious_patterns": {},
                "cross_detector_correlation": {
                    "top_co_fires": [
                        {"pair": ["loop", "retry_storm"], "count": 2, "pct": 2.0},
                    ]
                },
                "skipped_detectors": {},
                "detector_errors": {},
            }
        )

        with patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator):
            result = runner.invoke(cli, ["validate"])
            assert result.exit_code == 0
            assert "Cross-detector hotspots" in result.output

    def test_llm_detector_results_in_output(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 20,
                "anomaly_count": 3,
                "traces_with_anomalies": 2,
                "anomaly_by_type": {
                    "semantic_loop": 2,
                    "hallucination": 1,
                },
                "suspicious_patterns": {},
                "cross_detector_correlation": {"top_co_fires": []},
                "skipped_detectors": {},
                "detector_errors": {},
            }
        )

        with patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator):
            result = runner.invoke(cli, ["validate", "--llm-sample", "10"])
            assert result.exit_code == 0
            assert "LLM DETECTOR RESULTS" in result.output
            assert "semantic_loop" in result.output
            assert "hallucination" in result.output

    def test_llm_detector_skipped_in_output(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 20,
                "anomaly_count": 0,
                "traces_with_anomalies": 0,
                "anomaly_by_type": {},
                "suspicious_patterns": {},
                "cross_detector_correlation": {"top_co_fires": []},
                "skipped_detectors": {"goal_drift": 5, "confusion_pattern": 3},
                "detector_errors": {},
            }
        )

        with patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator):
            result = runner.invoke(cli, ["validate", "--llm-sample", "10"])
            assert result.exit_code == 0
            assert "Skipped/errored" in result.output

    def test_llm_no_anomalies_output(self) -> None:
        runner = CliRunner()
        mock_validator = MagicMock()
        mock_validator.run = AsyncMock(
            return_value={
                "traces_processed": 10,
                "anomaly_count": 0,
                "traces_with_anomalies": 0,
                "anomaly_by_type": {},
                "suspicious_patterns": {},
                "cross_detector_correlation": {"top_co_fires": []},
                "skipped_detectors": {},
                "detector_errors": {},
            }
        )

        with patch("analytics.trace_pipeline.validator.Validator", return_value=mock_validator):
            result = runner.invoke(cli, ["validate", "--llm-sample", "5"])
            assert result.exit_code == 0
            assert "0 anomalies found" in result.output


class TestMaterialize:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["materialize", "--help"])
        assert result.exit_code == 0
        assert "--agent-name" in result.output
        assert "--workload-type" in result.output
        assert "--period-hours" in result.output

    def test_basic_invocation(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()
        mock_fleet_mat = MagicMock()
        mock_fleet_mat.materialize_fleet_rollups = AsyncMock(return_value=5)
        mock_cohort_mat = MagicMock()
        mock_cohort_mat.materialize_version_cohorts = AsyncMock(return_value=3)

        with (
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch(
                "analytics.materializer.FleetRollupMaterializer",
                return_value=mock_fleet_mat,
            ),
            patch(
                "analytics.materializer.VersionCohortMaterializer",
                return_value=mock_cohort_mat,
            ),
        ):
            result = runner.invoke(cli, ["materialize"])
            assert result.exit_code == 0
            assert "Materialized 5 fleet rollups, 3 version cohorts" in result.output

    def test_with_agent_name_filter(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()
        mock_fleet_mat = MagicMock()
        mock_fleet_mat.materialize_fleet_rollups = AsyncMock(return_value=2)
        mock_cohort_mat = MagicMock()
        mock_cohort_mat.materialize_version_cohorts = AsyncMock(return_value=1)

        with (
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch(
                "analytics.materializer.FleetRollupMaterializer",
                return_value=mock_fleet_mat,
            ),
            patch(
                "analytics.materializer.VersionCohortMaterializer",
                return_value=mock_cohort_mat,
            ),
        ):
            result = runner.invoke(cli, ["materialize", "--agent-name", "test-agent"])
            assert result.exit_code == 0

    def test_with_workload_type_filter(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()
        mock_fleet_mat = MagicMock()
        mock_fleet_mat.materialize_fleet_rollups = AsyncMock(return_value=1)
        mock_cohort_mat = MagicMock()
        mock_cohort_mat.materialize_version_cohorts = AsyncMock(return_value=0)

        with (
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch(
                "analytics.materializer.FleetRollupMaterializer",
                return_value=mock_fleet_mat,
            ),
            patch(
                "analytics.materializer.VersionCohortMaterializer",
                return_value=mock_cohort_mat,
            ),
        ):
            result = runner.invoke(cli, ["materialize", "--workload-type", "batch"])
            assert result.exit_code == 0

    def test_with_period_hours_option(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()
        mock_fleet_mat = MagicMock()
        mock_fleet_mat.materialize_fleet_rollups = AsyncMock(return_value=3)
        mock_cohort_mat = MagicMock()
        mock_cohort_mat.materialize_version_cohorts = AsyncMock(return_value=2)

        with (
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch(
                "analytics.materializer.FleetRollupMaterializer",
                return_value=mock_fleet_mat,
            ),
            patch(
                "analytics.materializer.VersionCohortMaterializer",
                return_value=mock_cohort_mat,
            ),
        ):
            result = runner.invoke(cli, ["materialize", "--period-hours", "12"])
            assert result.exit_code == 0

    def test_with_all_options(self) -> None:
        runner = CliRunner()
        mock_pool = MagicMock()
        mock_fleet_mat = MagicMock()
        mock_fleet_mat.materialize_fleet_rollups = AsyncMock(return_value=4)
        mock_cohort_mat = MagicMock()
        mock_cohort_mat.materialize_version_cohorts = AsyncMock(return_value=2)

        with (
            patch("analytics.main.get_pool", AsyncMock(return_value=mock_pool)),
            patch(
                "analytics.materializer.FleetRollupMaterializer",
                return_value=mock_fleet_mat,
            ),
            patch(
                "analytics.materializer.VersionCohortMaterializer",
                return_value=mock_cohort_mat,
            ),
        ):
            result = runner.invoke(
                cli,
                [
                    "materialize",
                    "--agent-name",
                    "test-agent",
                    "--workload-type",
                    "batch",
                    "--period-hours",
                    "6",
                ],
            )
            assert result.exit_code == 0


class TestDownloadTraces:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["download-traces", "--help"])
        assert result.exit_code == 0
        assert "--target" in result.output
        assert "--ingest" in result.output
        assert "--output-dir" in result.output
        assert "--batch-size" in result.output
        assert "--dataset" in result.output
        assert "--datasets-file" in result.output

    def test_basic_invocation(self) -> None:
        runner = CliRunner()
        mock_pipeline = MagicMock()
        mock_pipeline.run = AsyncMock(
            return_value={
                "datasets_downloaded": 2,
                "total_rows_downloaded": 500,
                "total_traces_valid": 450,
            }
        )

        with patch("analytics.trace_pipeline.pipeline.TracePipeline", return_value=mock_pipeline):
            result = runner.invoke(cli, ["download-traces"])
            assert result.exit_code == 0
            assert "Download complete" in result.output
            assert "Datasets attempted: 2" in result.output
            assert "Total rows downloaded: 500" in result.output
            assert "Total valid traces: 450" in result.output

    def test_with_target_option(self) -> None:
        runner = CliRunner()
        mock_pipeline = MagicMock()
        mock_pipeline.run = AsyncMock(
            return_value={
                "datasets_downloaded": 1,
                "total_rows_downloaded": 200,
                "total_traces_valid": 180,
            }
        )

        with patch("analytics.trace_pipeline.pipeline.TracePipeline", return_value=mock_pipeline):
            result = runner.invoke(cli, ["download-traces", "--target", "500"])
            assert result.exit_code == 0

    def test_with_ingest_flag(self) -> None:
        runner = CliRunner()
        mock_pipeline = MagicMock()
        mock_pipeline.run = AsyncMock(
            return_value={
                "datasets_downloaded": 1,
                "total_rows_downloaded": 100,
                "total_traces_valid": 90,
            }
        )

        with patch("analytics.trace_pipeline.pipeline.TracePipeline", return_value=mock_pipeline):
            result = runner.invoke(cli, ["download-traces", "--ingest"])
            assert result.exit_code == 0

    def test_with_output_dir_option(self) -> None:
        runner = CliRunner()
        mock_pipeline = MagicMock()
        mock_pipeline.run = AsyncMock(
            return_value={
                "datasets_downloaded": 1,
                "total_rows_downloaded": 100,
                "total_traces_valid": 95,
            }
        )

        with patch("analytics.trace_pipeline.pipeline.TracePipeline", return_value=mock_pipeline):
            result = runner.invoke(cli, ["download-traces", "--output-dir", "custom/output"])
            assert result.exit_code == 0

    def test_with_batch_size_option(self) -> None:
        runner = CliRunner()
        mock_pipeline = MagicMock()
        mock_pipeline.run = AsyncMock(
            return_value={
                "datasets_downloaded": 1,
                "total_rows_downloaded": 100,
                "total_traces_valid": 95,
            }
        )

        with patch("analytics.trace_pipeline.pipeline.TracePipeline", return_value=mock_pipeline):
            result = runner.invoke(cli, ["download-traces", "--batch-size", "10"])
            assert result.exit_code == 0

    def test_with_dataset_options(self) -> None:
        runner = CliRunner()
        mock_pipeline = MagicMock()
        mock_pipeline.run = AsyncMock(
            return_value={
                "datasets_downloaded": 2,
                "total_rows_downloaded": 300,
                "total_traces_valid": 270,
            }
        )

        with patch("analytics.trace_pipeline.pipeline.TracePipeline", return_value=mock_pipeline):
            result = runner.invoke(
                cli,
                [
                    "download-traces",
                    "--dataset",
                    "dataset-a",
                    "--dataset",
                    "dataset-b",
                ],
            )
            assert result.exit_code == 0

    def test_with_datasets_file_option(self) -> None:
        runner = CliRunner()
        mock_pipeline = MagicMock()
        mock_pipeline.run = AsyncMock(
            return_value={
                "datasets_downloaded": 3,
                "total_rows_downloaded": 400,
                "total_traces_valid": 380,
            }
        )

        with (
            patch("analytics.trace_pipeline.pipeline.TracePipeline", return_value=mock_pipeline),
            patch(
                "analytics.main.Path.read_text",
                return_value="dataset-1\n# comment\ndataset-2\n\n",
            ),
        ):
            result = runner.invoke(cli, ["download-traces", "--datasets-file", "datasets.txt"])
            assert result.exit_code == 0

    def test_with_datasets_file_not_found(self) -> None:
        runner = CliRunner()
        mock_pipeline = MagicMock()
        mock_pipeline.run = AsyncMock(
            return_value={
                "datasets_downloaded": 0,
                "total_rows_downloaded": 0,
                "total_traces_valid": 0,
            }
        )

        with patch("analytics.trace_pipeline.pipeline.TracePipeline", return_value=mock_pipeline):
            result = runner.invoke(cli, ["download-traces", "--datasets-file", "nonexistent.txt"])
            assert result.exit_code == 0
            assert "Warning" in result.output

    def test_with_all_options(self) -> None:
        runner = CliRunner()
        mock_pipeline = MagicMock()
        mock_pipeline.run = AsyncMock(
            return_value={
                "datasets_downloaded": 2,
                "total_rows_downloaded": 250,
                "total_traces_valid": 230,
            }
        )

        with patch("analytics.trace_pipeline.pipeline.TracePipeline", return_value=mock_pipeline):
            result = runner.invoke(
                cli,
                [
                    "download-traces",
                    "--target",
                    "200",
                    "--ingest",
                    "--output-dir",
                    "data/test-traces",
                    "--batch-size",
                    "8",
                    "--dataset",
                    "ds1",
                    "--dataset",
                    "ds2",
                ],
            )
            assert result.exit_code == 0
