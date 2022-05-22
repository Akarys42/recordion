from pydantic import BaseModel, validator

from recordion.utils import validate_domain


class NewDomain(BaseModel):
    """New domain model."""

    name: str

    @validator("name")
    def validate_name(self, v: str) -> str:
        """Validate domain name."""
        validate_domain(v)
        return v


class Domain(NewDomain):
    """Domain model."""

    id: int


class NewRecord(BaseModel):
    """New record model."""

    name: str
    content: str
    type: str
    ttl: int | None = None
    prio: int | None = None

    @validator("name")
    def validate_name(self, v: str) -> str:
        """Validate record name."""
        validate_domain(v)
        return v


class UpdateRecord(BaseModel):
    """Update record model."""

    content: str | None = None
    ttl: int | None = None
    prio: int | None = None


class Record(NewRecord):
    """Record model."""

    id: int
    domain: str
    ttl: int
    can_edit: bool