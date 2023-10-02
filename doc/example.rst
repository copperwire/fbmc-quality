Example uses of the codebase
============================

Example using the package and APIs
-----------------------------------

The simplest use of the repository is to plot the linearsiation error for a period in, lets begin::

    from fbmc_quality.linearisation_analysis import compute_linearisation_error
    from fbmc_quality.linearisation_analysis import compute_linearisation_error, compute_linearised_flow
    from fbmc_quality.linearisation_analysis import load_data_for_cnec, load_jao_data_basecase_nps_and_observed_nps

    from datetime import date
    import plotly.express as px
    import plotly.io as pio
    import pandas as pd

    start = date(2023, 4, 1)
    end = date(2023, 5, 1)
    data = load_jao_data_basecase_nps_and_observed_nps(start, end)
    cnec_name ='NO3->SE2' 
    cnec_data = load_data_for_cnec(
        cnec_name,
        data
    )
    if cnec_data is None:
        raise ValueError("No data found")

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