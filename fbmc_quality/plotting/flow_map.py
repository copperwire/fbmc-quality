import colorsys
from functools import cache
from logging import getLogger
from time import time
from typing import Any

import geopandas as gpd
import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from entsoe import Area
from entsoe.exceptions import NoMatchingDataError
from entsoe.geo.utils import load_zones
from numpy import floating
from numpy.typing import NDArray
from pandera.typing import DataFrame
from PIL import ImageColor
from requests import Session
from shapely import LineString, MultiLineString, MultiPolygon, Point, Polygon, affinity, geometry, measurement
from shapely.geometry import shape
from sklearn.linear_model import LinearRegression

from fbmc_quality.dataframe_schemas import JaoData
from fbmc_quality.dataframe_schemas.schemas import NetPosition
from fbmc_quality.entsoe_data.fetch_entsoe_data import fetch_entsoe_data_from_bidding_zones, get_entsoe_client
from fbmc_quality.enums import BiddingZonesEnum
from fbmc_quality.jao_data.analyse_jao_data import (
    BIDDING_ZONE_CNEC_MAP,
    get_cnec_id_from_name,
    get_cross_border_cnec_ids,
)
from fbmc_quality.linearisation_analysis import compute_linearised_flow

ZONE_AREA_MAP = {
    BiddingZonesEnum.NO2: "NO_2",
    BiddingZonesEnum.NO1: "NO_1",
    BiddingZonesEnum.NO3: "NO_3",
    BiddingZonesEnum.NO4: "NO_4",
    BiddingZonesEnum.NO5: "NO_5",
    BiddingZonesEnum.SE2: "SE_2",
    BiddingZonesEnum.SE1: "SE_1",
    BiddingZonesEnum.SE3: "SE_3",
    BiddingZonesEnum.SE4: "SE_4",
    BiddingZonesEnum.DK1: "DK_1",
    BiddingZonesEnum.DK2: "DK_2",
    BiddingZonesEnum.FI: "FI",
}

HVDC_AREA_MAP: dict[BiddingZonesEnum, str] = {
    BiddingZonesEnum.NO2_ND: "NL",
    BiddingZonesEnum.NO2_NK: "DE_LU",
    BiddingZonesEnum.NO2_SK: "DK_1",
    BiddingZonesEnum.DK1_CO: "DK_2",
    BiddingZonesEnum.DK1_DE: "DE_LU",
    BiddingZonesEnum.DK1_KS: "SE_3",
    BiddingZonesEnum.DK1_SB: "DK_2",
    # BiddingZonesEnum.DK1_SK: 'NO_2',
    # BiddingZonesEnum.DK1_ST:'.',
    # BiddingZonesEnum.DK2_SB: 'DK_2',
    BiddingZonesEnum.DK2_KO: "DE_LU",
    # BiddingZonesEnum.DK2_ST:'. ',
    BiddingZonesEnum.SE3_FS: "FI",
    # BiddingZonesEnum.SE3_KS:'.',
    # BiddingZonesEnum.FI_FS: '. ',
    BiddingZonesEnum.FI_EL: "EE",
    BiddingZonesEnum.SE4_BC: "DE_LU",
    BiddingZonesEnum.SE4_SP: "PL",
    BiddingZonesEnum.SE4_NB: "LT",
}
ZONE_MAP_WITH_HVDC = {hvdc_cable: hvdc_cable.value for hvdc_cable in HVDC_AREA_MAP}
ZONE_MAP_WITH_HVDC.update(ZONE_AREA_MAP)
ALL_ZONES = list(
    ZONE_AREA_MAP.values()
)  # ['NO_1', 'NO_2', 'NO_3', 'NO_4', 'NO_5', 'SE_1', 'SE_2', 'SE_3', 'SE_4', 'DK_1']


def compute_flow_geo_frame(
    input_timestamp: pd.Timestamp,
    basecase_data: DataFrame[JaoData],
    observed_data: DataFrame[NetPosition],
    european_nps: dict[BiddingZonesEnum, pd.Series],
) -> tuple[
    gpd.GeoDataFrame,
    dict[tuple[BiddingZonesEnum, BiddingZonesEnum], float],
    dict[tuple[BiddingZonesEnum, BiddingZonesEnum], float],
]:
    geo_df = get_base_geodf()

    start = input_timestamp.tz_convert("utc")
    end = input_timestamp + pd.Timedelta(hours=2)

    subset_jao = basecase_data.xs(input_timestamp, level=JaoData.time)

    cnec_ids = get_cross_border_cnec_ids(basecase_data)
    flow_based_corridor_values = {}
    observed_corridor_values = {}

    for bz in ZONE_MAP_WITH_HVDC.keys():
        for i, _ in enumerate(cnec_ids[bz]):
            target = BIDDING_ZONE_CNEC_MAP[bz][i][1]
            from_to = (bz, target)

            cnec_id = get_cnec_id_from_name(BIDDING_ZONE_CNEC_MAP[bz][i][0], basecase_data)
            fb_cnec_flow = -1 * compute_linearised_flow(subset_jao.loc[cnec_id], observed_data).loc[start]
            try:
                obs_cnec_flow = fetch_entsoe_data_from_bidding_zones(start, end, bz, target).loc[start].iloc[0]
            except ValueError:
                obs_cnec_flow = 0
            flow_based_corridor_values[from_to] = fb_cnec_flow
            observed_corridor_values[from_to] = obs_cnec_flow

    subset_nps = observed_data.xs(start)
    nps = []
    for zone_enum in ZONE_AREA_MAP:
        nps.append(
            {
                "zoneName": ZONE_AREA_MAP[zone_enum],
                "Net Position": subset_nps[zone_enum.value],
            }
        )

    nps = pd.DataFrame(nps)
    nps = nps.set_index("zoneName")
    geo_df = geo_df.merge(nps, left_index=True, right_index=True, how="left")
    update_frame_with_european_nps(geo_df, european_nps, start)

    return geo_df, flow_based_corridor_values, observed_corridor_values


@cache
def get_base_geodf():
    geo_df = load_zones(ALL_ZONES, pd.Timestamp("2023-1-1"))
    hvdc_geo_frame = [
        {
            "zoneName": ZONE_MAP_WITH_HVDC[bz],
            "geometry": load_zones([area], pd.Timestamp("2023-1-1"))["geometry"].iloc[0],
        }
        for bz, area in HVDC_AREA_MAP.items()
    ]

    hvdc_geo_frame = gpd.GeoDataFrame(hvdc_geo_frame)
    hvdc_geo_frame = hvdc_geo_frame.set_index("zoneName")

    geo_df = gpd.GeoDataFrame(pd.concat([geo_df, hvdc_geo_frame], axis=0))
    return geo_df


@cache
def get_european_nps(start: pd.Timestamp, end: pd.Timestamp) -> dict[BiddingZonesEnum, pd.Series]:
    nps_map = {}
    with Session() as sess:
        client = get_entsoe_client(sess)
        for bz, area in HVDC_AREA_MAP.items():
            try:
                nps = client.query_net_position(getattr(Area, area), start=start, end=end, dayahead=False)
                nps_map[bz] = nps
            except NoMatchingDataError:
                try:
                    nps = client.query_net_position(getattr(Area, area), start=start, end=end, dayahead=True)
                    nps_map[bz] = nps
                except NoMatchingDataError:
                    index = pd.date_range(start, end, freq="h", tz="utc")
                    values = np.full_like(index, np.nan)
                    nps_map[bz] = pd.Series(values, index=index)
    return nps_map


def update_frame_with_european_nps(
    geo_df: gpd.GeoDataFrame, european_nps: dict[BiddingZonesEnum, pd.Series], insert_at_time: pd.Timestamp
):
    for bz, values in european_nps.items():
        geo_df.loc[bz.value, "Net Position"] = values.loc[insert_at_time]


@cache
def find_min_distance_line(poly1: Polygon | MultiPolygon, poly2: Polygon | MultiPolygon, num_points=100):
    # Step 1: Determine Common Boundary
    common_boundary = poly1.intersection(poly2)

    # Step 2: Generate Points along the Boundary
    if common_boundary.is_empty:
        attempt_virtual_min_distance_line = find_set_of_n_closest_points(poly1, poly2)
        if attempt_virtual_min_distance_line is None:
            return LineString([poly1.centroid, poly2.centroid])
        return attempt_virtual_min_distance_line

    line = fit_best_line(common_boundary)
    return line


@cache
def find_set_of_n_closest_points(poly1: Polygon | MultiPolygon, poly2: Polygon | MultiPolygon) -> LineString | None:
    min_distance = 1e100
    min_fit_orthogonal_line = None
    lines1 = get_bounding_straight_lines(poly1)
    lines2 = get_bounding_straight_lines(poly2)

    for line1 in lines1:
        for line2 in lines2:
            if line1.distance(line2) < min_distance:
                min_fit_orthogonal_line = LineString([line1.centroid, line2.centroid])
                min_distance = line1.distance(line2)

    return min_fit_orthogonal_line


@cache
def shrink_or_swell_shapely_polygon(my_polygon: Polygon, factor=0.10, swell=False):
    """returns the shapely polygon which is smaller or bigger by passed factor.
    If swell = True , then it returns bigger polygon, else smaller"""

    xs = list(my_polygon.exterior.coords.xy[0])
    ys = list(my_polygon.exterior.coords.xy[1])
    x_center = 0.5 * min(xs) + 0.5 * max(xs)
    y_center = 0.5 * min(ys) + 0.5 * max(ys)
    min_corner = geometry.Point(min(xs), min(ys))
    center = geometry.Point(x_center, y_center)
    shrink_distance = center.distance(min_corner) * factor

    # if abs(shrink_distance - center.distance(max_corner)) > 0.001:
    #     raise ValueError('No solution to shrinking')

    if swell:
        my_polygon_resized = my_polygon.buffer(shrink_distance)  # expand
    else:
        my_polygon_resized = my_polygon.buffer(-shrink_distance)  # shrink

    return my_polygon_resized


def get_bounding_straight_lines(poly: Polygon | MultiPolygon) -> list[LineString]:
    if isinstance(poly, MultiPolygon):
        poly = max(poly.geoms, key=lambda a: a.area)

    poly = shrink_or_swell_shapely_polygon(poly)
    lines = []
    for segment_start, segment_end in zip(poly.convex_hull.boundary.coords[:-1], poly.convex_hull.boundary.coords[1:]):
        lines.append(LineString([segment_start, segment_end]))
    return lines


def fit_best_line(multi_obj: MultiLineString | MultiPolygon | LineString) -> LineString:
    # Extract coordinates from MultiLineString
    if isinstance(multi_obj, MultiLineString):
        coordinates = [list(line.coords) for line in multi_obj.geoms]
        flat_coordinates = [point for sublist in coordinates for point in sublist]
    elif isinstance(multi_obj, MultiPolygon):
        flat_coordinates = []
        for polygon in multi_obj.geoms:
            flat_coordinates.extend(polygon.exterior.coords[:-1])
    elif isinstance(multi_obj, LineString):
        flat_coordinates = list(multi_obj.coords)

    # Flatten the list of coordinates

    # Separate x and y coordinates
    x_coords, y_coords = zip(*flat_coordinates)

    # Reshape for linear regression
    x = np.array(x_coords).reshape(-1, 1)
    y = np.array(y_coords)

    # Fit a linear regression model
    model = LinearRegression()
    model.fit(x, y)

    # Use the model to predict y values for the entire domain
    domain_x = np.array(list(set(x_coords)))
    domain_x = np.array([domain_x.min(), domain_x.max()]).reshape((-1, 1))
    domain_y_pred = model.predict(domain_x)

    # Create a LineString from the predicted coordinates
    line_coords = list(zip(domain_x.flatten(), domain_y_pred))
    best_fit_line = LineString(line_coords)
    perpendicular = affinity.rotate(best_fit_line, 90)
    scale_factor = 1 / best_fit_line.length
    perpendicular = affinity.scale(perpendicular, xfact=scale_factor, yfact=scale_factor)
    return perpendicular


def compute_color(input_number: int, colormap_name: str, vmin: int, vmax: int) -> str:
    # Normalize the input_number based on the provided vmin, vmax, and midpoint
    normalized_value = (input_number - vmin) / (vmax - vmin)

    # Define a color scale using Plotly Express
    color_scale = px.colors.get_colorscale(colormap_name)

    # Interpolate the color for the normalized value using numpy
    mapped_color = color_scale[0][1]
    dist = 100

    for color in color_scale:
        if abs(color[0] - normalized_value) < dist:
            dist = abs(color[0] - normalized_value)
            mapped_color = color[1]
    return mapped_color


def compute_contrast_color(base_color: str) -> str:
    # Convert the RGB color to HSL
    rgb = ImageColor.getrgb(base_color)
    h, l, s = colorsys.rgb_to_hls(*[c / 255 for c in rgb])

    # Adjust the hue by 180 degrees to get a contrasting color
    contrast_hue = (h + 0.5) % 1.0
    contrast_saturation = min(1.0, max(0.0, 1.0 - s))

    # Convert the HSL back to RGB
    contrast_color = colorsys.hls_to_rgb(contrast_hue, l, contrast_saturation)
    r, g, b = [int(x * 255) for x in contrast_color]

    return f"rgb({r},{g},{b})"


def get_color_for_point(plot: go.Choropleth, point: Point):
    z_arr = np.sort(np.array(plot.z))
    for i, feature in enumerate(plot.geojson["features"]):
        shape_obj = shape(feature["geometry"])
        if shape_obj.contains(point):
            if np.isnan(z_arr[i]):
                return "black"
            # ref_color = compute_color(z_arr[i], "rdbu", np.nanmin(z_arr), np.nanmax(z_arr))
            # contrast = compute_contrast_color(ref_color)
            contrast = compute_color(z_arr[i], "twilight", np.nanmin(z_arr), np.nanmax(z_arr))
            return contrast
    return "black"


def compute_lines(to_area_center: Point, value: int | float, color: str, line: LineString, **text_kwargs):
    # Workaround to get the arrow at the end of an edge AB

    line_width, text_size, B, S, T, arrow_x, arrow_y, x, y = compute_line_attributes(to_area_center, value, line)

    traces = [
        go.Scattergeo(
            lon=[S[0], T[0], B[0], S[0]],
            lat=[S[1], T[1], B[1], S[1]],
            mode="lines",
            fill="toself",
            fillcolor=color,
            line_color=color,
            showlegend=False,
        ),
        go.Scattergeo(
            lon=x,
            lat=y,
            mode="text",
            showlegend=False,
            textfont=dict(size=text_size, color=color),
            **text_kwargs,
        ),
        go.Scattergeo(
            mode="lines",
            lon=arrow_x,
            lat=arrow_y,
            line=dict(color=color, width=line_width),
            showlegend=False,
        ),
    ]
    return traces


def compute_line_attributes(
    to_area_center: Point, value: int | float, line: LineString
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[Any],
    NDArray[floating[Any]],
    NDArray[floating[Any]],
    list[float],
    list[float],
    list[Any],
    list[Any],
]:
    line_width = np.interp(value, [0, 6000], [2, 5])
    text_size = np.interp(value, [0, 6000], [13, 18])
    width = line_width / 46
    lw = line_width / 10

    distances = np.linspace(0, line.length, 100)
    points: list[Point] = [line.interpolate(distance) for distance in distances]

    if measurement.distance(points[-1], to_area_center) < measurement.distance(points[0], to_area_center):
        line = LineString([points[0], points[-2]])
        A = np.squeeze(np.array(points[-3].xy))
        B = np.squeeze(np.array(points[-1].xy))
    else:
        line = LineString([points[1], points[-1]])
        A = np.squeeze(np.array(points[2].xy))
        B = np.squeeze(np.array(points[0].xy))

    v = B - A
    w = v / np.linalg.norm(v)
    u = np.array([-w[1], w[0]])  # u orthogonal on  w

    P = B - lw * w
    S = P - width * u
    T = P + width * u

    arrow_x, arrow_y = line.xy
    arrow_x = list(arrow_x)
    arrow_y = list(arrow_y)

    x, y = line.centroid.xy
    x = list(x)
    x = [x[0] - 0.3]
    y = list(y)
    y = [y[0] - 0.1]
    return line_width, text_size, B, S, T, arrow_x, arrow_y, x, y


def draw_flow_map_figure(
    geo_df: gpd.GeoDataFrame,
    observed_corridor_values: dict[tuple[BiddingZonesEnum, BiddingZonesEnum], float],
    flow_based_corridor_values: dict[tuple[BiddingZonesEnum, BiddingZonesEnum], float],
    parallel_context: None | joblib.Parallel = None,
):
    logger = getLogger()

    st_fig = time()
    fig = px.choropleth(
        geo_df,
        geojson=geo_df.geometry,
        locations=geo_df.index,
        color="Net Position",
        projection="mercator",
        range_color=[-7500, 7500],
        color_continuous_scale="edge",
        height=1000,
    )
    fig.update_geos(fitbounds="locations", visible=False)
    logger.info(f"Draw fig {time() - st_fig }")
    choropleth = fig.data[0]

    arrow_traces: list[go.Scattergeo] = []
    st_fig = time()

    seen_corridors = set()
    deduoplicated_corridors = []
    for corridor in observed_corridor_values:
        set_corridor = frozenset(corridor)
        if set_corridor not in seen_corridors:
            deduoplicated_corridors.append(corridor)
            seen_corridors.add(set_corridor)

    paralell_loop_fun = joblib.delayed(loop_function)
    run_context = parallel_context if parallel_context is not None else joblib.Parallel()
    arguments = [argument_prep(corridor, geo_df, choropleth) for corridor in deduoplicated_corridors]
    all_arrow_traces = run_context(
        paralell_loop_fun(
            observed_corridor_values[corridor], flow_based_corridor_values[corridor], corridor, *arguments
        )
        for corridor, arguments in zip(deduoplicated_corridors, arguments)
    )
    arrow_traces = [trace for subarray in all_arrow_traces for trace in subarray]

    logger.info(f"Draw arrows {time() - st_fig } for N = {len(observed_corridor_values)}")
    fig.add_traces(arrow_traces)
    return fig


def argument_prep(
    corridor: tuple[BiddingZonesEnum, BiddingZonesEnum], geo_df: gpd.GeoDataFrame, choropleth: go.Choropleth
):
    try:
        from_poly = geo_df.loc[ZONE_MAP_WITH_HVDC[corridor[0]], "geometry"]
    except KeyError:
        return None, None, None

    try:
        to_poly = geo_df.loc[ZONE_MAP_WITH_HVDC[corridor[1]], "geometry"]
    except KeyError:
        return None, None, None

    color = get_color_for_point(choropleth, to_poly.centroid)
    return color, from_poly, to_poly


def loop_function(
    value: float | int,
    fb_value: float | int,
    corridor: tuple[BiddingZonesEnum, BiddingZonesEnum],
    color: str | None,
    from_poly: Polygon | MultiPolygon | None,
    to_poly: Polygon | MultiPolygon | None,
) -> list[go.Scattergeo]:
    if color is None or from_poly is None or to_poly is None:
        return []

    if value < 0:
        corridor = (corridor[1], corridor[0])
        from_poly, to_poly = to_poly, from_poly
        value = -1 * value
        fb_value = -1 * fb_value

    corridor_line = find_min_distance_line(from_poly, to_poly)

    loop_traces = compute_lines(
        to_poly.centroid, value, color, corridor_line, text=f"OBS {value:.0f}", textposition="top left"
    )
    loop_traces += compute_lines(
        to_poly.centroid,
        fb_value,
        color,
        corridor_line,
        text=f"FB {fb_value:.0f}",
        textposition="bottom left",
    )
    return loop_traces
