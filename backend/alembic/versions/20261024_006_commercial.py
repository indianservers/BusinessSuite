"""Add shared commercial identity mappings and invoice context. No history rewrite."""

from alembic import op
import sqlalchemy as sa

revision = "20261024_006"
down_revision = "20261024_005"
branch_labels = None
depends_on = None


def upgrade():
    from app.apps.srm.commercial_models import (
        CustomerLink,
        ProjectCommercial,
        InvoiceContext,
        InvoiceDelivery,
        SellerGrant,
        TimeBillingAllocation,
        SalesTeamAssignment,
        MilestoneBillingSource,
        CommercialNumberSequence,
        ReceiptContext,
    )

    for model in [
        CustomerLink,
        ProjectCommercial,
        InvoiceContext,
        InvoiceDelivery,
        SellerGrant,
        TimeBillingAllocation,
        SalesTeamAssignment,
        MilestoneBillingSource,
        CommercialNumberSequence,
        ReceiptContext,
    ]:
        model.__table__.create(op.get_bind(), checkfirst=True)

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("srm_invoice_lines"):
        columns = {c["name"]: c for c in inspector.get_columns("srm_invoice_lines")}
        if "discount_amount" not in columns:
            op.add_column(
                "srm_invoice_lines",
                sa.Column(
                    "discount_amount",
                    sa.Numeric(14, 2),
                    nullable=True,
                    server_default="0",
                ),
            )
        quantity_type = columns["quantity"]["type"]
        if getattr(quantity_type, "scale", None) != 10:
            with op.batch_alter_table("srm_invoice_lines") as batch:
                batch.alter_column(
                    "quantity",
                    existing_type=quantity_type,
                    type_=sa.Numeric(24, 10),
                    existing_nullable=True,
                )


def downgrade():
    pass  # Preserve financial references and delivery history on app rollback.
