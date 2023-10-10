

Command Line Interface
=======================

Downloading Data
----------------
Pulling data from JAO and ENTSOE-Transparency can be quite slow. The data is cached locally in the :code:`~\\.linearisation_data` directory.

* You can pre download the data to disk using the CLIs eg,::

    fetch_jao_data 2023-4-1 2023-5-1
    fetch_entsoe_data 2023-4-1 2023-5-1
    
Both of these accept a from-date and to-date, on the format `YYYY-MM-DD`. 
