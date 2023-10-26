
Configuration
=============



API keys
--------

.. _API keys:

To query data from `ENTSOE-Transparency <https://transparency.entsoe.eu/>`_ you need an API key from them. The `Transparency website has a guide <https://transparency.entsoe.eu/content/static_content/download?path=/Static%20content/API-Token-Management.pdf>`_.

The API key needs to be set in the environment before querying data, the value should be stored in an environment variable named :code:`ENTSOE_API_KEY`

Caching
-------

.. _CACHING:

The package stores data in a `duckdb <https://duckdb.org/>` database. This database is persisted on disk at `~/.flowbased_data` by default.
This storage location can be changed by setting the environment variable :code:`DB_PATH`. This variable should be a path + the name of the database ending with a ".db" or ".duckdb" file extension.
