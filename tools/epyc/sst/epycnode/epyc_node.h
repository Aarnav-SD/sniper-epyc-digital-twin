#ifndef EPYC_NODE_H
#define EPYC_NODE_H

#include <sst/core/component.h>
#include <sst/core/params.h>
#include <sst/core/timeConverter.h>

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
        {"memory_gib",       "Installed node memory in GiB",      "512"},

        {"job_id",           "Synthetic workload identifier",     ""},
        {"job_start_us",     "Job start time in microseconds",    "0"},
        {"job_duration_us",  "Job duration in microseconds",      "0"},
        {"active_cores",     "Active physical cores while running","0"},
        {"utilization",      "Node utilization while running",    "0.0"},

        {"power_model",      "Reduced-order node power backend",   "pending-calibration"},
        {"reference_power_w","Raw CPU-side McPAT reference point", "88.48"}
    )

    EpycNode(SST::ComponentId_t id, SST::Params& params);

private:
    enum class RuntimeState {
        IDLE,
        RUNNING
    };

    bool clockTick(SST::Cycle_t cycle);

    // Static hardware identity
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

    // Runtime workload state
    RuntimeState state_;

    std::string job_id_;
    uint64_t job_start_us_;
    uint64_t job_duration_us_;
    uint32_t active_cores_;
    double utilization_;

    bool job_started_;
    bool job_completed_;

    // Power-model interface.
    //
    // "pending-calibration":
    //     no numerical wattage is produced.
    //
    // "mcpat-reference":
    //     exposes a fixed raw CPU-side McPAT reference point.
    //
    // "mcpat-surrogate-v1":
    //     exposes a workload-sensitive CPU-side McPAT surrogate estimate
    //     evaluated by the Python SST configuration layer from an explicit
    //     Sniper-derived activity profile.
    //
    // Both McPAT-backed values are REFERENCE_ONLY and are NOT calibrated
    // physical EPYC 7763 power predictions.
    std::string power_model_;
    double reference_power_w_;
};

} // namespace EpycTwin

#endif
