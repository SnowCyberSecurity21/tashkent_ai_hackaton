"""SQLModel tables."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now()


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    gtin: str = Field(index=True, unique=True)
    trade_name: str
    inn_list: list = Field(default_factory=list, sa_column=Column(JSON))
    dose_form: str
    route: str
    manufacturer: str = Field(index=True)
    country: str
    is_local: bool = False
    rx_only: bool = False
    reg_status: str = "registered"  # registered|expired|unknown
    conformity_expired: bool = False
    gmp: bool = True
    bioequivalence: Optional[bool] = None
    price_uzs: int = 0
    max_units_per_day: int = 4
    shelf_life_months: int = 24
    is_original: bool = False
    raw_official: dict = Field(default_factory=dict, sa_column=Column(JSON))
    is_mock: bool = True


class Batch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    batch_no: str = Field(index=True)
    mfg_date: date
    exp_date: date
    recalled: bool = False


class Code(SQLModel, table=True):
    serial: str = Field(primary_key=True)
    gtin: str = Field(index=True)
    batch_no: str
    status: str = "valid"  # valid|unknown|withdrawn


class Scan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    serial: Optional[str] = Field(default=None, index=True)
    gtin: str = Field(index=True)
    city: Optional[str] = None
    ts: datetime = Field(default_factory=now, index=True, sa_type=DateTime)
    result_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    batch_no: Optional[str] = None
    type: str = "CoA"  # CoA|GMP|BE
    path: str = ""
    sha256: str = ""
    verified: bool = False
    ts: datetime = Field(default_factory=now, sa_type=DateTime)


class LabResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    parameter: str
    value: float
    spec_min: Optional[float] = None
    spec_max: Optional[float] = None
    unit: str = ""
    status: str = "ok"  # ok|out


class SafetyRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str  # duplicate|max_daily|drug_drug|drug_condition
    a: str
    b: Optional[str] = None
    threshold_mg: Optional[float] = None
    severity: str = "warn"  # info|warn|danger
    message_uz: str
    source: str
    approved: bool = False
    origin: str = "seed"  # seed|llm
    ts: datetime = Field(default_factory=now, sa_type=DateTime)


class Patient(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    conditions: list = Field(default_factory=list, sa_column=Column(JSON))
    alcohol: bool = False


class Regimen(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    product_id: int = Field(foreign_key="product.id")
    units_per_day: int = 1
    ts: datetime = Field(default_factory=now, sa_type=DateTime)


class Approval(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    from_product_id: int = Field(foreign_key="product.id")
    to_product_id: int = Field(foreign_key="product.id")
    status: str = "pending"  # pending|approved|rejected
    note: Optional[str] = None
    ts: datetime = Field(default_factory=now, sa_type=DateTime)
    decided_at: Optional[datetime] = Field(default=None, sa_type=DateTime)
    seen_at: Optional[datetime] = Field(default=None, sa_type=DateTime)


class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    batch_no: Optional[str] = None
    text: str
    category: str = "boshqa"
    severity: str = "info"  # info|warn|danger
    classified_by: str = "rules"
    ts: datetime = Field(default_factory=now, sa_type=DateTime)


class Rating(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    role: str = "patient"  # pharmacist|patient
    stars: int = 5
    ts: datetime = Field(default_factory=now, sa_type=DateTime)


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    actor: str
    role: str
    action: str
    entity: str
    ts: datetime = Field(default_factory=now, sa_type=DateTime)


class LlmCache(SQLModel, table=True):
    key: str = Field(primary_key=True)
    task: str = ""
    model: str = ""
    response_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    ts: datetime = Field(default_factory=now, sa_type=DateTime)
