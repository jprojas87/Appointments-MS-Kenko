"""Esquema inicial: medical_centers, physicians y appointments.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPOINTMENT_TYPE = postgresql.ENUM(
    "GENERAL", "ODONTOLOGIA", "PSICOLOGIA", name="appointment_type", create_type=False
)
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def upgrade() -> None:
    APPOINTMENT_TYPE.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "medical_centers",
        sa.Column("medical_center_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("medical_center_id", name="pk_medical_centers"),
    )

    op.create_table(
        "physicians",
        sa.Column("physician_id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("specialty", APPOINTMENT_TYPE, nullable=False),
        sa.Column("primary_med_center_id", sa.Uuid(), nullable=False),
        sa.Column("secondary_med_center_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["primary_med_center_id"],
            ["medical_centers.medical_center_id"],
            name="fk_physicians_primary_med_center_id_medical_centers",
        ),
        sa.ForeignKeyConstraint(
            ["secondary_med_center_id"],
            ["medical_centers.medical_center_id"],
            name="fk_physicians_secondary_med_center_id_medical_centers",
        ),
        sa.PrimaryKeyConstraint("physician_id", name="pk_physicians"),
    )

    weekday_list = ", ".join(f"'{name}'" for name in WEEKDAYS)
    op.create_table(
        "appointments",
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("type", APPOINTMENT_TYPE, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("weekday", sa.String(length=10), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("physician_id", sa.Uuid(), nullable=False),
        sa.Column("medical_center_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("end_time > start_time", name="ck_appointments_end_after_start"),
        sa.CheckConstraint(f"weekday IN ({weekday_list})", name="ck_appointments_weekday_valid"),
        sa.ForeignKeyConstraint(
            ["physician_id"],
            ["physicians.physician_id"],
            name="fk_appointments_physician_id_physicians",
        ),
        sa.ForeignKeyConstraint(
            ["medical_center_id"],
            ["medical_centers.medical_center_id"],
            name="fk_appointments_medical_center_id_medical_centers",
        ),
        sa.PrimaryKeyConstraint("appointment_id", name="pk_appointments"),
    )
    op.create_index("ix_appointments_user_id", "appointments", ["user_id"])
    op.create_index(
        "ix_appointments_type_date_user_id", "appointments", ["type", "date", "user_id"]
    )
    op.create_index("ix_appointments_medical_center_id", "appointments", ["medical_center_id"])
    op.create_index("ix_appointments_physician_id", "appointments", ["physician_id"])


def downgrade() -> None:
    op.drop_index("ix_appointments_physician_id", table_name="appointments")
    op.drop_index("ix_appointments_medical_center_id", table_name="appointments")
    op.drop_index("ix_appointments_type_date_user_id", table_name="appointments")
    op.drop_index("ix_appointments_user_id", table_name="appointments")
    op.drop_table("appointments")
    op.drop_table("physicians")
    op.drop_table("medical_centers")
    APPOINTMENT_TYPE.drop(op.get_bind(), checkfirst=True)
