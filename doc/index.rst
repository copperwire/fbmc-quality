

Welcome to FBMC quality analysis's documentation!

=================================================


Indices and tables
-------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

Introduction
------------

.. automodule:: fbmc_quality

 .. toctree::
    :maxdepth: 2
    :caption: User manual

    installing.rst
    configuration.rst
    clis.rst
    example.rst
    example_app.rst

.. currentmodule:: fbmc_quality


Module reference
----------------

.. automodule:: fbmc_quality.linearisation_analysis
    :members:

.. automodule:: fbmc_quality.linearisation_analysis.compute_functions
    :members:

.. automodule:: fbmc_quality.linearisation_analysis.dataclasses
    :members:

.. automodule:: fbmc_quality.linearisation_analysis.process_data
    :members:

.. automodule:: fbmc_quality.jao_data
    :members:

.. automodule:: fbmc_quality.jao_data.analyse_jao_data
    :members:

.. automodule:: fbmc_quality.jao_data.fetch_jao_data
    :members:

.. automodule:: fbmc_quality.jao_data.jao_store_cli
    :members:

.. automodule:: fbmc_quality.entsoe_data
    :members:

.. automodule:: fbmc_quality.entsoe_data.fetch_entsoe_data
    :members:

.. automodule:: fbmc_quality.entsoe_data.entsoe_store_cli
    :members:

.. automodule:: fbmc_quality.enums
    :members:

.. automodule:: fbmc_quality.enums.bidding_zones
    :members:

.. automodule:: fbmc_quality.dataframe_schemas
    :members:

.. autoclass:: fbmc_quality.dataframe_schemas.BiddingZones
    :members:

.. autoclass:: fbmc_quality.dataframe_schemas.NetPosition
    :no-index:
    :members:
    :inherited-members: DataFrameModel, BaseModel, BaseModelConfig
    :exclude-members: Config

.. autoclass:: fbmc_quality.dataframe_schemas.JaoData
    :no-index:
    :members:
    :inherited-members: DataFrameModel, BaseModel, BaseModelConfig
    :exclude-members: Config

.. autoclass:: fbmc_quality.dataframe_schemas.CnecData
    :no-index:
    :members:
    :inherited-members: DataFrameModel, BaseModel, BaseModelConfig
    :exclude-members: Config
