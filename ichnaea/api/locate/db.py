"""Helper functions to query our own database."""

from sqlalchemy.orm import load_only


def query_database(query, lookups, model, raven_client,
                   load_fields=('lat', 'lon', 'range')):
    """
    Given a location query and a list of lookup instances, query the
    database and return a list of model objects.
    """
    hashkeys = [lookup.hashkey() for lookup in lookups]
    if not hashkeys:  # pragma: no cover
        return []

    try:
        model_iter = model.iterkeys(
            query.session,
            hashkeys,
            extra=lambda query: query.options(load_only(*load_fields))
                                     .filter(model.lat.isnot(None))
                                     .filter(model.lon.isnot(None)))

        return list(model_iter)
    except Exception:
        raven_client.captureException()
    return []
