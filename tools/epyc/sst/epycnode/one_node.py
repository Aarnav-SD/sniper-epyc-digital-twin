import sst

cpu000 = sst.Component("CPU000", "epyctwin.EpycNode")

cpu000.addParams({
    "node_id":          "CPU000",
    "rack_id":          "R00",
    "rack_type":        "regular",

    "server_model":     "Dell PowerEdge R6525",
    "cpu_model":        "AMD EPYC 7763",

    "sockets":          2,
    "cores_per_socket": 64,
    "total_cores":      128,

    "numa_nodes":       8,
    "cores_per_numa":   16,

    "l3_groups":        16,
    "cores_per_l3":     8,

    "dram_controllers": 16,
    "memory_gib":       512,
})
