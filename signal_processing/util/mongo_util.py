"""
Functions to help manage mongo databases.
"""
import structlog

LOG = structlog.getLogger(__name__)


def create_indexes(collection, indexes):
    """
    Create indexes for a given collections.

    :param pymongo.Collection collection: The target collection.
    :param list(dict) indexes: The indexes to create.
    """
    LOG.debug('create indexes', collection=collection, indexes=indexes)
    for index in indexes:
        options = index['options'] if 'options' in index else {}
        collection.create_index(index['keys'], **options)


def drop_indexes(collection, indexes):
    """
    Drop indexes on a given collection.

    :param pymongo.Collection collection: The target collection.
    :param list(dict) indexes: The indexes to drop.
    """
    LOG.debug('drop indexes', collection=collection, indexes=indexes)
    for index in indexes:
        collection.drop_index(index['keys'])


def create_validator(collection, validator, action='error'):
    """
    Modify a collection to apply validation rules to a collection.

    :param pymongo.Collection collection: The target collection.
    :param dict validator: The validation rules.
    :param str action: The validation action. This controls the response to a
    validation issue. The default is error.

    See `schema-validation <https://docs.mongodb.com/manual/core/schema-validation/>`_
    See `json-schema <http://json-schema.org/>`_
    """
    LOG.debug('_create_validator', collection=collection, validator=validator)
    collection.database.command(
        'collMod',
        collection.name,
        validator=validator,
        validationAction=action)  # yapf: disable
