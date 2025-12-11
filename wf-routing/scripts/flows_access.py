"""Calculate OD fluxes for service acccess using the radiation model.

    To profile:
        py-spy record -o profile.json -- python road_fluxes.py
        sudo py-spy record --format speedscope -o profile.speedscope.json -- python road_fluxes.py
        sudo py-spy record -o profile.svg -- python road_fluxes.py
        sudo py-spy top -- python road_fluxes.py
"""
# %%
import numpy as np
import pandas as pd
import geopandas as gpd
from time import time
from tqdm import tqdm
from collections import Counter

import graphtool.all as gt

from utils import traffic

def get_type(obj):
        if isinstance(obj, int):
            return "int"
        if np.issubdtype(type(obj), np.number):
            return "float"
        if isinstance(obj, str):
            return "string"
        
def process_ids(
        nodes:pd.DataFrame, edges:pd.DataFrame,
        idcol="id", source="from_id", target="to_id"
        ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Process node and edge IDs to ensure they are integers.
        This is necessary for graph_tool."""
    nodes = nodes.copy()
    edges = edges.copy()

    id_map = {node: idx for idx, node in enumerate(nodes[idcol].unique())}

    nodes["old_id"] = nodes[idcol]
    nodes["id"] = nodes[idcol].map(id_map)
    edges["from_id"] = edges[source].map(id_map)
    edges["to_id"] = edges[target].map(id_map)

    return nodes, edges, id_map


def make_edges_list(edges:pd.DataFrame) -> tuple[list, list]:
    edge_list = list(edges.itertuples(index=False, name=None))
    eprop_labels = list(edges.drop(columns=["from_id", "to_id"]).columns)
    eprop_types = [get_type(edges[k].values[0]) for k in eprop_labels]
    eprops = [(k, v) for k, v in zip(eprop_labels, eprop_types)]
    return edge_list, eprops


def make_graph(edges:pd.DataFrame, directed=False) -> gt.Graph:
    nodes, edges, id_map = process_ids(nodes, edges)
    edge_list, eprops = make_edges_list(edges)
    g = gt.Graph(edge_list, hashed=False, eprops=eprops, directed=directed)
    return g, id_map

# %% 
# setup for dev
from collecions import namedtuple

input = namedtuple("input", ["nodes", "edges"])
output = namedtuple("output", ["trips"])
params = namedtuple("params", [
    "local_crs", "service_str", "cost",
    "min_cost", "max_cost", "pop_threshold", "zeta"
    ])

# input.nodes = "../../results/assets/tza_roads_edges/kilimanjaro.parquet"
input.edges = "../../results/assets/tza_roads_edges/kilimanjaro.parquet"


# %%
def map_path(path:list[tuple], node_map:dict, edge_map:dict) -> list[str]:
    """Map path from node id pairs to edge ids."""
    new_path = []
    for source, target in path:
        nodes = (node_map[source], node_map[target])
        edge_id = edge_map[nodes]
        new_path.append(edge_id)
    return new_path


def main(input, output, params):
    local_crs   = params.local_crs
    service_str = params.service_str
    cost        = params.cost
    min_cost    = params.min_cost
    max_cost    = params.max_cost
    pop_thresh  = params.pop_threshold
    zeta        = params.zeta

    nodes = pd.read_parquet(input.nodes)
    nodes = nodes[["id", service_str, "population"]].copy()
    nodes[service_str] = nodes[service_str].astype(int)
    print(f"{service_str=}")
    print(Counter(nodes[service_str]))
    print(f"{nodes[nodes[service_str] == 1]['population'].sum()=}")
    print(f"{zeta * nodes[nodes[service_str] == 1]['population'].sum()=}")

    edges = gpd.read_parquet(input.edges)
    edges["id"].nunique() == len(edges), "some edges have non-unique ids"
    edge_map = edges.set_index(["from_id", "to_id"])["id"].to_dict()
    edge_map = edge_map | {(k[1], k[0]): v for k, v in edge_map.items()} # add reverse edges
    edges = edges[["from_id", "to_id", cost]].copy()

    print(f"Making graph_tool graph from {len(edges)} edges and {len(nodes)} nodes.")
    g, node_map = make_graph(edges, nodes)
    print(f"Graph has {g.num_vertices()} vertices and {g.num_edges()} edges.")

    start = time()
    g, df_trips = traffic.radiation_model(
        g, cost,
        min_cost=min_cost, max_cost=max_cost,
        class_str=service_str,
        pop_thresh=pop_thresh,
        zeta=zeta,
        )
    end = time()
    print(f"Radiation model took {end - start:.2f} seconds for network.")

    # process output trips file
    trips = df_trips[["a", "b", "flux" ,cost, "path"]].copy()
    trips = trips.rename(columns={"a": "from", "b": "to", "flux": "demand"})
    node_map_r = {v: k for k, v in node_map.items()}  # reverse id_map
    trips["from"] = trips["from"].map(node_map_r)
    trips["to"] = trips["to"].map(node_map_r)

    # process paths properly (might be faster out-of-loop)
    print("Renaming paths...")
    start = time()
    tqdm.pandas(desc="Mapping paths")
    trips["path"] = trips["path"].progress_apply(
        lambda path: map_path(path, node_map_r, edge_map)
    )
    end = time()
    print(f"Renaming paths took {end - start:.2f} seconds.")
    print(f"{trips['path'].head()=}")

    # save output files
    print(f"Saving trips to {output.trips}...")
    trips.to_feather(output.trips, index=False) # preserves lists

    if False:
        total_traffic = g.ep["traffic"].a.sum()
        total_flux = df_trips["flux"].sum()
        print(f"{total_traffic=}, {total_flux=}")


if __name__ == "__main__":
    input = snakemake.input
    output = snakemake.output
    params = snakemake.params
    main(input, output, params)