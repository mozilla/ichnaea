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
from ichnaea.queue import DataQueue


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

    @classmethod
    def all(cls, session, detach=True):
        rows = session.query(cls).all()
        if detach:
            for row in rows:
                session.expunge(row)
        return rows

    @classmethod
    def get(cls, session, name, detach=True):
        row = (session.query(cls)
                      .filter(cls.name == name)).first()
        if row is not None and detach:
            session.expunge(row)
        return row

    def partitions(self, redis_client):
        if self.schema == 's3':
            # e.g. ['queue_export_something:api_key']
            return [key.decode('utf-8') for key in
                    redis_client.scan_iter(
                        match='queue_export_%s:*' % self.name, count=100)]
        return ['queue_export_' + self.name]

    def queue_key(self, api_key):
        if self.schema == 's3':
            if not api_key:
                api_key = 'no_key'
            return 'queue_export_%s:%s' % (self.name, api_key)
        return 'queue_export_' + self.name

    def queue(self, queue_key, redis_client):
        return DataQueue(queue_key, redis_client,
                         batch=self.batch, compress=False, json=True)
