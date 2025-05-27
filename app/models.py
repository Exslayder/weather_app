from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class SearchHistory(Base):
    __tablename__ = "search_history"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    city = Column(String, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
