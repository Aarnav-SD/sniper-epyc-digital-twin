#include "epyc_node.h"

#include <iostream>

namespace EpycTwin {

EpycNode::EpycNode(SST::ComponentId_t id, SST::Params& params)
    : SST::Component(id)
{
    node_id_          = params.find<std::string>("node_id", "CPU000");
    rack_id_          = params.find<std::string>("rack_id", "R00");
    rack_type_        = params.find<std::string>("rack_type", "regular");
    server_model_     = params.find<std::string>("server_model", "Dell PowerEdge R6525");
    cpu_model_        = params.find<std::string>("cpu_model", "AMD EPYC 7763");

    sockets_          = params.find<uint32_t>("sockets", 2);
    cores_per_socket_ = params.find<uint32_t>("cores_per_socket", 64);
    total_cores_      = params.find<uint32_t>("total_cores", 128);
    numa_nodes_       = params.find<uint32_t>("numa_nodes", 8);
    cores_per_numa_   = params.find<uint32_t>("cores_per_numa", 16);
    l3_groups_        = params.find<uint32_t>("l3_groups", 16);
    cores_per_l3_     = params.find<uint32_t>("cores_per_l3", 8);
    dram_controllers_ = params.find<uint32_t>("dram_controllers", 16);
    memory_gib_       = params.find<uint32_t>("memory_gib", 512);

    std::cout
        << "[" << node_id_ << "] "
        << server_model_ << "\n"
        << "[" << node_id_ << "] "
        << sockets_ << " x " << cpu_model_ << "\n"
        << "[" << node_id_ << "] "
        << "cores=" << total_cores_
        << " numa=" << numa_nodes_
        << " l3_groups=" << l3_groups_
        << " dram_controllers=" << dram_controllers_
        << " memory=" << memory_gib_ << "GiB\n"
        << "[" << node_id_ << "] "
        << "rack=" << rack_id_
        << " rack_type=" << rack_type_ << "\n"
        << "[" << node_id_ << "] initialized"
        << std::endl;
}

} // namespace EpycTwin
