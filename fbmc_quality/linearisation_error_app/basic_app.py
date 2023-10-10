from datetime import date, timedelta
from typing import Callable

import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st
import streamlit_searchbox as st_searchbox
from dotenv import load_dotenv
from simstring.database.dict import DictDatabase
from simstring.feature_extractor.character_ngram import CharacterNgramFeatureExtractor
from simstring.measure.cosine import CosineMeasure
from simstring.searcher import Searcher

from fbmc_quality.dataframe_schemas.schemas import JaoData
from fbmc_quality.linearisation_analysis import (
    JaoDataAndNPS,
    compute_cnec_vulnerability_to_err,
    compute_linearisation_error,
    compute_linearised_flow,
    load_data_for_corridor_cnec,
    load_data_for_internal_cnec,
    load_jao_data_basecase_nps_and_observed_nps,
)
from fbmc_quality.linearisation_analysis.process_data import get_from_to_bz_from_name


@st.cache_data
def get_data(start, end):
    if isinstance(start, date) and isinstance(end, date):
        if start > end:
            return None
        data_load_state = st.text("Loading data...")
        data = load_jao_data_basecase_nps_and_observed_nps(start, end)
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
        if from_bz is None or to_bz is not None:
            if _self.internal_cnec_func is not None:
                cnec_data = load_data_for_internal_cnec(selected_name, _self.internal_cnec_func, _self.data)
            else:
                st.error(f"No function for reading internal CNECs supplied, and no BZ found for {selected_name}")
                cnec_data = None
        else:
            cnec_data = load_data_for_corridor_cnec(selected_name, _self.data)
        data_load_state.text("Loading CNEC data...done!")
        return cnec_data


def get_names(data: JaoDataAndNPS):
    return data.jaoData[JaoData.cnecName].unique()


class NameSearcher:
    def __init__(self):
        self.db = DictDatabase(CharacterNgramFeatureExtractor(2))

        self.seen_names = set()
        self.searcher = Searcher(self.db, CosineMeasure())

    def add_names(self, names):
        for name in names:
            name = str(name)

            if name not in self.seen_names:
                self.db.add(str(name))
                self.seen_names.add(name)

    def __call__(self, name: str):
        return self.searcher.search(name, 0.3)


def app(internal_cnec_func: Callable[[date, date, str], pd.DataFrame | None] | None = None):
    load_dotenv()

    pio.templates.default = "ggplot2"
    st.title("Linearisation Error Explorer")

    start = st.date_input("Start Date", value=None, max_value=date.today() - timedelta(2))
    end = st.date_input("End Date", value=None, max_value=date.today() - timedelta(1))

    data = get_data(start, end)
    name_searcher = NameSearcher()
    cnec_data = None
    cnec_data_container = None

    if data is not None:
        name_searcher.add_names(get_names(data))
        cnec_data_container = DataContainer(data, internal_cnec_func)

    selected_name = st_searchbox.st_searchbox(name_searcher)

    if selected_name is not None and cnec_data_container is not None:
        cnec_data = cnec_data_container.get_cnec_data(selected_name, start, end)

    if cnec_data is not None:
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
            reset_lin_err, id_vars=["index"], value_vars=[col for col in lin_err_frame.columns if col != "index"]
        )
        lineplot = px.line(
            new_frame,
            x="index",
            y="value",
            color="variable",
            labels={"x": "Date", "y": "Flow and Linearisation Error"},
            title="Linearisation Error timeseries",
        )
        st.plotly_chart(lineplot)

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
            cnec_data.cnecData, cnec_data.observedNPs, cnec_data.observed_flow["flow"]
        )
        reset_vuln_frame = vulnerability_frame.reset_index()
        new_vuln_frame = pd.melt(
            reset_vuln_frame, id_vars=["index"], value_vars=[col for col in reset_vuln_frame.columns if col != "index"]
        )

        fmax_mean = cnec_data.cnecData[JaoData.fmax].mean()
        vuln_lineplot = px.line(
            new_vuln_frame,
            x="index",
            y="value",
            color="variable",
            labels={"x": "Date", "y": "Score value"},
            title=f"Vulnerability and Reliability against Fmax ~ {fmax_mean}",
        )
        st.plotly_chart(vuln_lineplot)


if __name__ == "__main__":
    app()
