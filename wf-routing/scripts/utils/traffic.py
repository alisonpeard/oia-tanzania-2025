"""Entirely based-on Ren (2014) radiation model for estimating traffic flows in a network.

Might be too slow for large networks.

Optimisation. What is to be done? So far:
1. Vectorize where possible. Trade off between memory and array size.
2. Use boolean indexing not fancy indexing.
3. Minimise translation between Python and C++ in graph_tool.
4. Parallelise... but where is best?
5. One-to-many for loops.

TODO: still needs work to improve speed. Try numpy + njit or numba next.
"""
import numpy as np
from numba import jit
import pandas as pd
from tqdm import tqdm
from collections import Counter

import graph_tool.all as gt
from graph_tool.topology import shortest_distance

from typing import Union, Tuple


__all__ = ["radiation_model"]


def radiation_flux(
    m_a:float, 
    n_b:Union[float, np.array], 
    s_ab:Union[float, np.array], 
    zeta:float=1.0
) -> float:
    """Calculate radiation flux based on the radiation model.
    
    Args:
        m_a (float): Population at the source node.
        n_b (float): Population at the destination node.
        s_ab (float): Sum of populations of intervening nodes.
        zeta (float): Scaling factor for the radiation model.
    
    Returns:
        float: Calculated radiation flux.
    """
    return zeta * (m_a**2 * n_b) / ((m_a + s_ab) * (m_a + s_ab + n_b))


def distribute_traffic(traffic, ab_paths, phi_ab):
    # ! TODO: vectorize this function
    if phi_ab <= 0:
        return
    
    edge_count = sum(max(0, len(path) - 1) for path in ab_paths)
    if edge_count == 0:
        return
        
    traffic_per_edge = phi_ab / edge_count
    nedges = 0
    for path in ab_paths:
        for i in range(len(path) - 1):
            traffic[(path[i], path[i+1])] += traffic_per_edge
            nedges += 1


@jit('float64(int64, int64, int64, int64[:], float64[:], float64[:])', nopython=True)
def intervening_opportunities(
    a:int,
    b:int,
    c_ab:float,
    opportunities_sorted:np.array,
    distances_sorted:np.array,
    populations_sorted:np.array
) -> float:
    """Calculate the number of intervening opportunities between two vertices in a graph.
        Args:
            - a : int, source node
            - b : int, target node
            - i_b : int, index of the target node in opportunities, distances and pop arrays
            - opportunities : array, (n_b x 1) array of target nodes
            - distances : array, (n_b x 1) array of costs to target nodes
            - populations : array, (n_b x 1) array of populations at target nodes
    """
    #! O(n) scan every call, bottleneck, n=O(200_000) for Somalia
    cutoff_idx = np.searchsorted(distances_sorted, c_ab, side='right')
    total = 0.0
    for i in range(cutoff_idx):
        if opportunities_sorted[i] != a and opportunities_sorted[i] != b:
            total += populations_sorted[i]
    return total


def extract_path_from_pred_map(pred_map, source, target):
    """Extract shortest path from predecessor map - much faster than shortest_path()
    
    #!Still a massive bottleneck for high cutoff limits.
    """
    if pred_map[target] == target:  # unreachable
        return []
    
    path = []
    current = target
    while current != source:
        prev = int(pred_map[current])
        path.append((prev, int(current)))
        current = prev

    return list(reversed(path))


def iterative_mobility_model(
        a:int, b_nodes:np.array,
        m_a:int, n_bs:np.array, # populations
        min_cost:float, max_cost:float, costs_a:np.array, 
        a_list, b_list, flux_list, cost_list, s_ab_list,m_a_list, n_b_list, path_list,
        zeta=1.0, pred_map=None,
        flipped:bool=False, # whether to flip phi_ab calculation
    ) -> None:
    valid_idx = np.where((costs_a >= min_cost) & (costs_a < max_cost))[0]
    sort_idx = valid_idx[np.argsort(costs_a[valid_idx])]
    ab_nodes = b_nodes[sort_idx]
    ab_costs = costs_a[sort_idx]
    ab_pops = n_bs[sort_idx]

    for i_b in range(len(ab_nodes)):
        b = ab_nodes[i_b]
        n_b = ab_pops[i_b]
        c_ab = ab_costs[i_b]

        # calculate the flux
        s_ab = intervening_opportunities(a, b, c_ab, ab_nodes, ab_costs, n_bs)
        phi_ab = radiation_flux(m_a, n_b, s_ab, zeta=zeta, flipped=flipped)

        # calculate the path
        if phi_ab >= 1e-4:
            path_ab = extract_path_from_pred_map(pred_map, a, b) # big ol' bottleneck...
        else:
            path_ab = []
        
        # store results
        a_list.append(a)
        b_list.append(b)
        flux_list.append(phi_ab)
        cost_list.append(c_ab)
        m_a_list.append(m_a)
        n_b_list.append(n_b)
        s_ab_list.append(s_ab)
        path_list.append(path_ab)


def radiation_model(
    g:gt.Graph,
    cost:str, 
    min_cost:float=0.0,
    max_cost:float=None,
    origin_class:int=0,
    dest_class:int=1,
    class_str:str="school",
    population:str="population",
    pop_thresh:float=0.,
    zeta:float=1.0,
    calculate_traffic:bool=False,
    ) -> Tuple[gt.Graph, pd.DataFrame]:
    """
    Estimate total traffic flows using radiation model and cost function on edges, based on [1].

    Assumes symmetric trips from origins to destinations to save double-calculations.

    References:
    -----------
    ..[1] Ren Y, Ercsey-Ravasz M, Wang P, González MC, Toroczkai Z. Predicting commuter flows in spatial networks using a 
    radiation model based on temporal ranges. Nat Commun. 2014 Nov 6;5:5347. doi: 10.1038/ncomms6347. PMID: 25373437.
    """
    max_cost = max_cost or float("inf")

    # filter origin and destination nodes
    classes      = g.vp[class_str].a
    populations  = g.vp[population].a
    vertices     = np.arange(g.num_vertices())
    origin_nodes = vertices[(populations > pop_thresh) & (classes == origin_class)]
    dest_nodes   = vertices[(populations > pop_thresh) & (classes == dest_class)]

    # output some stats
    print(f"{class_str=}")
    print(f"{Counter(classes)=}")
    print(f"{origin_class=}, {dest_class=}")
    print(f"{sum(classes == origin_class)=}")
    print(f"{sum(classes == dest_class)=}")

    # for making the DataFrame
    a_list    = []
    b_list    = []
    flux_list = []
    cost_list = []
    s_ab_list = []
    m_a_list  = []
    n_b_list  = []
    path_list = []

    print(f"Found {len(origin_nodes)} origin nodes ({origin_class=}) and {len(dest_nodes)} destination nodes "
          f"({dest_class=}) with population threshold {pop_thresh}.")
    
    a_nodes = origin_nodes
    b_nodes = dest_nodes
    n_bs    = populations[b_nodes] # n_b x 1

    for a in (pbar := tqdm(a_nodes, desc="Radiation mobility model", unit=" node", leave=True)):
        # get costs and predecessor tree for all shortest paths from a
        m_a = populations[a]
        costs_map, pred_map = shortest_distance(
            g, source=a, weights=g.ep[cost], max_dist=max_cost, pred_map=True
            )
        costs_a = costs_map.a[b_nodes] # n_b x 1, will have inf for unreachable nodes
        iterative_mobility_model(
            a, b_nodes,
            m_a, n_bs, # populations
            min_cost, max_cost, costs_a,
            a_list, b_list, flux_list, cost_list, s_ab_list,m_a_list, n_b_list, path_list,
            zeta=zeta, pred_map=pred_map
            )

    # create DataFrame from the results
    df = pd.DataFrame({
        'a': a_list,
        'b': b_list,
        "m_a": m_a_list,
        "n_b": n_b_list,
        "s_ab": s_ab_list,
        cost: cost_list,
        "flux": flux_list,
        "path": path_list
    })

    return g, df