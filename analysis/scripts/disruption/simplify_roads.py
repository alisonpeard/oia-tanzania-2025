import numba
import traffic

def assign_segment_ids(edges_df, from_col='from_id', to_col='to_id'):
    """
    Assign segment IDs by contracting degree-2 nodes.
    """
    edges = edges_df[[from_col, to_col]].values.astype(np.int64)
    n_vertices = edges.max() + 1
    n_edges = len(edges)
    
    # build CSR (undirected)
    dummy_weights = np.ones(n_edges, dtype=np.float64)
    idxptr, indices, *_ = edges_to_csr(edges, dummy_weights, n_vertices, directed=False)
    
    # compute degrees
    degrees = idxptr[1:] - idxptr[:-1]
    
    # build sorted edge lookup: (min_node, max_node, edge_idx)
    edge_keys = np.empty((n_edges, 2), dtype=np.int64)
    for i in range(n_edges):
        u, v = edges[i]
        edge_keys[i, 0] = min(u, v)
        edge_keys[i, 1] = max(u, v)
    
    sort_order = np.lexsort((edge_keys[:, 1], edge_keys[:, 0]))
    sorted_keys = edge_keys[sort_order]
    
    segment_ids = _assign_segments_numba(edges, degrees, idxptr, indices, sorted_keys, sort_order)
    
    edges_df = edges_df.copy()
    edges_df['segment_id'] = segment_ids
    return edges_df


@numba.njit
def _find_edge_binary(sorted_keys, sort_order, u, v):
    """Binary search for edge (u,v) in sorted edge list. O(log n)."""
    lo, hi = min(u, v), max(u, v)
    
    # binary search on first key
    left, right = 0, len(sorted_keys)
    while left < right:
        mid = (left + right) // 2
        if sorted_keys[mid, 0] < lo:
            left = mid + 1
        elif sorted_keys[mid, 0] > lo:
            right = mid
        elif sorted_keys[mid, 1] < hi:
            left = mid + 1
        elif sorted_keys[mid, 1] > hi:
            right = mid
        else:
            return sort_order[mid]
    return -1


@numba.njit
def _extend_segment(node, came_from, edges, degrees, idxptr, indices, 
                    sorted_keys, sort_order, segment_ids, seg_id):
    """Walk along degree-2 nodes, assigning segment IDs to edges."""
    current = node
    prev = came_from
    
    while degrees[current] == 2:
        # find the other neighbor
        next_node = -1
        for k in range(idxptr[current], idxptr[current + 1]):
            if indices[k] != prev:
                next_node = indices[k]
                break
        
        if next_node == -1:
            break
        
        edge_idx = _find_edge_binary(sorted_keys, sort_order, current, next_node)
        if edge_idx == -1 or segment_ids[edge_idx] != -1:
            break
        
        segment_ids[edge_idx] = seg_id
        prev = current
        current = next_node


@numba.njit
def _assign_segments_numba(edges, degrees, idxptr, indices, sorted_keys, sort_order):
    n_edges = len(edges)
    segment_ids = np.full(n_edges, -1, dtype=np.int64)
    current_segment = 0
    
    for e in range(n_edges):
        if segment_ids[e] != -1:
            continue
        
        segment_ids[e] = current_segment
        u, v = edges[e]
        
        _extend_segment(v, u, edges, degrees, idxptr, indices,
                        sorted_keys, sort_order, segment_ids, current_segment)
        _extend_segment(u, v, edges, degrees, idxptr, indices,
                        sorted_keys, sort_order, segment_ids, current_segment)
        
        current_segment += 1
    
    return segment_ids


"""
Network-wide criticality analysis for every single edge.

Re-route traffic for every flood hazard. Treats hazards as maps.
"""
# %%
import os
import time
from tqdm import tqdm
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
from importlib import reload
from contextlib import contextmanager
import traffic

# parameters
outdir = "/Users/alison/Downloads/flows/school_traffic"
# road_path = "../../results/assets/tza_roads_edges/dar_es_salaam.geoparquet"
road_path = "/Volumes/Expansion/02_oia/oia-tanzania-2025/input/assets/tza_roads_edges.parquet"


@contextmanager
def timer(name="Operation"):
    """use as: with timer("my operation"): ..."""
    start = time.time()
    yield
    print(f"{name}: {time.time() - start:.2f}s")



def make_indices_mapping(ids: np.ndarray) -> dict:
    """Create a mapping from arbitrary IDs to contiguous integer indices."""
    unique_ids = np.unique(ids)
    id_to_index = {id_: idx for idx, id_ in enumerate(unique_ids)}
    index_to_id = {idx: id_ for idx, id_ in enumerate(unique_ids)}
    return id_to_index, index_to_id


if __name__ == "__main__":
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, Path(road_path).stem)

    # create road graph
    roads = gpd.read_parquet(road_path)
    roads = roads.reset_index(drop=True)
    road_ids = np.array(list(set(roads["from_id"]).union(set(roads["to_id"]))))
    id_to_index, index_to_id = make_indices_mapping(road_ids)
    roads["from_idx"] = roads["from_id"].map(id_to_index)
    roads["to_idx"] = roads["to_id"].map(id_to_index)
    edges = roads[["from_idx", "to_idx"]].to_numpy(dtype=np.int64)
    weights = roads["length_m"].to_numpy(dtype=np.float64)
    n_vertices = len(set(roads["from_idx"]).union(set(roads["to_idx"])))
    csr_data = traffic.edges_to_csr(edges, weights, n_vertices, directed=False)
    idxptr, indices, csr_weights, csr_edges, sort_idx, orig_to_csr = csr_data

    # compute degrees and assign segments
    degrees = idxptr[1:] - idxptr[:-1]

    # build sorted edge lookup
    n_edges = len(edges)
    edge_keys = np.empty((n_edges, 2), dtype=np.int64)
    for i in range(n_edges):
        u, v = edges[i]
        edge_keys[i, 0] = min(u, v)
        edge_keys[i, 1] = max(u, v)

    sort_order = np.lexsort((edge_keys[:, 1], edge_keys[:, 0]))
    sorted_keys = edge_keys[sort_order]

    # assign segment IDs
    segment_ids = _assign_segments_numba(
        edges, degrees, idxptr, indices, sorted_keys, sort_order
    )
    roads["segment_id"] = segment_ids

    def format_segment_id(seg_id):
        return f"tza_seg_{seg_id:06d}"
    roads["segment_id"] = roads["segment_id"].apply(format_segment_id)

    # now you can groupby segment_id
    # e.g. roads.groupby("segment_id").agg({"length_m": "sum", "traffic": "mean"})
    # %%
    component_counts = roads.groupby("segment_id")["id"].nunique().to_dict()
    component_counts
    # %%
    roads["ncomponents"] = roads["segment_id"].map(component_counts)
    # %%
    roads = roads.sort_values(by="ncomponents", ascending=True)
    roads.plot(column="ncomponents", cmap="viridis_r", legend=True, figsize=(10, 10))
    # %%
    roads[["id", "segment_id", "ncomponents"]].to_csv(
        f"/Users/alison/Downloads/flows/tza_road_simplifications.csv",
        index="id",
    )

# %%
import pandas as pd
path = "/Users/alison/Downloads/flows/tza_road_simplifications.csv"
df = pd.read_csv(path)
print(df["id"].nunique())
print(df["segment_id"].nunique())
# %%
