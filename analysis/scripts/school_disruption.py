"""Should not do. Treats hazards maps as events.

Re-route traffic for every flood hazard. Treats hazards as maps.
"""
# %%
import os
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
import time
from contextlib import contextmanager
import traffic

# parameters
outdir = "/Users/alison/Downloads/flows/school_traffic"
road_path = "../../results/assets/tza_roads_edges/dar_es_salaam.geoparquet"
# road_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet"
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
    
    # %%
    # tidy up topology
    roads["self_loop"] = roads["from_id"] == roads["to_id"]
    roads = roads[~roads["self_loop"]].copy()
    #! start of temporary: to see if it fixes the mismatches in final fluxes
    roads['min_node'] = roads[['from_id', 'to_id']].min(axis=1)
    roads['max_node'] = roads[['from_id', 'to_id']].max(axis=1)
    roads = roads.loc[roads.groupby(['min_node', 'max_node'])['walking_time'].idxmin()].copy()
    roads = roads.drop(columns=['min_node', 'max_node'])
    #! end of temporary
    roads = roads.reset_index(drop=True)

    # %% create edges array
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

    # %% traffic flows
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

    # %%
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

    # total flux on network
    total_flux = od_matrix['flux'].sum()
    print(f"Total school-trips within {max_cost} mins: {total_flux:,.0f}")
    print(f"Total school-going demand: {total_demand:,.0f}")
    print(f"{total_demand - total_flux:,.0f} people unable to reach school within {max_cost} mins")

    # %% re-running Dijkstra for every single edge
    dependency_sort = np.argsort(edge_idxs)
    edge_idxs = edge_idxs[dependency_sort]
    od_indices = od_indices[dependency_sort]
    # %%
    from tqdm import tqdm
    from importlib import reload
    reload(traffic)

    chunk_size = len(edges) // 10
    total_base_fluxes = []
    total_detour_fluxes = []
    total_isolated_fluxes = []
    total_weighted_detours = []

    i = 0
    for start_idx in tqdm(range(0, len(edges), chunk_size)):
        end_idx = min(start_idx + chunk_size, len(edges))
        chunk_edges = edges[start_idx:end_idx]
        
        with timer(f"chunk {i}"):  
            res = traffic.compute_edge_disruptions(
                chunk_edges, edge_idxs, od_indices,
                idxptr, indices, sort_idx, csr_weights,
                out_a, out_b, out_cost, out_flux,
                n_vertices, max_cost
            )
            total_base_fluxes.append(res[0])
            total_detour_fluxes.append(res[1])
            total_isolated_fluxes.append(res[2])
            total_weighted_detours.append(res[3])
        i += 1
        break # for now, to test results
    
    # %%
    flows_fwd = flows[sort_idx][:len(edges)]
    flows_bwd = flows[sort_idx][len(edges):]
    flows_out = flows_fwd + flows_bwd

    # %%

    total_base_fluxes_arr = np.concatenate(total_base_fluxes)
    total_detour_fluxes_arr = np.concatenate(total_detour_fluxes)
    total_isolated_fluxes_arr = np.concatenate(total_isolated_fluxes)
    total_weighted_detours_arr = np.concatenate(total_weighted_detours)

    # quick look at results
    tmp_df = pd.DataFrame({
        "orig_flux": flows_out[:len(total_base_fluxes_arr)],
        "base_flux": total_base_fluxes_arr,
        "detoured_flux": total_detour_fluxes_arr,
        "isolated_flux": total_isolated_fluxes_arr,
        "weighted_detour": total_weighted_detours_arr
    })
    tmp_df["disrupted_flux"] = tmp_df["detoured_flux"] + tmp_df["isolated_flux"]
    tmp_df["disrupted_frac"] = tmp_df["disrupted_flux"] / tmp_df["orig_flux"]
    mask = abs(tmp_df["orig_flux"] - tmp_df["base_flux"]) > 1e-4
    print(f"{tmp_df[mask][['orig_flux', 'base_flux']]=}")

    # %% #! make final results
    res_df = pd.DataFrame({
        "from_idx": edges[:, 0],
        "to_idx": edges[:, 1],
        "orig_flux": flows_out[:len(total_base_fluxes_arr)],
        "base_flux": total_base_fluxes_arr,
        "detoured_flux": total_detour_fluxes_arr,
        "isolated_flux": total_isolated_fluxes_arr,
        "weighted_detour": total_weighted_detours_arr
    })

    res_df["disrupted_flux"] = res_df["detoured_flux"] + res_df["isolated_flux"]
    res_df["disrupted_frac"] = res_df["disrupted_flux"] / res_df["orig_flux"]
    res_df["from_id"] = res_df["from_idx"].map(index_to_id)
    res_df["to_id"] = res_df["to_idx"].map(index_to_id)
    res_df["id"] = roads.set_index(["from_idx", "to_idx"]).index.map(
        roads.set_index(["from_idx", "to_idx"])["id"].to_dict()
    )

    res_df.to_csv(f"~/Desktop/school_costs_dar_es_salaam.csv", index=False)

    # %%
    mask = res_df["disrupted_flux"] - res_df["base_flux"] > 1e-4
    print(f"{res_df[mask][['disrupted_flux', 'base_flux']]=}")

    # %%
    mask = abs(res_df["orig_flux"] - res_df["base_flux"]) > 1e-4
    print(f"{res_df[mask][['orig_flux', 'base_flux']]=}")
    # %%
    
    res_df["disrupted_flux"].sum() / res_df["base_flux"].sum()
    res_df["disrupted_flux"].sum() / res_df["orig_flux"].sum()

    # %% next: local detours
    if False:
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
        # assert np.allclose(detour_costs, detour_costs_bwd) #! check this

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

        # %% load disruption data
        hazcol = "hazard-fluvial_2050_ssp585_rp00100"

        roads = gpd.read_parquet(road_path)
        disruptions = gpd.read_parquet(disrupt_path)
        disruptions["disrupted"] = (disruptions[hazcol] > 0).astype(bool)
        disruptions = disruptions[disruptions["disrupted"]].copy()

        edge_id_map = roads[["id", "from_id", "to_id"]].set_index("id").to_dict()
        disruptions["to_id"] = disruptions.index.map(edge_id_map["to_id"])
        disruptions["from_id"] = disruptions.index.map(edge_id_map["from_id"])
        disruptions["to_idx"] = disruptions["to_id"].map(id_to_index)
        disruptions["from_idx"] = disruptions["from_id"].map(id_to_index)
        assert not disruptions["to_idx"].isna().any(), "Some 'to' IDs not found in roads!"
        assert not disruptions["from_idx"].isna().any(), "Some 'from' IDs not found in roads!"
        disruptions = disruptions[["from_idx", "to_idx"]].copy()

        # %%
        disruptions.set_index(["from_idx", "to_idx"], inplace=True)
        traffic_gdf.set_index(["from_idx", "to_idx"], inplace=True)
        merged = disruptions.join(traffic_gdf[["detour_cost"]], how="inner")
        merged = merged.reset_index()

        # %%
        isolated = merged[~np.isfinite(merged["detour_cost"])].copy()
        rerouted = merged[np.isfinite(merged["detour_cost"])].copy()
        isolated_edges = isolated[["from_idx", "to_idx"]].to_numpy(dtype=np.int64)
        rerouted_edges = rerouted[["from_idx", "to_idx"]].to_numpy(dtype=np.int64)
        detour_costs = rerouted["detour_cost"].to_numpy(dtype=np.float64)

        # %%
        def get_affected_od_rows(u, v):
            packed_query = traffic.safe_pack(u, v)
            start = np.searchsorted(edge_idxs, packed_query, side='left')
            end = np.searchsorted(edge_idxs, packed_query, side='right')
            return od_indices[start:end]
        
        isolated_trips = np.zeros(len(od_matrix), dtype=bool)
        rerouted_trips = np.zeros(len(od_matrix), dtype=bool)
        cumulative_detours = np.zeros(len(od_matrix), dtype=np.float64)
        count_detours = np.zeros(len(od_matrix), dtype=np.int32)
        count_bridges = np.zeros(len(od_matrix), dtype=np.int32)

        for i in range(len(isolated_edges)):
            u, v = isolated_edges[i]
            od_idx = get_affected_od_rows(u, v)
            isolated_trips[od_idx] = True
            count_bridges[od_idx] += 1

        for i in range(len(rerouted_edges)):
            u, v = rerouted_edges[i]
            od_idx = get_affected_od_rows(u, v)
            detour_cost = detour_costs[i]
            rerouted_trips[od_idx] = True
            cumulative_detours[od_idx] += detour_cost
            count_detours[od_idx] += 1

        print(f"Total isolated trips from {len(isolated_edges)} edges: {isolated_trips.sum():,.0f}")
        print(f"Total rerouted trips from {len(rerouted_edges)} edges: {rerouted_trips.sum():,.0f}")

        # sum fluxes of rerouted trips to get
        od_matrix_disrupted = od_matrix.copy()
        od_matrix_disrupted["detour_cost"] = cumulative_detours
        od_matrix_disrupted["detour_count"] = count_detours
        od_matrix_disrupted["bridge_count"] = count_bridges
        od_matrix_disrupted["isolated"] = isolated_trips
        od_matrix_disrupted["rerouted"] = rerouted_trips
        od_matrix_disrupted[od_matrix_disrupted["isolated"]].head()
        od_matrix_disrupted["disrupted"] = od_matrix_disrupted["isolated"] | od_matrix_disrupted["rerouted"]
        od_matrix_disrupted = od_matrix_disrupted[od_matrix_disrupted["disrupted"]].copy()
        print(f"Total disrupted trips: {len(od_matrix_disrupted):,.0f}")
        # %%
        od_matrix_disrupted.to_csv(f"~/Desktop/schools_{hazcol}.csv", index=False)
# %% 

