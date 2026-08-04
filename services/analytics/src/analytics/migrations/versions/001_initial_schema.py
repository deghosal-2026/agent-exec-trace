"""Initial schema: create read-model tables.

Revision ID: 001
Revises:
Create Date: 2026-01-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_summaries",
        sa.Column("run_id", sa.String(255), primary_key=True),
        sa.Column("agent_name", sa.String(255), nullable=False),
        sa.Column("agent_version", sa.String(50), nullable=True),
        sa.Column("workload_type", sa.String(100), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("total_tool_calls", sa.Integer(), server_default="0"),
        sa.Column("total_retries", sa.Integer(), server_default="0"),
        sa.Column("total_interventions", sa.Integer(), server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(10, 6), nullable=True),
        sa.Column("loop_count", sa.Integer(), server_default="0"),
        sa.Column("loop_detected", sa.Boolean(), server_default="false"),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("root_span_id", sa.String(255), nullable=True),
        sa.Column("trace_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("idx_run_summaries_agent", "run_summaries", ["agent_name"])
    op.create_index("idx_run_summaries_version", "run_summaries", ["agent_version"])
    op.create_index("idx_run_summaries_started_at", "run_summaries", ["started_at"])

    op.create_table(
        "anomalies",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("run_id", sa.String(255), sa.ForeignKey("run_summaries.run_id"), nullable=False),
        sa.Column("agent_name", sa.String(255), nullable=False),
        sa.Column("anomaly_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), server_default="warning"),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("idx_anomalies_run_id", "anomalies", ["run_id"])
    op.create_index("idx_anomalies_type", "anomalies", ["anomaly_type"])

    op.create_table(
        "fleet_rollups",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("agent_name", sa.String(255), nullable=False),
        sa.Column("agent_version", sa.String(50), nullable=True),
        sa.Column("workload_type", sa.String(100), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_runs", sa.Integer(), server_default="0"),
        sa.Column("success_count", sa.Integer(), server_default="0"),
        sa.Column("error_count", sa.Integer(), server_default="0"),
        sa.Column("loop_count", sa.Integer(), server_default="0"),
        sa.Column("anomaly_count", sa.Integer(), server_default="0"),
        sa.Column("avg_duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("avg_cost", sa.Numeric(10, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "agent_name", "agent_version", "workload_type", "period_start", "period_end",
            name="uq_fleet_rollup_period",
        ),
    )

    op.create_index("idx_fleet_rollups_agent", "fleet_rollups", ["agent_name"])

    op.create_table(
        "version_cohort_summaries",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("agent_name", sa.String(255), nullable=False),
        sa.Column("agent_version", sa.String(50), nullable=False),
        sa.Column("total_runs", sa.Integer(), server_default="0"),
        sa.Column("success_count", sa.Integer(), server_default="0"),
        sa.Column("error_count", sa.Integer(), server_default="0"),
        sa.Column("loop_count", sa.Integer(), server_default="0"),
        sa.Column("anomaly_count", sa.Integer(), server_default="0"),
        sa.Column("avg_duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("avg_cost", sa.Numeric(10, 6), nullable=True),
        sa.Column("total_tool_calls", sa.Integer(), server_default="0"),
        sa.Column("total_retries", sa.Integer(), server_default="0"),
        sa.Column("top_tools", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("agent_name", "agent_version", name="uq_version_cohort"),
    )


def downgrade() -> None:
    op.drop_table("version_cohort_summaries")
    op.drop_table("fleet_rollups")
    op.drop_table("anomalies")
    op.drop_table("run_summaries")