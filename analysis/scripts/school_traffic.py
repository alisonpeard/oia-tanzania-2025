# %%
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import time
from contextlib import contextmanager
import traffic

# parameters
i = 1
outdir = "/Users/alison/Downloads/flows/road_traffic"
road_path = [
    "../../results/assets/tza_roads_edges/dar_es_salaam.geoparquet",
    "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet"
][i]
outpath = [os.path.join(outdir, "dar_es_salaam.gpkg"), os.path.join(outdir, "tza_roads_edges.gpkg")][i]
pops_path = "/Users/alison/Downloads/flows/school_weights/tza_roads_weights.gpkg"
pops_col = "population"


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

if __name__ == "__main__":

    os.makedirs(outdir, exist_ok=True)

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
    zeta = pops_df["zeta"][0]
    print(f"Using ζ = {zeta:.4f}")

    pops_df = pops_df[["id", pops_col]].rename(columns={pops_col: "pop"}).copy()
    pops_df["idx"] = pops_df["id"].map(id_to_index)
    pops_df = pops_df.dropna(subset=["idx"]).copy()
    pops_df["idx"] = pops_df["idx"].astype(np.int64)
    pops_df = pops_df.set_index("idx")[["pop"]].sort_index()
    pops = np.zeros(n_vertices, dtype=np.float64)
    for idx, row in pops_df.iterrows():
        pops[idx] = row["pop"]

    # start
    origin_nodes = dest_nodes = np.array(list(index_to_id.keys()), dtype=np.int64)
    csr_data = traffic.edges_to_csr(edges, weights, n_vertices, directed=False)
    idxptr, indices, csr_weights, csr_edges, sort_idx = csr_data

    with timer("radiation model"):
        *res, flows = traffic.radiation_model(
            idxptr, indices, csr_weights, n_vertices,
            origin_nodes, dest_nodes, pops,
            min_cost=0,
            max_cost=120.0,
            zeta=zeta,
            flux_threshold=0.0,
            use_heap=True
        )

    out_a, out_b, out_flux, out_cost, out_s_ab, out_m_a, out_n_b = res

    od_matrix = pd.DataFrame({
        'a': out_a,
        'b': out_b,
        'm_a': out_m_a,
        'n_b': out_n_b,
        's_ab': out_s_ab,
        'cost': out_cost,
        'flux': out_flux,
    })
    
    print(od_matrix.shape)


    with timer("local detour costs"):
        detour_costs = traffic.local_detour_costs(
            idxptr, indices, csr_weights, n_vertices,
            max_cost=120.0
        )

    # %%
    if False:
        fig, axs = plt.subplots(1, 2)

        ax = axs[0]
        od_matrix[od_matrix["flux"] > 0]["flux"].plot.hist(ax=ax, bins=1000)
        ax.set_yscale('log')
        ax.set_xscale('log')
        ax.set_xlabel("Modeled trips (flux)")
        ax.set_ylabel("Count")

        ax = axs[1]
        ax.scatter(od_matrix["cost"], od_matrix["flux"], alpha=0.1)
        ax.set_xlabel("Travel time (minutes)")
        ax.set_ylabel("Modeled trips (flux)")
        ax.set_yscale('log')
    
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
    detour_costs = detour_costs[:len(edges)]
    detour_costs_bwd = detour_costs[len(edges):]
    assert np.allclose(detour_costs, detour_costs_bwd)

    # output traffic info
    traffic_df = pd.DataFrame({
        "from_idx": edges[:, 0],
        "to_idx": edges[:, 1],
        "traffic": flows,
        "detour_cost": detour_costs
    })

    roads = roads.reset_index(drop=True)
    assert traffic_df["from_idx"].equals(roads["from_idx"]), "From indices don't match!"
    assert traffic_df["to_idx"].equals(roads["to_idx"]), "To indices don't match!"


    traffic_gdf = pd.concat([
        roads, traffic_df[["traffic", "detour_cost"]]
    ], axis=1)
    traffic_gdf["cost_unit"] = "walking time (minutes)"

    # save
    traffic_gdf = gpd.GeoDataFrame(traffic_gdf, geometry="geometry", crs=roads.crs)
    traffic_gdf.to_file(outpath, driver="GPKG")
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

