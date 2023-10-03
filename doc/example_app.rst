Running the bundled example app
================================

Running the example app
------------------------

This package comes bundled with an example app. It just needs a function to read data from internal CNECs,
but this defaults to `None` and can be ignored.

The app is streamlit and the minimal configuration is to import the app function into a file, e.g `appfile.py`::

    from fbmc_quality.linearisation_error_app import app

    app()

This app can then be run from the commandline with::

    streamlit run appfile.py

Which will start the streamlit dashboard.

Example app
--------------

.. literalinclude:: ../fbmc_quality/linearisation_error_app/basic_app.py
    :language: python
    :linenos:
