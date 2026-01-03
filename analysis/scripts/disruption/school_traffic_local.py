"""Calculate school traffic flows using the radiation model.
https://doi.org/10.1038/ncomms6347
"""
# %%
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path
import time
from contextlib import contextmanager
import traffic

# parameters
outdir = "/Users/alison/Downloads/flows/school_traffic"
# road_path = "../../results/assets/tza_roads_edges/dar_es_salaam.geoparquet"
road_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet"
pops_path = "/Users/alison/Downloads/flows/school_weights/tza_roads_weights.gpkg"
figdir = "/Users/alison/Local/github/oia-tanzania-2025/analysis/figures/school_traffic"
pops_col = "population"
max_cost = [120.0, np.inf][0]  # minutes
zeta = [None, 1.0][1]  # None to read from pops file


@contextmanager
def timer(name="Operation"):
    """use as: with timer("my operation"): ..."""
    start = time.time()
    yield
    print(f"{name}: {time.time() - start:.2f}s")


def walking_time(df:pd.DataFrame) -> pd.Series:
    speed_map = {
        'asphalt concrete': 5.0,
        'concrete': 5.0,
        'dbst': 4.5,
        'gravel': 3.5,
        'earthern': 3.5,
        'non engineered': 3.5
    }
    speed_kmph = df['road_surface_type'].map(speed_map).fillna(3.5)
    time_hours = df['length_km'] / speed_kmph
    time_minutes = time_hours * 60.0
    return time_minutes


def make_indices_mapping(ids: np.ndarray) -> dict:
    """Create a mapping from arbitrary IDs to contiguous integer indices."""
    unique_ids = np.unique(ids)
    id_to_index = {id_: idx for idx, id_ in enumerate(unique_ids)}
    index_to_id = {idx: id_ for idx, id_ in enumerate(unique_ids)}
    return id_to_index, index_to_id


def millions(x, pos):
    """The two args are the value and tick position"""
    return f"{x * 1e-6:.1f} M"


if __name__ == "__main__":
    os.makedirs(figdir, exist_ok=True)
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, Path(road_path).stem)

    # create road graph
    roads = gpd.read_parquet(road_path)
    roads["length_km"] = roads["length_m"] * 1e-3
    roads["walking_time"] = walking_time(roads)

    # tidy up topology
    roads["self_loop"] = roads["from_id"] == roads["to_id"]
    roads = roads[~roads["self_loop"]].copy()

    # create edges array
    road_ids = np.array(list(set(roads["from_id"]).union(set(roads["to_id"]))))
    id_to_index, index_to_id = make_indices_mapping(road_ids)
    roads["from_idx"] = roads["from_id"].map(id_to_index)
    roads["to_idx"] = roads["to_id"].map(id_to_index)
    edges = roads[["from_idx", "to_idx"]].to_numpy(dtype=np.int64)
    weights = roads["walking_time"].to_numpy(dtype=np.float64)
    n_vertices = len(set(roads["from_idx"]).union(set(roads["to_idx"])))

    # create a populations array
    pops_df = gpd.read_file(pops_path)
    zeta = zeta or pops_df["zeta"].iloc[0]
    print(f"Using ζ = {zeta:.4f}")

    pops_df = pops_df[["id", "school", pops_col]].rename(columns={pops_col: "pop"}).copy()
    pops_df["idx"] = pops_df["id"].map(id_to_index)
    pops_df = pops_df.dropna(subset=["idx"]).copy()
    pops_df["idx"] = pops_df["idx"].astype(np.int64)
    pops_df = pops_df.set_index("idx")[["school","pop"]].sort_index()
    pops = np.zeros(n_vertices, dtype=np.float64)
    for idx, row in pops_df.iterrows():
        pops[idx] = row["pop"]

    # split origin/destination nodes
    origin_nodes = pops_df[pops_df["school"] == 0].index.to_numpy(dtype=np.int32)
    dest_nodes = pops_df[pops_df["school"] == 1].index.to_numpy(dtype=np.int32)
    total_demand = pops[origin_nodes].sum()
    total_capacity = pops[dest_nodes].sum()
    print(f"Total capacity: {total_capacity:,.0f}")
    print(f"Total demand: {total_demand:,.0f}")

    # compressed sparse row graph
    csr_data = traffic.edges_to_csr(edges, weights, n_vertices, directed=False)
    idxptr, indices, csr_weights, csr_edges, sort_idx = csr_data

    # traffic flows
    with timer("radiation model"):
        *res, edge_idxs, od_indices, flows = traffic.radiation_model(
            idxptr, indices, csr_weights, n_vertices,
            origin_nodes, dest_nodes, pops,
            min_cost=0,
            max_cost=max_cost,
            zeta=1.0,
            flux_threshold=0.0,
            use_heap=True
        )

    out_a, out_b, out_flux, out_cost, out_s_ab, out_m_a, out_n_b = res
    # %%
    od_matrix = pd.DataFrame({
        'a': out_a,
        'b': out_b,
        'm_a': out_m_a,
        'n_b': out_n_b,
        's_ab': out_s_ab,
        'cost': out_cost,
        'flux': out_flux,
    })

    # %% figures: average walking time to school
    fig, ax = plt.subplots(figsize=(4, 2.5))
    ax.hist(od_matrix['cost'], weights=od_matrix['flux'],
             bins=50, color='skyblue', edgecolor='k')
    ax.set_xlabel("Walking time to school (mins)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(millions))
    fig.savefig(os.path.join(figdir, "od_matrix_cost_histogram.png"),
                dpi=300, transparent=True, bbox_inches='tight');
    print(f"Mean walking time: {np.average(od_matrix['cost'], weights=od_matrix['flux']):.2f} mins")
    print(f"\nSaved figure to {figdir}/od_matrix_cost_histogram.png\n")

    # %% total flux on network
    total_flux = od_matrix['flux'].sum()
    print(f"Total school-trips within {max_cost} mins: {total_flux:,.0f}")
    print(f"Total school-going demand: {total_demand:,.0f}")
    print(f"{total_demand - total_flux:,.0f} people unable to reach school within {max_cost} mins")

    # %%
    with timer("local detour costs"):
        detour_costs = traffic.local_detour_costs(
            idxptr, indices, csr_weights, n_vertices,
            max_cost=max_cost * 10
        )
    
    # map back to road edges
    edge_ids = roads[["id", "from_idx", "to_idx"]].set_index(["from_idx", "to_idx"]).to_dict()
    edge_ids_rev = roads[["id", "to_idx", "from_idx"]].set_index(["to_idx", "from_idx"]).to_dict()
    edge_ids = {**edge_ids["id"], **edge_ids_rev["id"]}

    # re-order flows to match edges
    flows = flows[sort_idx]
    flows_fwd = flows[:len(edges)]
    flows_bwd = flows[len(edges):]
    flows = flows_fwd + flows_bwd

    # re-order detour costs to match edges
    detour_costs = detour_costs[sort_idx]
    detour_costs_bwd = detour_costs[len(edges):]
    detour_costs = detour_costs[:len(edges)]
    detour_costs = np.minimum(detour_costs, detour_costs_bwd)
    # assert np.allclose(detour_costs, detour_costs_bwd)

    # %% output traffic info
    traffic_df = pd.DataFrame({
        "from_idx": edges[:, 0],
        "to_idx": edges[:, 1],
        "traffic": flows,
        "detour_cost": detour_costs
    })

    roads = roads.reset_index(drop=True)
    assert traffic_df["from_idx"].equals(roads["from_idx"]), "'from' indices don't match!"
    assert traffic_df["to_idx"].equals(roads["to_idx"]), "'to' indices don't match!"


    traffic_gdf = pd.concat([
        roads, traffic_df[["traffic", "detour_cost"]]
    ], axis=1)
    traffic_gdf["cost_unit"] = "walking time (mins)"

    # save
    traffic_gdf = gpd.GeoDataFrame(traffic_gdf, geometry="geometry", crs=roads.crs)
    traffic_gdf.to_file(outpath)
    print(f"Saved traffic to {outpath}")
    print(traffic_gdf.head())
    # %%

    for col in traffic_gdf.columns:
        print(col)
    
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.scatter(traffic_gdf["traffic_aadt"], traffic_gdf["traffic"], alpha=0.1)
    ax.set_xlabel("Observed AADT")
    ax.set_ylabel("Modeled Traffic")

# %% 

