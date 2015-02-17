from sqlalchemy.ext.declarative import declarative_base


class BaseModel(object):

    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
    }


_Model = declarative_base(cls=BaseModel)
