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
    
    return idxptr, indices, csr_weights, csr_edges, np.argsort(sort_idx)


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
def radiation_model(
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


@njit(parallel=PARALLEL)
def local_detour_costs(
    idxptr: np.ndarray,
    indices: np.ndarray,
    weights: np.ndarray,
    # traffic_ij: np.ndarray,
    n_vertices: int,
    max_cost: float = np.inf,
) -> np.ndarray:
    n_edges = len(indices)
    criticality = np.zeros(n_edges, dtype=np.float32)

    assert len(indices) == len(weights)
    
    for u in range(n_vertices):
        print(f"Computing local detour costs for node {u + 1} / {n_vertices}")
        for edge_idx in range(idxptr[u], idxptr[u + 1]):
            v = indices[edge_idx]
            # flow = traffic_ij[edge_idx]
            
            # if flow <= 0:
                # continue
            
            original_weight = weights[edge_idx]
            weights[edge_idx] = np.inf
            
            # 2. Find local detour u -> v
            # Note: max_dist can be original_weight * 5 to speed up search
            dists, _ = dijkstra_with_heap(
                idxptr, indices, weights, u, n_vertices,
                max_dist=max_cost
            )
            detour_dist = dists[v]
            
            if detour_dist < max_cost:
                criticality[edge_idx] = detour_dist
            else: # bridge edge
                criticality[edge_idx] = np.inf
            
            weights[edge_idx] = original_weight
            
    return criticality
