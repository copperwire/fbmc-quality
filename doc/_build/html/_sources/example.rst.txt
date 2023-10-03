Example uses of the codebase
============================

Pulling net positions from ENTSOE-Transparency
----------------------------------------------
.. note::
    To pull data from the ENTSOE-Transparency you need to set API keys as noted in the :ref:`configuration guide <API keys>`.

Pulling data from JAO and ENTSOE-Transparency is the first step of the analysis. The data can be pulled from
the remote APIs or from the local cache. The local cache is by default stored at `~/.linearisation_error` and contains hourly snapshots of data.
To pull data from JAO and compute the Net Positions in the Base Case (Common Grid Model Net Positions)::

    from datetime import date
    from fbmc_quality.jao_data.analyse_jao_data import compute_basecase_net_pos
    from fbmc_quality.jao_data.fetch_jao_data import fetch_jao_dataframe_timeseries

    start = date(2023, 4, 1)
    end = date(2023, 5, 1)

    dataframe = fetch_jao_dataframe_timeseries(start, end)
    if dataframe is None:
        raise RuntimeError("No data")

    print(dataframe.head())

    basecase_nps = compute_basecase_net_pos(start, end)

    if basecase_nps is None:
        raise RuntimeError("No data")

    basecase_nps['NO2'].plot()

The :code:`dataframe` from JAO contains the FBMC results for all CNECs for a given hour. This includes the zonal PTDFs that we
use to compute the Base Case Net Positions. These are computed by summing up the cross border flows for each zonal border.

The API for pulling from ENTSOE-Transparency has a very similar API, you pull observed net positions with this snippet::

    from fbmc_quality.jao_data import compute_basecase_net_pos
    from fbmc_quality.jao_data import fetch_jao_dataframe_timeseries
    from datetime import date

    start = date(2023, 4, 1)
    end = date(2023, 5, 1)

    observed_nps = fetch_net_position_from_crossborder_flows(start, end)

    if observed_nps is None:
        raise RuntimeError("No data")

    observed_nps['NO2'].plot()

And pulling the data from a single cross border CNEC is similarly concise::

    from fbmc_quality.entsoe_data import fetch_net_position_from_crossborder_flows, fetch_observed_entsoe_data_for_cnec
    from fbmc_quality.enums import BiddingZonesEnum
    from datetime import date

    start = date(2023, 4, 1)
    end = date(2023, 5, 1)

    observed_nps = fetch_net_position_from_crossborder_flows(start, end)

    if observed_nps is None:
        raise RuntimeError("No data")

    observed_nps['NO2'].plot()

    no1_no2_observed_flow = fetch_observed_entsoe_data_for_cnec(from_area=BiddingZonesEnum.NO2, to_area=BiddingZonesEnum.NO1, start_date=start, end_date=end)
    no1_no2_observed_flow.plot()


Computing the linearisation error using the API
-----------------------------------------------------------

To plot the linearsiation error for a period we need to pull JAO data and observed data to measure against.
This section uses the method in the previous sub-section to pull data to compute flow and net positions.
Lets begin::

    from fbmc_quality.linearisation_analysis import compute_linearisation_error
    from fbmc_quality.linearisation_analysis import compute_linearisation_error, compute_linearised_flow
    from fbmc_quality.linearisation_analysis import load_data_for_corridor_cnec, load_jao_data_basecase_nps_and_observed_nps

    from datetime import date
    import plotly.express as px
    import plotly.io as pio
    import pandas as pd

    start = date(2023, 4, 1)
    end = date(2023, 5, 1)
    data = load_jao_data_basecase_nps_and_observed_nps(start, end)
    cnec_name ='NO3->SE2'
    cnec_data = load_data_for_corridor_cnec(
        cnec_name,
        data
    )
    if cnec_data is None:
        raise ValueError("No data found")


The

.. autofunction:: fbmc_quality.linearisation_analysis.load_data_for_corridor_cnec

and,

.. autofunction:: fbmc_quality.linearisation_analysis.load_jao_data_basecase_nps_and_observed_nps

returns `Dataclass` like `NamedTuples`. These containers are used in the workflow to pass data in a structured way.

Continuing::

    lin_err = compute_linearisation_error(cnec_data.cnecData, cnec_data.observedNPs, cnec_data.observed_flow['flow'])
    lin_err_frame = pd.DataFrame(
        {
            'Linearisation Error': lin_err,
            'Observed Flow': cnec_data.observed_flow['flow'],
            'Linearised Flow': compute_linearised_flow(cnec_data.cnecData, cnec_data.observedNPs),
        }
    )

    pio.templates.default = "ggplot2"
    fig = px.density_contour(
        lin_err_frame,
        x='Observed Flow',
        y='Linearised Flow',
        marginal_x='box',marginal_y='box',
        title=cnec_name[10:],
        width=600,
        height=600,
    )
    fig.update_layout(
        font=dict(
            size=16,
        )
    )
    fig.update_traces(line={'width': 2})

This plot shows the observed flow, and linearised flow for the border cnec `NO3->SE2`
