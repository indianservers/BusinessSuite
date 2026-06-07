"""fam inventory deep accounting integration

Revision ID: 20260607_021
Revises: 20260607_020
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260607_021"
down_revision = "20260607_020"
branch_labels = None
depends_on = None


def _add_column_if_missing(inspector, table_name: str, column: sa.Column) -> None:
    existing = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def _index_if_missing(inspector, table_name: str, index_name: str, columns: list[str]) -> None:
    existing = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    _add_column_if_missing(inspector, "fam_stock_items", sa.Column("purchase_ledger_id", sa.Integer(), sa.ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing(inspector, "fam_stock_items", sa.Column("sales_ledger_id", sa.Integer(), sa.ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing(inspector, "fam_stock_items", sa.Column("adjustment_gain_ledger_id", sa.Integer(), sa.ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing(inspector, "fam_stock_items", sa.Column("adjustment_loss_ledger_id", sa.Integer(), sa.ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing(inspector, "fam_stock_items", sa.Column("grni_ledger_id", sa.Integer(), sa.ForeignKey("fam_ledgers.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing(inspector, "fam_stock_items", sa.Column("cost_center_id", sa.Integer(), sa.ForeignKey("fam_cost_centers.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing(inspector, "fam_stock_items", sa.Column("branch_id", sa.Integer(), sa.ForeignKey("fam_branches.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing(inspector, "fam_stock_items", sa.Column("valuation_method", sa.String(length=40), nullable=True, server_default="weighted_average"))
    inspector = sa.inspect(bind)
    for column in ["purchase_ledger_id", "sales_ledger_id", "adjustment_gain_ledger_id", "adjustment_loss_ledger_id", "grni_ledger_id", "cost_center_id", "branch_id", "valuation_method"]:
        _index_if_missing(inspector, "fam_stock_items", f"ix_fam_stock_items_{column}", [column])


def downgrade() -> None:
    for column in ["valuation_method", "branch_id", "cost_center_id", "grni_ledger_id", "adjustment_loss_ledger_id", "adjustment_gain_ledger_id", "sales_ledger_id", "purchase_ledger_id"]:
        op.drop_column("fam_stock_items", column)
