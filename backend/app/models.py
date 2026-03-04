from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    clinical_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    images: Mapped[list["CaseImage"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    outputs: Mapped[list["ModelOutput"]] = relationship(back_populates="case", cascade="all, delete-orphan")

class CaseImage(Base):
    __tablename__ = "case_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False)
    image_path: Mapped[str] = mapped_column(String(400), nullable=False)  # relative to /static
    caption: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    case: Mapped["Case"] = relationship(back_populates="images")

class ModelOutput(Base):
    __tablename__ = "model_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    output_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    case: Mapped["Case"] = relationship(back_populates="outputs")

class PerOutputEvaluation(Base):
    __tablename__ = "per_output_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False)
    output_id: Mapped[int] = mapped_column(ForeignKey("model_outputs.id"), nullable=False)

    annotator: Mapped[str] = mapped_column(String(120), nullable=False)
    accuracy: Mapped[int] = mapped_column(Integer, nullable=False)
    completeness: Mapped[int] = mapped_column(Integer, nullable=False)
    readability: Mapped[int] = mapped_column(Integer, nullable=False)

    issue_tags: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # {"tags": [...]}
    suggested_correction: Mapped[str] = mapped_column(Text, nullable=True, default="")
    comment: Mapped[str] = mapped_column(Text, nullable=True, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("case_id", "output_id", "annotator", name="uq_per_output_one_per_user"),
    )

class OverallPreference(Base):
    __tablename__ = "overall_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False)
    annotator: Mapped[str] = mapped_column(String(120), nullable=False)

    best_output_id: Mapped[int] = mapped_column(ForeignKey("model_outputs.id"), nullable=False)
    rationale_tags: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # {"tags": [...]}
    overall_comment: Mapped[str] = mapped_column(Text, nullable=True, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("case_id", "annotator", name="uq_overall_one_per_user"),
    )

class PairwiseComparison(Base):
    __tablename__ = "pairwise_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False)
    annotator: Mapped[str] = mapped_column(String(120), nullable=False)

    output_a_id: Mapped[int] = mapped_column(ForeignKey("model_outputs.id"), nullable=False)
    output_b_id: Mapped[int] = mapped_column(ForeignKey("model_outputs.id"), nullable=False)
    winner_output_id: Mapped[int] = mapped_column(ForeignKey("model_outputs.id"), nullable=False)

    reason_tags: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    comment: Mapped[str] = mapped_column(Text, nullable=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
