from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, func, Index
from core.database.engine import Base


class ModelDownload(Base):
    """ORM model for tracking HuggingFace model downloads."""

    __tablename__ = "model_downloads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(String(255), nullable=False, index=True)
    quantization = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    progress = Column(Float, default=0.0)
    local_path = Column(String(1024), nullable=True)
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Composite index for checking duplicate active downloads
    __table_args__ = (
        Index("ix_model_quantization", "model_id", "quantization"),
    )

    def __repr__(self):
        return f"<ModelDownload(id={self.id}, model_id={self.model_id}, status={self.status}, progress={self.progress}%)>"
