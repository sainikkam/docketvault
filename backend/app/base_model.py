from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field


class TimestampMixin(SQLModel):
    """Inherit this in every table model. Provides created_at and updated_at."""

    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"onupdate": datetime.utcnow},
    )


class BaseID(TimestampMixin):
    """Inherit this for any table that needs a UUID primary key + timestamps."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
