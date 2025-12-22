# %%
import numpy as np
import pandas as pd
from numba import njit

PARALLEL = True

def edges_to_csr(
    edges: np.ndarray,
    weights: np.ndarray,
    n_vertices: int,
    directed: bool = False
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Convert edge list to CSR format.
    
    Args:
        edges: (n_edges, 2) array of (source, target) pairs
        weights: (n_edges,) edge weights
        n_vertices: number of vertices
        directed: if False, add reverse edges
    
    Returns:
        idxptr, indices, csr_weights in CSR format
    """
    if not directed:
        # add reverse edges
        edges = np.vstack([edges, edges[:, ::-1]])
        weights = np.concatenate([weights, weights])
    
    n_edges = len(edges)
    
    # sort by source vertex
    sort_idx = np.lexsort((edges[:, 1], edges[:, 0]))
    edges = edges[sort_idx]
    weights = weights[sort_idx]
    
    # build index ptr
    idxptr = np.zeros(n_vertices + 1, dtype=np.int64)
    for i in range(n_edges):
        idxptr[edges[i, 0] + 1] += 1
    idxptr = np.cumsum(idxptr)
    
    # indices and weights are now just the sorted arrays
    indices = edges[:, 1].astype(np.int64)
    csr_weights = weights.astype(np.float64)
    csr_edges = edges.astype(np.int64)
    
    return idxptr, indices, csr_weights, csr_edges


@njit(parallel=PARALLEL)
def dijkstra(
    idxptr: np.ndarray,
    indices: np.ndarray,
    weights: np.ndarray,
    source: int,
    n_vertices: int,
    max_dist: float = np.inf,
) -> tuple[np.ndarray, np.ndarray]:
    """Dijkstra with array scan. O(V^2). Better for dense graphs or small max_dist."""
    distances = np.full(n_vertices, np.inf, dtype=np.float64)
    predecessors = np.full(n_vertices, -1, dtype=np.int64)
    visited = np.zeros(n_vertices, dtype=np.bool_)
    
    distances[source] = 0.0
    predecessors[source] = source
    
    for _ in range(n_vertices):
        # find unvisited min
        min_dist = np.inf
        u = -1
        for i in range(n_vertices):
            if not visited[i] and distances[i] < min_dist:
                min_dist = distances[i]
                u = i
        
        if u == -1 or min_dist > max_dist:
            break
        
        visited[u] = True
        
        for edge_idx in range(idxptr[u], idxptr[u + 1]):
            v = indices[edge_idx]
            new_dist = min_dist + weights[edge_idx]
            if new_dist < distances[v]:
                distances[v] = new_dist
                predecessors[v] = u
    
    return distances, predecessors


@njit(parallel=PARALLEL)
def dijkstra_with_heap(
    idxptr: np.ndarray,
    indices: np.ndarray,
    weights: np.ndarray,
    source: int,
    n_vertices: int,
    max_dist: float = np.inf,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Dijkstra's algorithm with binary heap. Better for sparse graphs.
    
    Args:
        idxptr: CSR row (index) pointers (length n_vertices + 1)
        indices: CSR column indices (length n_edges)
        weights: CSR edge weights (length n_edges)
        source: source vertex
        n_vertices: number of vertices in graph
        max_dist: stop exploring beyond this distance
    
    Returns:
        distances: shortest distance from source to each vertex (inf if unreachable)
        predecessors: predecessor of each vertex on shortest path (-1 if unreachable, source for source)
    """
    distances = np.full(n_vertices, np.inf, dtype=np.float64)
    predecessors = np.full(n_vertices, -1, dtype=np.int64)
    visited = np.zeros(n_vertices, dtype=np.bool_)
    
    # binary heap arrays
    heap_dist = np.empty(n_vertices + 1, dtype=np.float64)
    heap_node = np.empty(n_vertices + 1, dtype=np.int64)
    heap_size = 0
    
    # initialise source
    distances[source] = 0.0
    predecessors[source] = source
    
    # push source to heap
    heap_size = 1
    heap_dist[1] = 0.0
    heap_node[1] = source
    
    while heap_size > 0:
        # pop minimum
        dist_u = heap_dist[1]
        u = heap_node[1]
        
        # move last element to root and sift down
        last_dist = heap_dist[heap_size]
        last_node = heap_node[heap_size]
        heap_size -= 1
        
        if heap_size > 0:
            pos = 1
            while pos * 2 <= heap_size:
                child = pos * 2
                if child + 1 <= heap_size and heap_dist[child + 1] < heap_dist[child]:
                    child += 1
                if last_dist <= heap_dist[child]:
                    break
                heap_dist[pos] = heap_dist[child]
                heap_node[pos] = heap_node[child]
                pos = child
            heap_dist[pos] = last_dist
            heap_node[pos] = last_node
        
        # skip if already visited or beyond max_dist
        if visited[u] or dist_u > max_dist:
            continue
        visited[u] = True
        
        # relax edges from u
        for edge_idx in range(idxptr[u], idxptr[u + 1]):
            v = indices[edge_idx]
            if visited[v]:
                continue
            
            new_dist = dist_u + weights[edge_idx]
            if new_dist < distances[v]:
                distances[v] = new_dist
                predecessors[v] = u
                
                # push to heap (sift up)
                heap_size += 1
                pos = heap_size
                while pos > 1 and new_dist < heap_dist[pos // 2]:
                    heap_dist[pos] = heap_dist[pos // 2]
                    heap_node[pos] = heap_node[pos // 2]
                    pos //= 2
                heap_dist[pos] = new_dist
                heap_node[pos] = v
    
    return distances, predecessors


@njit(parallel=PARALLEL)
def compute_flux_for_origin(
    a: int,
    m_a: float,
    dest_nodes: np.ndarray,
    dest_pops: np.ndarray,
    costs_a: np.ndarray,
    min_cost: float,
    max_cost: float,
    zeta: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute radiation flux from origin a to all valid destinations.
    
    Returns:
        valid_indices: indices into dest_nodes for valid OD pairs
        fluxes: flux values for valid pairs
        s_abs: intervening opportunities for valid pairs
    """    
    # filter valid destinations (reachable and within cost range)
    valid_mask = (costs_a >= min_cost) & (costs_a < max_cost)
    n_valid = np.sum(valid_mask)
    
    if n_valid == 0:
        return (
            np.empty(0, dtype=np.int64),
            np.empty(0, dtype=np.float64),
            np.empty(0, dtype=np.float64),
        )
    
    # sort valid destinations by cost (for intervening opportunities)
    valid_idx = np.where(valid_mask)[0]
    sort_order = np.argsort(costs_a[valid_idx])
    sorted_idx = valid_idx[sort_order]
    
    # compute s_ab (cumulative population of closer nodes)
    s_abs = np.empty(n_valid, dtype=np.float64)
    cumsum = 0.0
    for i in range(n_valid):
        s_abs[i] = cumsum
        cumsum += dest_pops[sorted_idx[i]]
    
    # compute flux
    fluxes = np.empty(n_valid, dtype=np.float64)
    for i in range(n_valid):
        idx = sorted_idx[i]
        n_b = dest_pops[idx]
        s_ab = s_abs[i]
        denom = (m_a + s_ab) * (m_a + s_ab + n_b)
        if denom > 0:
            fluxes[i] = zeta * (m_a * m_a * n_b) / denom
        else:
            fluxes[i] = 0.0
    
    return sorted_idx, fluxes, s_abs


@njit(parallel=PARALLEL)
def accumulate_edge_traffic(
    a: int,
    n_vertices: int,
    idxptr: np.ndarray,
    indices: np.ndarray,
    costs: np.ndarray,
    predecessors: np.ndarray,
    dest_nodes: np.ndarray,
    sorted_idx: np.ndarray,
    fluxes: np.ndarray,
    traffic_ij: np.ndarray,
) -> None:
    """
    Back-propagate fluxes from destinations to source along shortest path tree.
    Accumulates traffic into traffic_ij array (modified in place).
    """
    # assign flux to dest_nodes
    node_flux = np.zeros(n_vertices, dtype=np.float64)
    for i in range(len(sorted_idx)):
        idx = sorted_idx[i]
        b = dest_nodes[idx]
        node_flux[b] += fluxes[i]

    # get reachable nodes (excl. source)
    reachable = np.empty(n_vertices, dtype=np.int64)
    reachable_cost = np.empty(n_vertices, dtype=np.float64)
    n_reachable = 0
    for v in range(n_vertices):
        if costs[v] < np.inf and v!= a:
            reachable[n_reachable] = v
            reachable_cost[n_reachable] = costs[v]
            n_reachable += 1

    # trim and sort descending (leaves first) using argsort
    reachable = reachable[:n_reachable]
    reachable_cost = reachable_cost[:n_reachable]
    order = np.argsort(-reachable_cost)

    # back-propagate flux to edges
    for i in range(n_reachable):
        v = reachable[order[i]]
        flux_v = node_flux[v]
        if flux_v <= 0:
            continue
        pred = predecessors[v]
        if pred == -1 or pred == v:
            continue
        # find edge index pred -> v
        for edge_idx in range(idxptr[pred], idxptr[pred + 1]):
            if indices[edge_idx] == v:
                traffic_ij[edge_idx] += flux_v
                break
        node_flux[pred] += flux_v


@njit(parallel=PARALLEL)
def radiation_model_core(
    idxptr: np.ndarray,
    indices: np.ndarray,
    weights: np.ndarray,
    n_vertices: int,
    origin_nodes: np.ndarray,
    dest_nodes: np.ndarray,
    populations: np.ndarray,
    min_cost: float,
    max_cost: float,
    zeta: float,
    flux_threshold: float = 1.0,
    use_heap: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Core radiation model loop.
    
    Returns:
        out_a, out_b, out_flux, out_cost, out_s_ab, out_m_a, out_n_b
    """
    n_origins = len(origin_nodes)
    n_dests = len(dest_nodes)
    n_edges = len(indices)
    dest_pops = populations[dest_nodes]
    
    # preallocate (overestimate, trim later)
    max_results = n_origins * n_dests
    out_a = np.empty(max_results, dtype=np.int64)
    out_b = np.empty(max_results, dtype=np.int64)
    out_flux = np.empty(max_results, dtype=np.float64)
    out_cost = np.empty(max_results, dtype=np.float64)
    out_s_ab = np.empty(max_results, dtype=np.float64)
    out_m_a = np.empty(max_results, dtype=np.float64)
    out_n_b = np.empty(max_results, dtype=np.float64)
    traffic_ij = np.zeros(n_edges, dtype=np.float64)
    
    result_idx = 0
    
    for i_a in range(n_origins):
        print(f"Processing origin {i_a + 1} / {n_origins}")  
        # shortest
        a = origin_nodes[i_a]
        m_a = populations[a]
        
        # shortest paths from a
        if use_heap:
            costs_a, predecessors_a = dijkstra_with_heap(idxptr, indices, weights, a, n_vertices, max_cost)
        else:
            costs_a, predecessors_a = dijkstra(idxptr, indices, weights, a, n_vertices, max_cost)
                
        # compute fluxes
        sorted_idx, fluxes_a, s_abs = compute_flux_for_origin(
            a, m_a, dest_nodes, dest_pops, costs_a, min_cost, max_cost, zeta
        )

        accumulate_edge_traffic(
            a, n_vertices, idxptr, indices, costs_a, predecessors_a,
            dest_nodes, sorted_idx, fluxes_a, traffic_ij
        )
        
        # store results above threshold
        for i in range(len(sorted_idx)):
            if fluxes_a[i] >= flux_threshold:
                idx = sorted_idx[i]
                out_a[result_idx] = a
                out_b[result_idx] = dest_nodes[idx]
                out_flux[result_idx] = fluxes_a[i]
                out_cost[result_idx] = costs_a[idx]
                out_s_ab[result_idx] = s_abs[i]
                out_m_a[result_idx] = m_a
                out_n_b[result_idx] = dest_pops[idx]
                result_idx += 1
    
    print("Finished. Trimming results...")
    # trim to actual size
    return (
        out_a[:result_idx],
        out_b[:result_idx],
        out_flux[:result_idx],
        out_cost[:result_idx],
        out_s_ab[:result_idx],
        out_m_a[:result_idx],
        out_n_b[:result_idx],
        traffic_ij,
    )

# %%
if __name__ == "__main__":
    import os
    import geopandas as gpd

    def make_indices_mapping(ids: np.ndarray) -> dict:
        """Create a mapping from arbitrary IDs to contiguous integer indices."""
        unique_ids = np.unique(ids)
        id_to_index = {id_: idx for idx, id_ in enumerate(unique_ids)}
        index_to_id = {idx: id_ for idx, id_ in enumerate(unique_ids)}
        return id_to_index, index_to_id
    
    outdir = "/Users/alison/Downloads/flows/road_traffic"
    road_path = "../../results/assets/tza_roads_edges/dar_es_salaam.geoparquet"
    pops_path = "/Users/alison/Downloads/flows/road_weights/tza_roads_weights.parquet"
    pops_col = "pop_2030"
    
    os.makedirs(outdir, exist_ok=True)

    # create road graph
    roads = gpd.read_parquet(road_path)
    roads["length_km"] = roads["length_m"] * 1e-3
    road_ids = np.array(list(set(roads["from_id"]).union(set(roads["to_id"]))))
    id_to_index, index_to_id = make_indices_mapping(road_ids)
    roads["from_idx"] = roads["from_id"].map(id_to_index)
    roads["to_idx"] = roads["to_id"].map(id_to_index)
    edges = roads[["from_idx", "to_idx"]].to_numpy(dtype=np.int64)
    weights = roads["length_km"].to_numpy(dtype=np.float64)
    n_vertices = len(set(roads["from_idx"]).union(set(roads["to_idx"])))

    # create a populations array
    pops_df = gpd.read_parquet(pops_path)
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
    print(origin_nodes.shape) # origin_nodes.shape

    idxptr, indices, csr_weights, csr_edges = edges_to_csr(edges, weights, n_vertices, directed=False)
    print(csr_weights.shape) # print(csr_weights.shape)

    # run core
    *res, traffic = radiation_model_core(
        idxptr, indices, csr_weights, n_vertices,
        origin_nodes, dest_nodes, pops,
        min_cost=0,
        max_cost=50.0,
        zeta=1.0,
        flux_threshold=10.0,
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
    
    print(od_matrix.shape) # (62190319, 7) | (146828236, 7)

    # %%
    fig,ax = plt.subplots()
    od_matrix[od_matrix["flux"] > 0]["flux"].plot.hist(ax=ax, bins=1000)
    ax.set_yscale('log')
    ax.set_xscale('log')
    
    # %%
    edge_ids = roads[["id", "from_idx", "to_idx"]].set_index(["from_idx", "to_idx"]).to_dict()
    edge_ids_rev = roads[["id", "to_idx", "from_idx"]].set_index(["to_idx", "from_idx"]).to_dict()
    edge_ids = {**edge_ids["id"], **edge_ids_rev["id"]}


    # %%
    traffic_df = pd.DataFrame({
        "from_idx": csr_edges[:, 0],
        "to_idx": csr_edges[:, 1],
        "traffic": traffic
    })

    traffic_df["id"] = traffic_df.apply(
        lambda row: edge_ids.get((row["from_idx"], row["to_idx"]), None),
        axis=1
    )
    traffic_df.head()
    # %%
    traffic_df = traffic_df.groupby(["id"], as_index=False)[["traffic"]].sum()
    traffic_gdf = traffic_df.merge(
        roads,
        left_on=["id"],
        right_on=["id"],
        how="left"
    )

    traffic_gdf = gpd.GeoDataFrame(traffic_gdf, geometry="geometry", crs=roads.crs)
    traffic_gdf.to_file(os.path.join(outdir, "dar_es_salaam.gpkg"), driver="GPKG")
    print(traffic_gdf.head())

    # %%
    for col in traffic_gdf.columns:
        print(col)
    
    # %%
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.scatter(traffic_gdf["traffic_aadt"], traffic_gdf["traffic"], alpha=0.1)
    ax.set_xlabel("Observed AADT")
    ax.set_ylabel("Modeled Traffic")
# %% DEV BELOW HERE

def radiation_model(
    edges: np.ndarray,
    edge_weights: np.ndarray,
    n_vertices: int,
    origin_nodes: np.ndarray,
    dest_nodes: np.ndarray,
    populations: np.ndarray,
    min_cost: float = 0.0,
    max_cost: float = np.inf,
    zeta: float = 1.0,
    flux_threshold: float = 1e-4,
    directed: bool = False,
    use_heap: bool = True,
) -> pd.DataFrame:
    """
    Radiation model for estimating OD flows.
    
    Args:
        edges: (n_edges, 2) array of (source, target) pairs
        edge_weights: (n_edges,) edge costs
        n_vertices: number of vertices
        origin_nodes: array of origin vertex indices
        dest_nodes: array of destination vertex indices
        populations: (n_vertices,) population at each vertex
        min_cost: minimum cost threshold
        max_cost: maximum cost threshold
        zeta: scaling factor
        flux_threshold: minimum flux to include in output
        directed: whether graph is directed
        use_heap: use heap-based Dijkstra (faster for sparse graphs)
    
    Returns:
        DataFrame with columns: a, b, m_a, n_b, s_ab, cost, flux
    """
    # convert to CSR
    idxptr, indices, weights = edges_to_csr(edges, edge_weights, n_vertices, directed)
    
    # ensure correct dtypes
    origin_nodes = origin_nodes.astype(np.int64)
    dest_nodes = dest_nodes.astype(np.int64)
    populations = populations.astype(np.float64)
    
    # run core
    out_a, out_b, out_flux, out_cost, out_s_ab, out_m_a, out_n_b = radiation_model_core(
        idxptr, indices, weights, n_vertices,
        origin_nodes, dest_nodes, populations,
        min_cost, max_cost, zeta, flux_threshold, use_heap
    )
    
    return pd.DataFrame({
        'a': out_a,
        'b': out_b,
        'm_a': out_m_a,
        'n_b': out_n_b,
        's_ab': out_s_ab,
        'cost': out_cost,
        'flux': out_flux,
    })


# formal tests
def test_dijkstra():
    """Test on a simple graph."""
    #     1
    #  0 --- 1
    #  |     |
    # 2|     |1
    #  |     |
    #  2 --- 3
    #     1
    
    edges = np.array([
        [0, 1],
        [0, 2],
        [1, 3],
        [2, 3],
    ], dtype=np.int64)
    weights = np.array([1.0, 2.0, 1.0, 1.0])
    
    idxptr, indices, csr_weights = edges_to_csr(edges, weights, n_vertices=4, directed=False)
    
    print("CSR representation:")
    print(f"  idxptr: {idxptr}")
    print(f"  indices: {indices}")
    print(f"  weights: {csr_weights}")
    
    distances, predecessors = dijkstra(idxptr, indices, csr_weights, source=0, n_vertices=4)
    
    print(f"\nFrom source 0:")
    print(f"  distances: {distances}")  # should be [0, 1, 2, 2]
    print(f"  predecessors: {predecessors}")  # should be [0, 0, 0, 1] or [0, 0, 0, 2]
    
    assert np.allclose(distances, [0, 1, 2, 2]), f"Expected [0, 1, 2, 2], got {distances}"
    print("\n✓ Test passed!")


if __name__ == "__main__":
    test_dijkstra()