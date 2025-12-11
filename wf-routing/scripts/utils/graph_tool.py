import numpy as np
import pandas as pd
import graph_tool.all as gt


def get_type(obj):
        if isinstance(obj, int):
            return "int"
        if np.issubdtype(type(obj), np.number):
            return "float"
        if isinstance(obj, str):
            return "string"


def make_edges_list(edges:pd.DataFrame) -> tuple[list, list]:
    edge_list = list(edges.itertuples(index=False, name=None))
    eprop_labels = list(edges.drop(columns=["from_id", "to_id"]).columns)
    eprop_types = [get_type(edges[k].values[0]) for k in eprop_labels]
    eprops = [(k, v) for k, v in zip(eprop_labels, eprop_types)]
    return edge_list, eprops


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


def add_vertex_properties(g:gt.Graph, nodes:pd.DataFrame):
    for vprop in nodes.drop(columns="id").columns:
        vtype = get_type(nodes[vprop].values[0])
        prop = g.new_vertex_property(vtype)
        
        for _, vrow in nodes.iterrows():
            prop[vrow.id] = vrow[vprop]
        
        g.vertex_properties[vprop] = prop
    return g


def make_graph(edges:pd.DataFrame, nodes:pd.DataFrame, directed=False) -> gt.Graph:
    nodes, edges, id_map = process_ids(nodes, edges)
    edge_list, eprops = make_edges_list(edges)
    g = gt.Graph(edge_list, hashed=False, eprops=eprops, directed=directed)
    g = add_vertex_properties(g, nodes)
    return g, id_map


def get_path_cost(g, path, cost):
    total = 0.
    for i in range(len(path) - 1):
        edge = g.edge(path[i], path[i+1])
        total += g.ep[cost][edge]
    return total