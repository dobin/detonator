from sqlalchemy import create_engine, Column, Integer, String, LargeBinary, DateTime, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import hashlib
from sqlalchemy.orm import Mapped
from sqlalchemy import String, Integer, DateTime, Text, JSON
from typing import List, Optional


# SQLite database
SQLALCHEMY_DATABASE_URL = "sqlite:///./detonator.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    name: Mapped[str] = Column(String(100), nullable=False, unique=True, index=True)
    connector: Mapped[str] = Column(String(50), nullable=False)
    port: Mapped[int] = Column(Integer, nullable=False)
    edr_collector: Mapped[str] = Column(String(100), nullable=False)
    default_drop_path: Mapped[str] = Column(String(255), default="", nullable=False)
    comment: Mapped[str] = Column(Text, nullable=True)
    data: Mapped[dict] = Column(JSON, default={}, nullable=False)
    password: Mapped[str] = Column(String(255), default="", nullable=False)

    # Relationship
    scans: Mapped[List["Scan"]] = relationship("Scan", back_populates="profile")


class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    content: Mapped[bytes] = Column(LargeBinary, nullable=False)
    filename: Mapped[str] = Column(String(255), nullable=False)
    fileargs: Mapped[str] = Column(String(255), nullable=True)
    file_hash: Mapped[str] = Column(String(64), nullable=False, index=True)
    source_url: Mapped[str] = Column(String(500), nullable=True)
    comment: Mapped[str] = Column(Text, nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    scans: Mapped[List["Scan"]] = relationship("Scan", back_populates="file")

    @classmethod
    def calculate_hash(cls, content: bytes) -> str:
        """Calculate SHA256 hash of file content"""
        return hashlib.sha256(content).hexdigest()


class Scan(Base):
    __tablename__ = "scans"
    
    # IN
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    file_id: Mapped[int] = Column(Integer, ForeignKey("files.id"), nullable=False)
    profile_id: Mapped[int] = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    comment: Mapped[str] = Column(Text, default="", nullable=False)
    project: Mapped[str] = Column(String(100), default="", nullable=False)
    runtime: Mapped[int] = Column(Integer, default=10, nullable=False)
    drop_path: Mapped[str] = Column(String(255), default="", nullable=False)

    # TRACK
    detonator_srv_logs: Mapped[str] = Column(Text, nullable=False)
    status: Mapped[str] = Column(String(20), default="fresh", nullable=False)

    # OUT
    execution_logs: Mapped[str] = Column(Text, default="", nullable=False)
    agent_logs: Mapped[str] = Column(Text, default="", nullable=False)
    rededr_events: Mapped[str] = Column(Text, default="", nullable=False)
    edr_logs: Mapped[str] = Column(Text, default="", nullable=False)
    edr_summary: Mapped[list] = Column(JSON, default=[], nullable=False)
    result: Mapped[str] = Column(Text, default="", nullable=False)
    
    # Set by Instantiate, for Azure
    vm_exist: Mapped[int] = Column(Integer, default=0, nullable=False)
    vm_instance_name: Mapped[str] = Column(String(100), nullable=True)
    vm_ip_address: Mapped[str] = Column(String(15), nullable=True)

    # META
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime] = Column(DateTime, nullable=True)

    # Relationships
    file: Mapped[File] = relationship("File", back_populates="scans")
    profile: Mapped[Profile] = relationship("Profile", back_populates="scans")


# Create tables
Base.metadata.create_all(bind=engine)


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_for_thread():
    return SessionLocal()
