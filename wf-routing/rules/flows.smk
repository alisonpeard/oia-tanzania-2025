rule calculate_od_trips:
    """
    TODO:
    - remove need for nodes
    - remove need for socioeconomic groups in edges
    """
    input:
        nodes=os.path.join(DATADIR, "routing", "access", "nodes_{socioeconomic}.parquet"),
        edges=os.path.join(DATADIR, "routing", "network", "edges_with_times.gpq"),
    output:
        trips=os.path.join(DATADIR, "routing", "flows", "{socioeconomic}", "trips.feather")
    params:
        local_crs=LOCAL_CRS,
        service_str=lambda wc: config["socioeconomic"][wc.socioeconomic]["service"],
        cost=lambda wc: config["socioeconomic"][wc.socioeconomic]["cost"],
        min_cost=lambda wc: config["socioeconomic"][wc.socioeconomic]["min_cost"],
        max_cost=lambda wc: config["socioeconomic"][wc.socioeconomic]["max_cost"],
        pop_threshold=lambda wc: config["socioeconomic"][wc.socioeconomic]["pop_threshold"],
        zeta=lambda wc: config["socioeconomic"][wc.socioeconomic]["zeta"]
    script:
        "../scripts/flows_access.py"
"""
