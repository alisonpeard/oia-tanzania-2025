"""
Radiation model using CSR network representation and Numba JIT compilation.

indices: flattened array of target vertices for each edge.
idxptr: pointer to start of each vertex's edge list in indices.
"""
import numpy as np
import pandas as pd
import numba


PARALLEL = True

# @numba.njit
# def safe_pack(u, v):
#     """Safely pack two int32 into one int64, order-invariant."""
#     if u < v:
#         return (int(u) << 32) | (int(v) & 0xFFFFFFFF)
#     else:
#         return (int(v) << 32) | (int(u) & 0xFFFFFFFF)


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

    # crs mappings
    inverse_sort = np.argsort(sort_idx)
    n_original = len(edges) // 2  # after doubling
    orig_to_csr = np.empty((n_original, 2), dtype=np.int64)
    orig_to_csr[:, 0] = inverse_sort[:n_original]        # forward edges
    orig_to_csr[:, 1] = inverse_sort[n_original:]        # backward edges
    
    return idxptr, indices, csr_weights, csr_edges, inverse_sort, orig_to_csr


@numba.njit
def dijkstra(
    idxptr: np.ndarray,
    indices: np.ndarray,
    weights: np.ndarray,
    source: int,
    n_vertices: int,
    max_dist: float = np.inf,
) -> tuple[np.ndarray, np.ndarray]:
    """Dijkstra with array scan. O(V^2). Better for dense graphs or small max_dist.

    V linear scans of O(V): O(V^2).
    
    Args:
        idxptr: CSR row (index) pointers (length n_vertices + 1)
        indices: CSR column indices (length n_edges)
        weights: CSR edge weights (length n_edges)
        source: source vertex
        n_vertices: number of vertices in graph
        max_dist: stop exploring beyond this distance
    
    Values:
        distances: Array of length n_vertices with shortest
            distance from source to each vertex (inf if unreachable).
        predecessors: Array of length n_vertices with predecessor
            of each vertex on shortest path to source (-1 if unreachable,
            source for source).
    """
    distances = np.full(n_vertices, np.inf, dtype=np.float64)
    predecessors = np.full(n_vertices, -1, dtype=np.int64)
    predecessor_edges = np.full(n_vertices, -1, dtype=np.int64)
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
                predecessor_edges[v] = edge_idx
    
    return distances, predecessors, predecessor_edges


@numba.njit
def dijkstra_with_heap(
    idxptr: np.ndarray,
    indices: np.ndarray,
    weights: np.ndarray,
    source: int,
    n_vertices: int,
    max_dist: float = np.inf
) -> tuple[np.ndarray, np.ndarray]:
    """
    Dijkstra's algorithm with binary heap. Better for sparse graphs.

    O((V + E) log V).
    
    Args:
        idxptr: CSR row (index) pointers (length n_vertices + 1)
        indices: CSR column indices (length n_edges)
        weights: CSR edge weights (length n_edges)
        source: source vertex
        n_vertices: number of vertices in graph
        max_dist: stop exploring beyond this distance
    
    Values:
        distances: Array of length n_vertices with shortest
            distance from source to each vertex (inf if unreachable).
        predecessors: Array of length n_vertices with predecessor
            of each vertex on shortest path to source (-1 if unreachable,
            source for source).
    """
    distances = np.full(n_vertices, np.inf, dtype=np.float64)
    predecessors = np.full(n_vertices, -1, dtype=np.int64)
    predecessor_edges = np.full(n_vertices, -1, dtype=np.int64)
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
        
        # skip if already visited or break if beyond max_dist
        if visited[u]:
            continue
        if dist_u > max_dist:
            break
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
                predecessor_edges[v] = edge_idx
                
                # push to heap (sift up)
                heap_size += 1
                pos = heap_size
                while pos > 1 and new_dist < heap_dist[pos // 2]:
                    heap_dist[pos] = heap_dist[pos // 2]
                    heap_node[pos] = heap_node[pos // 2]
                    pos //= 2
                heap_dist[pos] = new_dist
                heap_node[pos] = v
    
    return distances, predecessors, predecessor_edges


@numba.njit
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
    # new (faster) implementation
    valid_idx = np.empty(len(dest_nodes), dtype=np.int64)

    n_valid = 0
    for i in range(len(dest_nodes)):
        node_idx = dest_nodes[i]
        cost = costs_a[node_idx]
        if cost >= min_cost and cost < max_cost:
            valid_idx[n_valid] = i
            n_valid += 1

    if n_valid == 0:
        return (
            np.empty(0, dtype=np.int64),
            np.empty(0, dtype=np.float64),
            np.empty(0, dtype=np.float64),
        )
    
    valid_idx = valid_idx[:n_valid]
    sort_order = np.argsort(costs_a[dest_nodes[valid_idx]])
    sorted_idx = valid_idx[sort_order]
    
    # compute cumulative population of closer nodes
    s_abs = np.empty(n_valid, dtype=np.float64)
    cumsum = 0.0
    for i in range(n_valid):
        s_abs[i] = cumsum
        cumsum += dest_pops[sorted_idx[i]]
    
    # compute flux
    p_abs = np.empty(n_valid, dtype=np.float64)
    total_probs = 0.0
    for i in range(n_valid):
        idx = sorted_idx[i]
        n_b = dest_pops[idx]
        s_ab = s_abs[i]
        denom = (m_a + s_ab) * (m_a + s_ab + n_b)
        if denom > 0:
            p_ab = m_a * m_a * n_b / denom
        else:
            p_ab = 0.0
        p_abs[i] = p_ab
        total_probs += p_ab

    # normalise fluxes to match total origin population
    total_probs = np.sum(p_abs)
    fluxes = np.zeros(n_valid, dtype=np.float64)
    if (total_probs > 0):
        scale_factor = np.float64(zeta * m_a) / total_probs
        for i in range(n_valid):
            fluxes[i] =  scale_factor * p_abs[i]
    
    return sorted_idx, fluxes, s_abs


@numba.njit
def accumulate_edge_traffic(
    a: int,
    n_vertices: int,
    idxptr: np.ndarray,
    indices: np.ndarray,
    costs: np.ndarray,
    predecessors: np.ndarray,
    predecessor_edges: np.ndarray,
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
        # for edge_idx in range(idxptr[pred], idxptr[pred + 1]):
        #     if indices[edge_idx] == v:
        #         traffic_ij[edge_idx] += flux_v
        #         break
        edge_idx = predecessor_edges[v]
        if edge_idx >= 0:
            traffic_ij[edge_idx] += flux_v
        node_flux[pred] += flux_v


@numba.njit
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
    use_heap: bool = True
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Core radiation model loop.
    
    Returns:
        out_a, out_b, out_flux, out_cost, out_s_ab, out_m_a, out_n_b
    """
    print("Preparing radiation model...")
    n_origins = len(origin_nodes)
    n_dests = len(dest_nodes)
    n_edges = len(indices)
    dest_pops = populations[dest_nodes]
    
    # preallocate (overestimate, trim later)
    print("Allocating output arrays...")
    max_results = n_origins * n_dests
    out_a = np.empty(max_results, dtype=np.int64)
    out_b = np.empty(max_results, dtype=np.int64)
    out_flux = np.empty(max_results, dtype=np.float64)
    out_cost = np.empty(max_results, dtype=np.float64)
    out_s_ab = np.empty(max_results, dtype=np.float64)
    out_m_a = np.empty(max_results, dtype=np.float64)
    out_n_b = np.empty(max_results, dtype=np.float64)
    traffic_ij = np.zeros(n_edges, dtype=np.float64)

    # pre-allocate dependency arrays for OD pairs
    est_dep_size = max_results * 50 
    dep_edge_ids = np.empty(est_dep_size, dtype=np.int64)
    dep_od_indices = np.empty(est_dep_size, dtype=np.int32)
    dep_ptr = 0
    
    result_idx = 0
    
    print("Starting radiation model...")
    for i_a in range(n_origins):
        print(f"Processing origin {i_a + 1} / {n_origins}")  
        # shortest
        a = origin_nodes[i_a]
        m_a = populations[a]
        
        # shortest paths from a
        if use_heap:
            costs_a, predecessors_a, predecessor_edges_a = dijkstra_with_heap(idxptr, indices, weights, a, n_vertices, max_cost)
        else:
            costs_a, predecessors_a, predecessor_edges_a = dijkstra(idxptr, indices, weights, a, n_vertices, max_cost)
                
        # compute fluxes
        sorted_idx, fluxes_a, s_abs = compute_flux_for_origin(
            a, m_a, dest_nodes, dest_pops, costs_a, min_cost, max_cost, zeta
        )

        accumulate_edge_traffic(
            a, n_vertices, idxptr, indices, costs_a, predecessors_a, predecessor_edges_a,
            dest_nodes, sorted_idx, fluxes_a, traffic_ij
        )

        # store results above threshold
        for i in range(len(sorted_idx)):
            if fluxes_a[i] >= flux_threshold:
                idx = sorted_idx[i]
                out_a[result_idx] = a
                out_b[result_idx] = dest_nodes[idx]
                out_flux[result_idx] = fluxes_a[i]
                out_cost[result_idx] = costs_a[dest_nodes[idx]]
                out_s_ab[result_idx] = s_abs[i]
                out_m_a[result_idx] = m_a
                out_n_b[result_idx] = dest_pops[idx]
                
                # trace path and store dependencies
                curr = dest_nodes[idx]
                while curr != a and curr != -1:
                    prev = predecessors_a[curr]
                    pred_e = predecessor_edges_a[curr]
                    if prev == -1 or prev == curr:
                        break
                    
                    # pack edge and map to current OD
                    if dep_ptr < est_dep_size:
                        dep_edge_ids[dep_ptr] = pred_e#safe_pack(prev, curr)
                        dep_od_indices[dep_ptr] = result_idx
                        dep_ptr += 1
                    
                    curr = prev

                result_idx += 1
    
    if dep_ptr >= est_dep_size:
        print("WARNING: Dependency arrays reached capacity. Disruption results will be incomplete.")
        print("Increase est_dep_size (currently max_results * 50).")

    print("Finished. Trimming results...")
    return (
        out_a[:result_idx],
        out_b[:result_idx],
        out_flux[:result_idx],
        out_cost[:result_idx],
        out_s_ab[:result_idx],
        out_m_a[:result_idx],
        out_n_b[:result_idx],
        dep_edge_ids[:dep_ptr],
        dep_od_indices[:dep_ptr],
        traffic_ij,
    )


@numba.njit(parallel=PARALLEL)
def local_detour_costs(
    idxptr: np.ndarray,
    indices: np.ndarray,
    weights: np.ndarray,
    n_vertices: int,
    max_cost: float = np.inf,
) -> np.ndarray:
    n_edges = len(indices)
    criticality = np.zeros(n_edges, dtype=np.float64)

    assert len(indices) == len(weights)
    
    for u in numba.prange(n_vertices):
        print(f"Computing local detour costs for node {u + 1} / {n_vertices}")
        for edge_idx in range(idxptr[u], idxptr[u + 1]):
            v = indices[edge_idx]
            
            original_weight = weights[edge_idx]
            weights[edge_idx] = np.inf
            
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

# above here is for traffic assignment 
# below here is for disruption analysis

@numba.njit
def dijkstra_with_heap_inplace(
    idxptr: np.ndarray,
    indices: np.ndarray,
    weights: np.ndarray,
    source: int,
    distances: np.ndarray[np.float64],
    predecessors: np.ndarray[np.int64],
    _visited: np.ndarray[np.bool_],
    _heap_dist: np.ndarray[np.float64],
    _heap_node: np.ndarray[np.int64],
    max_cost: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Dijkstra's algorithm with binary heap. Better for sparse graphs.

    Pre-alloc version to avoid repeated memory allocation.

    O((V + E) log V).
    
    Args:
        idxptr: CSR row (index) pointers (length n_vertices + 1)
        indices: CSR column indices (length n_edges)
        weights: CSR edge weights (length n_edges)
        source: source vertex
        n_vertices: number of vertices in graph
        max_dist: stop exploring beyond this distance
    
    Values:
        distances: Array of length n_vertices with shortest
            distance from source to each vertex (inf if unreachable).
        predecessors: Array of length n_vertices with predecessor
            of each vertex on shortest path to source (-1 if unreachable,
            source for source).
    """
    distances.fill(np.inf)
    predecessors.fill(-1)
    _visited.fill(False)
    
    # binary heap arrays
    heap_size = 0
    
    # initialise source
    distances[source] = 0.0
    predecessors[source] = source
    
    # push source to heap
    heap_size = 1
    _heap_dist[1] = 0.0
    _heap_node[1] = source
    
    while heap_size > 0:
        # pop minimum
        dist_u = _heap_dist[1]
        u = _heap_node[1]
        
        # move last element to root and sift down
        last_dist = _heap_dist[heap_size]
        last_node = _heap_node[heap_size]
        heap_size -= 1
        
        if heap_size > 0:
            pos = 1
            while pos * 2 <= heap_size:
                child = pos * 2
                if child + 1 <= heap_size and _heap_dist[child + 1] < _heap_dist[child]:
                    child += 1
                if last_dist <= _heap_dist[child]:
                    break
                _heap_dist[pos] = _heap_dist[child]
                _heap_node[pos] = _heap_node[child]
                pos = child
            _heap_dist[pos] = last_dist
            _heap_node[pos] = last_node

        if _visited[u]:
            continue
        if dist_u > max_cost:
            break

        _visited[u] = True
        
        # relax edges from u
        for edge_idx in range(idxptr[u], idxptr[u + 1]):
            v = indices[edge_idx]
            if _visited[v]:
                continue
            
            new_dist = dist_u + weights[edge_idx]
            if new_dist < distances[v]:
                distances[v] = new_dist
                predecessors[v] = u
                
                # push to heap (sift up)
                heap_size += 1
                pos = heap_size
                while pos > 1 and new_dist < _heap_dist[pos // 2]:
                    _heap_dist[pos] = _heap_dist[pos // 2]
                    _heap_node[pos] = _heap_node[pos // 2]
                    pos //= 2
                _heap_dist[pos] = new_dist
                _heap_node[pos] = v



@numba.njit
def toggle_edge(idxptr, indices, csr_weights, u, v, new_val):
    """Finds and updates weight for u->v and v->u in CSR."""
    # Search u -> v
    old_val = -1.0
    for k in range(idxptr[u], idxptr[u+1]):
        if indices[k] == v:
            old_val = csr_weights[k]
            csr_weights[k] = new_val
            break
    # Search v -> u
    for k in range(idxptr[v], idxptr[v+1]):
        if indices[k] == u:
            csr_weights[k] = new_val
            break
    return old_val


@numba.njit(parallel=True)
def compute_edge_disruptions(
    edges: np.ndarray,
    edge_idxs: np.ndarray,
    od_indices: np.ndarray,
    idxptr: np.ndarray,
    indices: np.ndarray,
    orig_to_csr: np.ndarray,
    # sort_idx: np.ndarray,
    weights: np.ndarray,
    out_a: np.ndarray,
    out_b: np.ndarray,
    out_cost: np.ndarray,
    out_flux: np.ndarray,
    n_vertices: int,
    max_cost: float
):
    """Compute disruption impacts for each edge."""
    # # pre-allocate workspace arrays for each thread
    n_threads = numba.config.NUMBA_NUM_THREADS
    _dists = np.empty((n_threads, n_vertices), dtype=np.float64)
    _preds = np.empty((n_threads, n_vertices), dtype=np.int32)
    _visited = np.empty((n_threads, n_vertices), dtype=np.bool_)
    _heap_dist = np.empty((n_threads, n_vertices + 1), dtype=np.float64)
    _heap_node = np.empty((n_threads, n_vertices + 1), dtype=np.int64)
    # _weights = np.repeat(weights[np.newaxis, :], n_threads, axis=0)

    _weights = np.empty((n_threads, len(weights)), dtype=np.float64)
    for t in range(n_threads):
        _weights[t, :] = weights[:]

    # pre-allocate results arrays
    total_detour_flux = np.zeros(len(edges), dtype=np.float64)
    total_isolated_flux = np.zeros(len(edges), dtype=np.float64)
    total_weighted_detours = np.zeros(len(edges), dtype=np.float64)
    total_flux = np.zeros(len(edges), dtype=np.float64)

    for i in numba.prange(len(edges)):
        tid = numba.get_thread_id()
        u, v = edges[i]
        # packed_query = safe_pack(u, v)
        # start = np.searchsorted(edge_idxs, packed_query, side='left')
        # end = np.searchsorted(edge_idxs, packed_query, side='right')
        # od_idx = od_indices[start:end]
        csr_fwd = orig_to_csr[i, 0]
        csr_bwd = orig_to_csr[i, 1]

        start_fwd = np.searchsorted(edge_idxs, csr_fwd, side='left')
        end_fwd = np.searchsorted(edge_idxs, csr_fwd, side='right')

        start_bwd = np.searchsorted(edge_idxs, csr_bwd, side='left')
        end_bwd = np.searchsorted(edge_idxs, csr_bwd, side='right')

        od_idx = np.concatenate((od_indices[start_fwd:end_fwd], od_indices[start_bwd:end_bwd]))
        if len(od_idx) == 0:
            continue

        # disrupt edge
        edge_weight = toggle_edge(idxptr, indices, _weights[tid], u, v, np.inf)

        # get unique origins in affected OD pairs
        # ! could cause numba issues
        origins = np.unique(out_a[od_idx])

        # TODO: better approach:

        weighted_detours = 0.0
        detour_flux = 0.0
        isolated_flux = 0.0
        base_flux = 0.0

        for origin in origins:
            dijkstra_with_heap_inplace(
                idxptr, indices, _weights[tid], origin,
                _dists[tid], _preds[tid], _visited[tid], _heap_dist[tid], _heap_node[tid],
                max_cost
            )
            # find affected OD pairs from this origin
            for idx in od_idx:
                if out_a[idx] != origin:
                    continue
                flux_idx = out_flux[idx]
                if flux_idx <= 0:
                    continue
                new_cost = _dists[tid, out_b[idx]]

                base_flux += flux_idx
                if np.isfinite(new_cost):
                    detour_flux += flux_idx
                    detour_cost = (new_cost - out_cost[idx])
                    weighted_detours += flux_idx * detour_cost
                else:
                    isolated_flux += flux_idx

        # update total disruption for edge
        total_flux[i] = base_flux # for validation later
        total_detour_flux[i] = detour_flux
        total_isolated_flux[i] = isolated_flux
        total_weighted_detours[i] = weighted_detours

        _  = toggle_edge(idxptr, indices, _weights[tid], u, v, edge_weight)

        if tid == 0 and i % 100 == 0:
            print(f"Processed {i}/{len(edges)} edges.")
    
    return total_flux, total_detour_flux, total_isolated_flux, total_weighted_detours