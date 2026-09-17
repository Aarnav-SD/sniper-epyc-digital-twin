#include "epyc_node.h"

#include <iostream>
#include <stdexcept>

namespace EpycTwin {

EpycNode::EpycNode(SST::ComponentId_t id, SST::Params& params)
    : SST::Component(id),
      state_(RuntimeState::IDLE),
      job_started_(false),
      job_completed_(false)
{
    // --------------------------------------------------------
    // Static hardware configuration
    // --------------------------------------------------------

    node_id_          = params.find<std::string>("node_id", "CPU000");
    rack_id_          = params.find<std::string>("rack_id", "R00");
    rack_type_        = params.find<std::string>("rack_type", "regular");
    server_model_     = params.find<std::string>(
        "server_model", "Dell PowerEdge R6525"
    );
    cpu_model_        = params.find<std::string>(
        "cpu_model", "AMD EPYC 7763"
    );

    sockets_          = params.find<uint32_t>("sockets", 2);
    cores_per_socket_ = params.find<uint32_t>("cores_per_socket", 64);
    total_cores_      = params.find<uint32_t>("total_cores", 128);
    numa_nodes_       = params.find<uint32_t>("numa_nodes", 8);
    cores_per_numa_   = params.find<uint32_t>("cores_per_numa", 16);
    l3_groups_        = params.find<uint32_t>("l3_groups", 16);
    cores_per_l3_     = params.find<uint32_t>("cores_per_l3", 8);
    dram_controllers_ = params.find<uint32_t>("dram_controllers", 16);
    memory_gib_       = params.find<uint32_t>("memory_gib", 512);

    // --------------------------------------------------------
    // Runtime workload configuration
    // --------------------------------------------------------

    job_id_          = params.find<std::string>("job_id", "");
    job_start_us_    = params.find<uint64_t>("job_start_us", 0);
    job_duration_us_ = params.find<uint64_t>("job_duration_us", 0);
    active_cores_    = params.find<uint32_t>("active_cores", 0);
    utilization_     = params.find<double>("utilization", 0.0);

    // --------------------------------------------------------
    // Power-model configuration
    // --------------------------------------------------------

    power_model_ = params.find<std::string>(
        "power_model", "pending-calibration"
    );

    reference_power_w_ = params.find<double>(
        "reference_power_w", 88.48
    );

    // --------------------------------------------------------
    // Runtime safety checks
    // --------------------------------------------------------

    if (active_cores_ > total_cores_) {
        throw std::runtime_error(
            node_id_ + ": active_cores exceeds total_cores"
        );
    }

    if (utilization_ < 0.0 || utilization_ > 1.0) {
        throw std::runtime_error(
            node_id_ + ": utilization must be in [0, 1]"
        );
    }

    if (!job_id_.empty() && job_duration_us_ == 0) {
        throw std::runtime_error(
            node_id_ + ": non-empty job requires job_duration_us > 0"
        );
    }

    if (
        power_model_ != "pending-calibration" &&
        power_model_ != "mcpat-reference"
    ) {
        throw std::runtime_error(
            node_id_ + ": unsupported power_model: " + power_model_
        );
    }

    if (reference_power_w_ < 0.0) {
        throw std::runtime_error(
            node_id_ + ": reference_power_w must be non-negative"
        );
    }

    // --------------------------------------------------------
    // Structural initialization output
    // --------------------------------------------------------

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

        << "[" << node_id_ << "] "
        << "state=IDLE t=0us\n"

        << "[" << node_id_ << "] initialized"
        << std::endl;

    // --------------------------------------------------------
    // Only nodes with an assigned workload need a clock.
    //
    // Idle nodes remain structural SST components without
    // generating unnecessary periodic events.
    // --------------------------------------------------------

    if (!job_id_.empty()) {
        registerClock(
            "1us",
            new SST::Clock::Handler<EpycNode, &EpycNode::clockTick>(
                this
            )
        );
    }
}


bool EpycNode::clockTick(SST::Cycle_t cycle)
{
    const uint64_t now_us = static_cast<uint64_t>(cycle);

    // --------------------------------------------------------
    // IDLE -> RUNNING
    // --------------------------------------------------------

    if (!job_started_ && now_us >= job_start_us_) {
        state_ = RuntimeState::RUNNING;
        job_started_ = true;

        std::cout
            << "[" << node_id_ << "] "
            << "t=" << now_us << "us "
            << "state=RUNNING "
            << "job=" << job_id_ << " "
            << "active_cores=" << active_cores_ << " "
            << "utilization=" << utilization_
            << std::endl;

        if (power_model_ == "mcpat-reference") {
            std::cout
                << "[" << node_id_ << "] "
                << "t=" << now_us << "us "
                << "power_model=mcpat-reference "
                << "power_w=" << reference_power_w_ << " "
                << "status=REFERENCE_ONLY "
                << "calibrated=false"
                << std::endl;
        }
        else {
            std::cout
                << "[" << node_id_ << "] "
                << "t=" << now_us << "us "
                << "power_model=pending-calibration "
                << "power_w=UNAVAILABLE "
                << "status=PENDING "
                << "calibrated=false"
                << std::endl;
        }
    }

    // --------------------------------------------------------
    // RUNNING -> IDLE
    // --------------------------------------------------------

    const uint64_t job_end_us =
        job_start_us_ + job_duration_us_;

    if (
        job_started_ &&
        !job_completed_ &&
        now_us >= job_end_us
    ) {
        state_ = RuntimeState::IDLE;
        job_completed_ = true;

        std::cout
            << "[" << node_id_ << "] "
            << "t=" << now_us << "us "
            << "state=IDLE "
            << "job=" << job_id_ << " completed"
            << std::endl;

        // Returning true unregisters this clock handler.
        // Once the synthetic job completes, this node has no
        // more events to generate.
        return true;
    }

    return false;
}

} // namespace EpycTwin
