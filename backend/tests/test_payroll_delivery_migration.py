from io import StringIO
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.services.payroll_delivery_schema import upgrade, downgrade


def test_payroll_delivery_upgrade_preserves_existing_form16_and_downgrades():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        metadata = sa.MetaData()
        for name in ["companies", "users", "employees", "payroll_records", "form16_records"]:
            sa.Table(name, metadata, sa.Column("id", sa.Integer(), primary_key=True))
        sa.Table("payroll_runs", metadata, sa.Column("id", sa.Integer(), primary_key=True), sa.Column("company_id", sa.Integer()))
        sa.Table("payroll_payment_batches", metadata, sa.Column("id", sa.Integer(), primary_key=True), sa.Column("payroll_run_id", sa.Integer()))
        metadata.create_all(connection)
        connection.execute(metadata.tables["form16_records"].insert().values(id=1))
        connection.execute(metadata.tables["companies"].insert().values(id=1))
        connection.execute(metadata.tables["payroll_runs"].insert().values(id=3, company_id=1))
        connection.execute(metadata.tables["payroll_payment_batches"].insert().values(id=2, payroll_run_id=3))
        operations = Operations(MigrationContext.configure(connection))
        upgrade(operations)
        assert connection.exec_driver_sql("SELECT id, signature_status FROM form16_records").one() == (1, "pending")
        assert connection.exec_driver_sql("SELECT company_id FROM payroll_payment_batches WHERE id = 2").scalar() == 1
        assert {"payroll_delivery_profiles", "payroll_payout_attempts"} <= set(sa.inspect(connection).get_table_names())
        assert {"signed_file_path", "reviewed_by", "signed_sha256"} <= {c["name"] for c in sa.inspect(connection).get_columns("form16_records")}
        downgrade(operations)
        assert connection.exec_driver_sql("SELECT id FROM form16_records").scalar() == 1
    engine.dispose()


def test_postgresql_payroll_delivery_ddl_can_be_generated():
    output = StringIO()
    operations = Operations(MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}))
    upgrade(operations)
    sql = output.getvalue()
    assert "CREATE TABLE payroll_payout_attempts" in sql
    assert "uq_payroll_payout_record_mode" in sql
    assert "ALTER TABLE form16_records ADD COLUMN signed_file_path" in sql
