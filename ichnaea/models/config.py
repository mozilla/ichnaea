"""
This module contains database models for tables storing configuration.
"""

from sqlalchemy import (
    Column,
    String,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
)

from ichnaea.models.base import _Model
from ichnaea.models.sa_types import SetColumn


class ExportConfig(_Model):
    """
    ExportConfig database model.
    """
    __tablename__ = 'export_config'

    name = Column(String(40), primary_key=True)  #: Unique name.
    batch = Column(Integer)  #: Export batch size.
    schema = Column(String(32))  #: The export schema.
    url = Column(String(512))  #: Export URL.
    skip_keys = Column(SetColumn(1024))  #: Set of API keys to skip.
