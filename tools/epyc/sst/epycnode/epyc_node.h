#ifndef EPYC_NODE_H
#define EPYC_NODE_H

#include <sst/core/component.h>
#include <sst/core/params.h>

#include <cstdint>
#include <string>

namespace EpycTwin {

class EpycNode : public SST::Component
{
public:
    SST_ELI_REGISTER_COMPONENT(
        EpycNode,
        "epyctwin",
        "EpycNode",
        SST_ELI_ELEMENT_VERSION(1, 0, 0),
        "Reduced-order Dell PowerEdge R6525 / AMD EPYC 7763 compute node",
        COMPONENT_CATEGORY_PROCESSOR
    )

    SST_ELI_DOCUMENT_PARAMS(
        {"node_id",          "Unique CPU-node identifier",        "CPU000"},
        {"rack_id",          "Rack identifier",                   "R00"},
        {"rack_type",        "Rack type",                         "regular"},
        {"server_model",     "Server model",                      "Dell PowerEdge R6525"},
        {"cpu_model",        "CPU model",                         "AMD EPYC 7763"},
        {"sockets",          "Physical CPU sockets",              "2"},
        {"cores_per_socket", "Physical cores per socket",         "64"},
        {"total_cores",      "Physical cores in node",            "128"},
        {"numa_nodes",       "NPS4 NUMA domains in node",         "8"},
        {"cores_per_numa",   "Physical cores per NUMA domain",    "16"},
        {"l3_groups",        "Shared-L3 groups in node",          "16"},
        {"cores_per_l3",     "Physical cores per L3 group",       "8"},
        {"dram_controllers", "DRAM controllers in node",          "16"},
        {"memory_gib",       "Installed node memory in GiB",      "512"}
    )

    EpycNode(SST::ComponentId_t id, SST::Params& params);

private:
    std::string node_id_;
    std::string rack_id_;
    std::string rack_type_;
    std::string server_model_;
    std::string cpu_model_;

    uint32_t sockets_;
    uint32_t cores_per_socket_;
    uint32_t total_cores_;
    uint32_t numa_nodes_;
    uint32_t cores_per_numa_;
    uint32_t l3_groups_;
    uint32_t cores_per_l3_;
    uint32_t dram_controllers_;
    uint32_t memory_gib_;
};

} // namespace EpycTwin

#endif
