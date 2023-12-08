Running the bundled example app
================================

Running the example app
------------------------

.. note::

    Installing with optional dependencies for hosting the basic app is done by

        pip install fbmc-linearisation-analysis[app-template]

This package comes bundled with an example app. It just needs a function to read data from internal CNECs,
but this defaults to `None` and can be ignored.

The app is streamlit and the minimal configuration is to import the app function into a file, e.g `appfile.py`::

    from fbmc_quality.linearisation_error_app import app

    if __name__ == '__main__':
        app()

This app can then be run from the commandline with::

    streamlit run appfile.py

Which will start the streamlit dashboard.

If you have a function that reads data from internal CNECs it must return a dataframe with columns `flow` and `fmax`.
It takes as argument the date-time range (start-end), and the name of the CNEC as it appears in JAO.

Repeating the setup as above with this function::

    from fbmc_quality.linearisation_error_app import app
    from XXX import internal_cnec_function

    if __name__ == '__main__':
        app(internal_cnec_function)


Example app
--------------

.. literalinclude:: ../fbmc_quality/linearisation_error_app/basic_app.py
    :language: python
    :linenos:
