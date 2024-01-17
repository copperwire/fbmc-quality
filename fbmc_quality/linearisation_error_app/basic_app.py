import logging
from datetime import date, timedelta
from typing import Callable, Optional

import numpy as np
import pandas as pd
from pkg_resources import declare_namespace
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from dotenv import load_dotenv
from joblib import Parallel
from pandas import NaT
from pytz import timezone

from fbmc_quality.dataframe_schemas.schemas import JaoData

# from fbmc_quality.linearisation_analysis.process_data import get_from_to_bz_from_name
from fbmc_quality.entsoe_data.fetch_entsoe_data import get_from_to_bz_from_name
from fbmc_quality.enums.bidding_zones import BiddingZonesEnum
from fbmc_quality.jao_data import get_cnec_id_from_name
from fbmc_quality.jao_data.fetch_jao_data import create_uuid_from_string
from fbmc_quality.linearisation_analysis import (
    JaoDataAndNPS,
    compute_cnec_vulnerability_to_err,
    compute_linearisation_error,
    compute_linearised_flow,
    fetch_jao_data_basecase_nps_and_observed_nps,
    load_data_for_corridor_cnec,
    load_data_for_internal_cnec,
)
from fbmc_quality.linearisation_analysis.process_data import align_by_index_overlap
from fbmc_quality.plotting.flow_map import compute_flow_geo_frame, draw_flow_map_figure, get_european_nps

load_dotenv()
logging.basicConfig(level="INFO")

st.set_page_config(layout="wide")
PARALLEL_CONTEXT = Parallel()


@st.cache_data
def get_data(start, end, _deanonymizer):
    if isinstance(start, date) and isinstance(end, date):
        if start > end:
            return None

        data_load_state = st.text("Loading data...")
        data = fetch_jao_data_basecase_nps_and_observed_nps(start, end)
        if _deanonymizer is not None:
            jaodata = data.jaoData
            jaodata[JaoData.cnecName] = jaodata[JaoData.cnecName].apply(_deanonymizer)
            jaodata[JaoData.cnec_id] = jaodata.apply(
                lambda row: create_uuid_from_string(row[JaoData.cnecName] + row[JaoData.contName]), axis=1
            )
            data = JaoDataAndNPS(jaodata, data.basecaseNPs, data.observedNPs)

        data_load_state.text("Loading data...done!")
        return data


class DataContainer:
    def __init__(
        self, data: JaoDataAndNPS, internal_cnec_func: Callable[[date, date, str], pd.DataFrame | None] | None
    ):
        self.data = data
        self.internal_cnec_func = internal_cnec_func

    @st.cache_data
    def get_cnec_data(_self, selected_name: str, start, end):
        data_load_state = st.text("Loading CNEC data...")

        from_bz, to_bz = get_from_to_bz_from_name(selected_name)
        if from_bz is None or to_bz is None:
            if _self.internal_cnec_func is not None:
                cnec_data = load_data_for_internal_cnec(selected_name, _self.internal_cnec_func, _self.data)
            else:
                st.error(f"No function for reading internal CNECs supplied, and no BZ found for {selected_name}")
                cnec_data = None
        else:
            cnec_data = load_data_for_corridor_cnec(selected_name, _self.data)
        data_load_state.text("Loading CNEC data...done!")
        return cnec_data


def get_names(data: JaoDataAndNPS)-> 'pd.Series[pd.StringDtype]': 
    return pd.Series(data.jaoData[JaoData.cnecName].unique())


@st.cache_data
def get_data_for_all_cnecs(_internal_cnec_func, names: list[str | pd.StringDtype], start, end):
    cnec_data = _internal_cnec_func(start, end, names)
    return cnec_data


def app(
    internal_cnec_func: Callable[[date, date, str | list[str]], pd.DataFrame | dict[str, pd.DataFrame] | None]
    | None = None,
    deanonymizer: Callable[[str], str] | None = None,
):
    load_dotenv()

    pio.templates.default = "ggplot2"
    st.title("Linearisation Error Explorer")

    if internal_cnec_func is not None:
        tabs = st.tabs(["Single CNEC Analysis", "Period all cnec Analysis"])
        single, all_cnecs = tabs
        single_cnec_analysis(internal_cnec_func, deanonymizer, single)
        all_cnecs_analysis(internal_cnec_func, deanonymizer, all_cnecs)
    else:
        single_cnec_analysis(None, deanonymizer, st)


def draw_flow_map(time: pd.Timestamp, data: JaoDataAndNPS, european_nps: dict[BiddingZonesEnum, pd.Series], st_col):
    with st_col.status("Plotting Flow..."):
        st.write("Computing Flow for MTU...")
        geo_df, obs_flow, fb_flow = compute_flow_geo_frame(time, data.jaoData, data.observedNPs, european_nps)
        st.write("Drawing Flow map for MTU...")
        fig = draw_flow_map_figure(
            geo_df,
            obs_flow,
            fb_flow,
        )
        st.write("Rendering map...")
        st_col.plotly_chart(fig, use_container_width=True)


def all_cnecs_analysis(
    internal_cnec_func: Callable[[date, date, list[str]], dict[str, pd.DataFrame] | None] | None = None,
    deanonymizer: Callable[[str, Optional[bool]], str] | None = None,
    st=None,
):
    if st is None:
        return

    start = st.date_input("Start Date", value=None, max_value=date.today() - timedelta(2), key="single_start")
    end = st.date_input("End Date", value=None, max_value=date.today() - timedelta(1), key="single_end")
    utc = timezone("utc")
    start = utc.localize(pd.Timestamp(start))
    end = utc.localize(pd.Timestamp(end))
    
    st.text('''
            Plot of the Vulnerability score for all CNECs in a period.
            The x axis shows if the FB process consistently under or overestimated the flow.
            When computing the Linearisation Error, the flow is capped to the max. flow allowable at the CNEC.
            The Vulnerability Score is calculated as: 
    ''')

    st.latex(
      r"\text{Relative} \hspace{0.1in} V=\frac{F_{obs} - min(F_{fb-max}, F_{fb})}{F_{limit} - F_{obs}}"
    )
    names = None
    data = None
    all_cnec_data = None
    overallocated_capacity = None
    underallocated_capacity = None

    if start is not NaT and end is not NaT:
        data = get_data(start, end, deanonymizer)
    if data is not None:
        names = list(get_names(data))

    if names is not None:
        all_cnec_data = get_data_for_all_cnecs(internal_cnec_func, names, start, end)

    if all_cnec_data is not None and data is not None:
        too_much_allocated_capacity = []
        too_little_allocated_capacity = []

        for cnec_name, frame in all_cnec_data.items():
            try:
                cnec_id = get_cnec_id_from_name(cnec_name, data.jaoData)

                if ("fmax" not in frame.columns) or ("flow" not in frame.columns):
                    raise ValueError('The internal cnec function must return a frame with columns "flow" and "fmax"')

                cnec_data = data.jaoData.xs(cnec_id, level=JaoData.cnec_id)
                overlap = align_by_index_overlap(cnec_data, frame, data.observedNPs)
                frame = frame.loc[overlap]
                vuln_cnec_data = compute_cnec_vulnerability_to_err(cnec_data.loc[overlap], data.observedNPs.loc[overlap], frame['flow'].loc[overlap], frame['fmax'].loc[overlap])
            except:
                continue

            mtus_above_threshold = 100 * (vuln_cnec_data["vulnerability_score"] > 1).sum() / len(vuln_cnec_data)
            median_above_zero = vuln_cnec_data["vulnerability_score"][
                vuln_cnec_data["vulnerability_score"] > 0
            ].median()


            too_much_allocated_capacity.append(
                {
                    "mtus_above_threshod": mtus_above_threshold,
                    "median_above_zero": median_above_zero,
                    "cnec": cnec_name,
                    "Significant Shadow Price": cnec_name in SHADOW_CNECS,
                    "Significant Domain Limit": (cnec_data[JaoData.presolved].sum() / len(cnec_data)) > 0.1
                }
            )

            mtus_below_threshold = 100 * (vuln_cnec_data["vulnerability_score"] < -1).sum() / len(vuln_cnec_data)
            median_below_zero = vuln_cnec_data["vulnerability_score"][
                vuln_cnec_data["vulnerability_score"] < 0
            ].median()
            too_little_allocated_capacity.append(
                {"mtus_below_threshod": mtus_below_threshold, "median_below_zero": median_below_zero, "cnec": cnec_name,
                    "Significant Shadow Price": cnec_name in SHADOW_CNECS,
                    "Significant Domain Limit": (cnec_data[JaoData.presolved].sum() / len(cnec_data)) > 0.1
                 }
            )

        overallocated_capacity = pd.DataFrame(too_much_allocated_capacity)
        overallocated_capacity = overallocated_capacity[
            (overallocated_capacity["mtus_above_threshod"] > 0) | (overallocated_capacity["median_above_zero"] > 0.7)
        ]
        underallocated_capacity = pd.DataFrame(too_little_allocated_capacity)
        underallocated_capacity = underallocated_capacity[
            (underallocated_capacity["mtus_below_threshod"] > 0) | (underallocated_capacity["median_below_zero"] < -0.7)
        ]

    if overallocated_capacity is not None and underallocated_capacity is not None:
        # st.dataframe(overallocated_capacity)
        # st.dataframe(underallocated_capacity)

        # fig_over = go.Figure()
        # fig_over.add_trace(
        #     go.Scatter(
        #         x=overallocated_capacity["median_above_zero"],
        #         y=overallocated_capacity["mtus_above_threshod"],
        #         text=overallocated_capacity["cnec"],
        #         mode="markers",
        #     )
        # )
        fig_over = px.scatter(
            overallocated_capacity,
            x='median_above_zero',
            y='mtus_above_threshod',
            hover_data=["cnec"],
            color='Significant Shadow Price',
            symbol='Significant Domain Limit'
        )

        fig_over.update_layout(
            title="CNECs that may have caused overloads",
            xaxis_title="Median Vulnerability Score - for MTUS with V > 0 ",
            yaxis_title=r"% of Active MTUS with Vulnerability score > 1",
            font=dict(
                size=24,  # Set the font size here
            ),
                xaxis=dict(
        tickfont=dict(size=14)  # Change the size value as needed
    ),
    yaxis=dict(
        tickfont=dict(size=14)  # Change the size value as needed
    )
        )
        st.plotly_chart(fig_over, use_container_width=True)
        filename = f"{start}-to-{end}-overloadrisk.html"
        st.download_button('Download Overestimate Plot as HTML', fig_over.to_html(), file_name=filename)

        # fig_under = go.Figure()
        # fig_under.add_trace(
        #     go.Scatter(
        #         x=underallocated_capacity["median_below_zero"],
        #         y=underallocated_capacity["mtus_below_threshod"],
        #         text=underallocated_capacity["cnec"],
        #         mode="markers",
        #     )
        # )

        fig_under= px.scatter(
            underallocated_capacity,
            x='median_below_zero',
            y='mtus_below_threshod',
            hover_data=["cnec"],
            color='Significant Shadow Price',
            symbol='Significant Domain Limit'
        )
        fig_under.update_layout(
            title="CNECs that may have caused too tight capacity restrictions",
            xaxis_title="Median Vulnerability Score - for MTUS with V < 0 ",
            yaxis_title=r"% of Active MTUS with Vulnerability score < -1",
            font=dict(
                size=24,  # Set the font size here
            ),
                xaxis=dict(
        tickfont=dict(size=14)  # Change the size value as needed
    ),
    yaxis=dict(
        tickfont=dict(size=14)  # Change the size value as needed
    )
        )
        st.plotly_chart(fig_under, use_container_width=True)
        filename = f"{start}-to-{end}-underallocaterisk.html"
        st.download_button('Download Underestimate Plot as HTML', fig_under.to_html(), file_name=filename)


def single_cnec_analysis(internal_cnec_func, deanonymizer, st):
    col1, col2 = st.columns(2)
    lin_err_from_cnec(internal_cnec_func, deanonymizer, col1, col2)


def lin_err_from_cnec(internal_cnec_func, deanonymizer, st, map_st):
    start = st.date_input("Start Date", value=None, max_value=date.today() - timedelta(2))
    end = st.date_input("End Date", value=None, max_value=date.today() - timedelta(1))
    utc = timezone("utc")
    start = utc.localize(pd.Timestamp(start))
    end = utc.localize(pd.Timestamp(end))
    cnec_data = None
    cnec_data_container = None
    selected_name = None
    data = None
    new_fmax = st.number_input("Replace Fmax in calculations with Number")

    if start is not NaT and end is not NaT:
        data = get_data(start, end, deanonymizer)

    if data is not None:
        cnec_data_container = DataContainer(data, internal_cnec_func)
        selected_name = st.selectbox(
            "Which CNEC do you want to plot for?", get_names(data), index=None, placeholder="Search for CNEC..."
        )

    if selected_name is not None and cnec_data_container is not None:
        cnec_data = cnec_data_container.get_cnec_data(selected_name, start, end)

    if cnec_data is not None and data is not None:
        lin_err = compute_linearisation_error(
            cnec_data.cnecData, cnec_data.observedNPs, cnec_data.observed_flow["flow"]
        )
        lin_err_frame = pd.DataFrame(
            {
                "Linearisation Error": lin_err,
                "Observed Flow": cnec_data.observed_flow["flow"],
                "Linearised Flow": compute_linearised_flow(cnec_data.cnecData, cnec_data.observedNPs),
            }
        )

        fig = px.density_contour(
            lin_err_frame,
            x="Observed Flow",
            y="Linearised Flow",
            marginal_x="box",
            marginal_y="box",
            width=600,
            height=600,
            title="Linearisation Error distribution",
        )

        reset_lin_err = lin_err_frame.reset_index()
        new_frame = pd.melt(
            reset_lin_err, id_vars=["time"], value_vars=[col for col in reset_lin_err.columns if col != "time"]
        )
        lineplot = px.line(
            new_frame,
            x="time",
            y="value",
            color="variable",
            labels={"x": "Date", "y": "Flow and Linearisation Error"},
            title="Linearisation Error timeseries",
        )
        fmax = (
            cnec_data.observed_flow["fmax"]
            if "fmax" in cnec_data.observed_flow.columns
            else cnec_data.cnecData[JaoData.fmax]
        )
        fmax = fmax if not new_fmax else np.full_like(cnec_data.cnecData.index, new_fmax)
        lineplot.add_trace(go.Scatter(x=cnec_data.observed_flow.index, y=fmax, name="Fmax", line=dict(dash="dash")))
        st.plotly_chart(lineplot)

        selected_time = map_st.selectbox("Select MTU to view flow", cnec_data.observed_flow.index)
        if selected_time is not None:
            try:
                european_nps = get_european_nps(start, end)
                draw_flow_map(selected_time, data, european_nps, map_st)
            except Exception as e:
                st.error(f"Drawing map failed with {e}")

        fig.update_layout(
            font=dict(
                size=16,  # Set the font size here
            )
        )
        fig.update_traces(line={"width": 2})
        st.plotly_chart(fig)

        fig = px.box(
            lin_err_frame,
            x=lin_err_frame.index.date,
            y="Linearisation Error",
            labels={"x": "Date", "y": "Linearisation Error"},
        )
        fig.update_layout(title="Linearisation Error Boxplot per Day")
        st.plotly_chart(fig)

        vulnerability_frame = compute_cnec_vulnerability_to_err(
            cnec_data.cnecData, cnec_data.observedNPs, cnec_data.observed_flow["flow"], fmax
        )
        reset_vuln_frame = vulnerability_frame.reset_index()
        new_vuln_frame = pd.melt(
            reset_vuln_frame, id_vars=["time"], value_vars=[col for col in reset_vuln_frame.columns if col != "time"]
        )

        fmax_mean = cnec_data.cnecData[JaoData.fmax].mean()
        vuln_lineplot = px.line(
            new_vuln_frame,
            x="time",
            y="value",
            color="variable",
            labels={"x": "Date", "y": "Score value"},
            title=f"Vulnerability and Reliability against Fmax ~ {fmax_mean}",
        )
        st.plotly_chart(vuln_lineplot)


if __name__ == "__main__":
    app()
