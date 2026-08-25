#include "address_home_lookup.h"
#include "log.h"

AddressHomeLookup::AddressHomeLookup(UInt32 ahl_param,
      std::vector<core_id_t>& core_list,
      UInt32 cache_block_size):
   m_ahl_param(ahl_param),
   m_ahl_mask((UInt64(1) << ahl_param) - 1),
   m_core_list(core_list),
   m_total_modules(core_list.size()),
   m_cache_block_size(cache_block_size),
   m_numa_controller_routing(false),
   m_num_numa_nodes(1)
{

   // Each Block Address is as follows:
   // /////////////////////////////////////////////////////////// //
   //   block_num               |   block_offset                  //
   // /////////////////////////////////////////////////////////// //

   LOG_ASSERT_ERROR((1 << m_ahl_param) >= (SInt32) m_cache_block_size,
         "2^AHL param(%u) must be >= Cache Block Size(%u)",
         m_ahl_param, m_cache_block_size);
}

AddressHomeLookup::~AddressHomeLookup()
{
   // There is no memory to deallocate, so destructor has no function
}

void
AddressHomeLookup::enableNumaControllerRouting(
      UInt32 num_numa_nodes,
      const std::vector<UInt64>& node_capacity_bytes)
{
   LOG_ASSERT_ERROR(num_numa_nodes > 0,
         "NUMA controller routing requires at least one NUMA node");

   LOG_ASSERT_ERROR(node_capacity_bytes.size() == num_numa_nodes,
         "NUMA node capacity count (%u) does not match number of NUMA nodes (%u)",
         (UInt32)node_capacity_bytes.size(), num_numa_nodes);

   LOG_ASSERT_ERROR(m_total_modules >= num_numa_nodes,
         "Number of DRAM controllers (%u) must be >= number of NUMA nodes (%u)",
         m_total_modules, num_numa_nodes);

   LOG_ASSERT_ERROR((m_total_modules % num_numa_nodes) == 0,
         "Number of DRAM controllers (%u) must be divisible by number of NUMA nodes (%u)",
         m_total_modules, num_numa_nodes);

   m_numa_controller_routing = true;
   m_num_numa_nodes = num_numa_nodes;

   m_numa_node_start_addresses.resize(num_numa_nodes);
   m_numa_node_end_addresses.resize(num_numa_nodes);

   UInt64 current_address = 0;

   for (UInt32 n = 0; n < num_numa_nodes; ++n)
   {
      m_numa_node_start_addresses[n] = current_address;
      m_numa_node_end_addresses[n] =
         current_address + node_capacity_bytes[n];

      current_address = m_numa_node_end_addresses[n];
   }
}

core_id_t AddressHomeLookup::getHome(IntPtr address) const
{
   SInt32 module_num;

   if (!m_numa_controller_routing)
   {
      // Original Sniper behavior:
      // globally stripe addresses across all modules.
      module_num = (address >> m_ahl_param) % m_total_modules;
   }
   else
   {
      UInt64 physical_address = (UInt64)address;

      UInt32 numa_node = 0;
      bool found = false;

      for (UInt32 n = 0; n < m_num_numa_nodes; ++n)
      {
         if (physical_address >= m_numa_node_start_addresses[n] &&
             physical_address <  m_numa_node_end_addresses[n])
         {
            numa_node = n;
            found = true;
            break;
         }
      }

      // Match the current NUMA model's fallback semantics:
      // addresses outside configured ranges fall back to node 0.
      if (!found)
         numa_node = 0;

      UInt32 controllers_per_node =
         m_total_modules / m_num_numa_nodes;

      UInt64 local_address =
         physical_address - m_numa_node_start_addresses[numa_node];

      UInt32 local_module =
         (local_address >> m_ahl_param) % controllers_per_node;

      module_num =
         numa_node * controllers_per_node + local_module;
   }

   LOG_ASSERT_ERROR(
         0 <= module_num &&
         module_num < (SInt32)m_total_modules,
         "module_num(%i), total_modules(%u)",
         module_num,
         m_total_modules);

   LOG_PRINT("address(0x%x), module_num(%i)",
         address, module_num);

   return m_core_list[module_num];
}

IntPtr AddressHomeLookup::getLinearBlock(IntPtr address) const
{
   return (address >> m_ahl_param) / m_total_modules;
}

IntPtr AddressHomeLookup::getLinearAddress(IntPtr address) const
{
   return (getLinearBlock(address) << m_ahl_param) | (address & m_ahl_mask);
}
