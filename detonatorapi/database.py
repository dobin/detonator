from sqlalchemy import create_engine, Column, Integer, String, LargeBinary, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import hashlib

# SQLite database
SQLALCHEMY_DATABASE_URL = "sqlite:///./detonator.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class File(Base):
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(LargeBinary, nullable=False)
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    source_url = Column(String(500), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    scans = relationship("Scan", back_populates="file")
    
    @classmethod
    def calculate_hash(cls, content: bytes) -> str:
        """Calculate SHA256 hash of file content"""
        return hashlib.sha256(content).hexdigest()


class Scan(Base):
    __tablename__ = "scans"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    comment = Column(Text, nullable=False)

    project = Column(String(100), nullable=False)
    edr_template = Column(String(100), nullable=False)

    detonator_srv_logs = Column(Text, nullable=False)          # Detonator API logs
    agent_logs = Column(Text, default="", nullable=False)      # RedEdr result (log, output)
    rededr_events = Column(Text, default="", nullable=False)   # RedEdr logs, exec output
    edr_logs = Column(Text, default="", nullable=False)        # AV/EDR logs (Event Viewer)
    result = Column(Text, default="", nullable=False)          # Detected or not (based on agent_logs)

    status = Column(String(20), default="fresh", nullable=False)

    vm_instance_name = Column(String(100), nullable=True)
    vm_ip_address = Column(String(15), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationship
    file = relationship("File", back_populates="scans")


# Create tables
Base.metadata.create_all(bind=engine)


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Function to get a new DB session for background tasks
def get_background_db():
    """Get a new database session for background tasks"""
    return SessionLocal()
