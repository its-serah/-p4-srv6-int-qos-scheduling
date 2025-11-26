/*
 * QoS-Aware Scheduling Module for P4-NEON
 * 
 * Implements DSCP-based priority scheduling to ensure EF (Expedited Forwarding)
 * traffic maintains low latency and priority during congestion.
 * 
 * DSCP Mapping:
 *   - DSCP 46 (EF):  Priority 0 (highest, never detour unless >90% congestion)
 *   - DSCP 34 (AF):  Priority 1 (medium, detour when needed)
 *   - DSCP 0  (BE):  Priority 2 (lowest, first to detour)
 */

#ifndef __QOS_SCHEDULING__
#define __QOS_SCHEDULING__

// ============================================================================
// QoS Class Definitions and Registers
// ============================================================================

// Standard DSCP values for QoS classes
const bit<8> DSCP_EF = 46;   // Expedited Forwarding (voice, critical data)
const bit<8> DSCP_AF = 34;   // Assured Forwarding (video, important flows)
const bit<8> DSCP_BE = 0;    // Best Effort (non-priority traffic)

// QoS Priority Levels (used for queue selection and scheduling)
const bit<3> QOS_PRIORITY_EF = 0;  // Highest priority
const bit<3> QOS_PRIORITY_AF = 1;  // Medium priority
const bit<3> QOS_PRIORITY_BE = 2;  // Lowest priority

// Per-port QoS statistics registers
register<bit<32>>(256) ef_packets_count;      // Count of EF packets per port
register<bit<32>>(256) af_packets_count;      // Count of AF packets per port
register<bit<32>>(256) be_packets_count;      // Count of BE packets per port

register<bit<32>>(256) ef_bytes_total;        // Total bytes of EF traffic per port
register<bit<32>>(256) af_bytes_total;        // Total bytes of AF traffic per port
register<bit<32>>(256) be_bytes_total;        // Total bytes of BE traffic per port

register<bit<8>>(256) port_congestion_level;  // 0-100 representing queue fill %
register<bit<8>>(256) qos_queue_select;       // Selected queue for egress (0-3)

// EF traffic protection flags
register<bit<8>>(256) ef_bandwidth_reserved;  // Reserved BW % for EF (default 20%)
register<bit<1>>(256) ef_protection_active;   // 1 = protecting EF, 0 = normal

// ============================================================================
// Header for QoS Metadata
// ============================================================================

header qos_meta_h {
    bit<8>  dscp;                // Original DSCP value from IPv4
    bit<3>  qos_priority;        // Computed QoS priority
    bit<8>  congestion_level;    // Queue fill percentage
    bit<1>  should_detour;       // 1 = packet eligible for detour
    bit<1>  ef_protected;        // 1 = EF traffic under protection
}

// ============================================================================
// QoS Stub Control (Disabled for baseline compatibility)
// ============================================================================
// NOTE: QoS register operations are managed via ONOS app
// Registers defined above are accessible for monitoring and configuration

/*
control QoSSchedulingControl(
    inout parsed_packet_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t standard_metadata)
{
    
    // ========================================================================
    // Action: Map DSCP to QoS Priority Level
    // ========================================================================
    action compute_qos_priority() {
        bit<8> dscp_value = hdr.ipv4.dscp;
        
        if (dscp_value == DSCP_EF) {
            meta.qos_priority = QOS_PRIORITY_EF;
        } else if (dscp_value == DSCP_AF) {
            meta.qos_priority = QOS_PRIORITY_AF;
        } else {
            meta.qos_priority = QOS_PRIORITY_BE;
        }
    }
    
    // ========================================================================
    // Action: Check if EF Traffic Protection is Active
    // ========================================================================
    action check_ef_protection(bit<32> port_idx) {
        bit<8> congestion;
        bit<8> ef_reserved;
        
        port_congestion_level.read(congestion, port_idx);
        ef_bandwidth_reserved.read(ef_reserved, port_idx);
        
        // EF protection active when congestion > threshold (default 70%)
        if (congestion >= 70) {
            ef_protection_active.write(port_idx, 1);
        } else {
            ef_protection_active.write(port_idx, 0);
        }
    }
    
    // ========================================================================
    // Action: Determine if Packet is Eligible for Detour
    // ========================================================================
    action evaluate_detour_eligibility() {
        bit<8> congestion = meta.congestion_level;
        bit<3> priority = meta.qos_priority;
        bit<1> eligible = 0;
        
        // EF traffic: Never detour unless extreme congestion (>90%)
        if (priority == QOS_PRIORITY_EF) {
            if (congestion >= 90) {
                eligible = 1;  // Detour only as last resort
            } else {
                eligible = 0;  // Never detour under normal conditions
            }
        }
        // AF traffic: Detour when congestion > 75%
        else if (priority == QOS_PRIORITY_AF) {
            if (congestion >= 75) {
                eligible = 1;
            } else {
                eligible = 0;
            }
        }
        // BE traffic: Detour when congestion > 70%
        else {
            if (congestion >= 70) {
                eligible = 1;
            } else {
                eligible = 0;
            }
        }
        
        meta.should_detour = eligible;
    }
    
    // ========================================================================
    // Action: Select Output Queue Based on QoS Priority
    // ========================================================================
    action select_output_queue() {
        bit<3> priority = meta.qos_priority;
        bit<8> queue_id = 0;
        
        // Priority-based queue selection (typically 4 queues per port)
        // Queue 0: EF (highest priority)
        // Queue 1: AF (medium priority)
        // Queue 2: BE (lowest priority)
        // Queue 3: Control plane traffic
        
        if (priority == QOS_PRIORITY_EF) {
            queue_id = 0;
        } else if (priority == QOS_PRIORITY_AF) {
            queue_id = 1;
        } else {
            queue_id = 2;
        }
        
        meta.qos_queue_id = queue_id;
    }
    
    // ========================================================================
    // Action: Update QoS Statistics per Port
    // ========================================================================
    action update_qos_stats(bit<32> port_idx, bit<16> packet_length) {
        if (meta.qos_priority == QOS_PRIORITY_EF) {
            bit<32> ef_count;
            ef_packets_count.read(ef_count, port_idx);
            ef_packets_count.write(port_idx, ef_count + 1);
            
            bit<32> ef_bytes;
            ef_bytes_total.read(ef_bytes, port_idx);
            ef_bytes_total.write(port_idx, ef_bytes + (bit<32>)packet_length);
        }
        else if (meta.qos_priority == QOS_PRIORITY_AF) {
            bit<32> af_count;
            af_packets_count.read(af_count, port_idx);
            af_packets_count.write(port_idx, af_count + 1);
            
            bit<32> af_bytes;
            af_bytes_total.read(af_bytes, port_idx);
            af_bytes_total.write(port_idx, af_bytes + (bit<32>)packet_length);
        }
        else {
            bit<32> be_count;
            be_packets_count.read(be_count, port_idx);
            be_packets_count.write(port_idx, be_count + 1);
            
            bit<32> be_bytes;
            be_bytes_total.read(be_bytes, port_idx);
            be_bytes_total.write(port_idx, be_bytes + (bit<32>)packet_length);
        }
    }
    
    // ========================================================================
    // Action: Enforce Bandwidth Reservation for EF Traffic
    // ========================================================================
    action enforce_ef_bandwidth_reservation() {
        bit<8> priority = meta.qos_priority;
        bit<8> congestion = meta.congestion_level;
        
        // If EF traffic and protection is active:
        // - Guarantee minimum bandwidth by preventing detour
        // - Mark packet to use reserved queue
        if (priority == QOS_PRIORITY_EF && congestion >= 70) {
            meta.ef_protected = 1;
            meta.should_detour = 0;  // Override: never detour EF
        }
    }
    
    // ========================================================================
    // Table: QoS Priority Classification (via port-based lookup)
    // ========================================================================
    table qos_priority_table {
        key = {
            standard_metadata.egress_port: exact;
            hdr.ipv4.dscp: exact;
        }
        actions = {
            compute_qos_priority;
            NoAction;
        }
        size = 256;
        default_action = NoAction();
    }
    
    // ========================================================================
    // Table: Congestion-Based Detour Decision
    // ========================================================================
    table congestion_detour_table {
        key = {
            meta.congestion_level: range;
            meta.qos_priority: exact;
        }
        actions = {
            evaluate_detour_eligibility;
            NoAction;
        }
        size = 32;
        default_action = NoAction();
    }
    
    // ========================================================================
    // Main Pipeline
    // ========================================================================
    apply {
        // Step 1: Compute QoS priority from DSCP
        compute_qos_priority();
        
        // Step 2: Select output queue based on priority
        select_output_queue();
        
        // Step 3: Update QoS statistics
        bit<32> port_idx = (bit<32>)standard_metadata.egress_port;
        update_qos_stats(port_idx, standard_metadata.packet_length);
        
        // Step 4: Check current congestion level
        port_congestion_level.read(meta.congestion_level, port_idx);
        
        // Step 5: Enforce EF bandwidth reservation
        enforce_ef_bandwidth_reservation();
        
        // Step 6: If not already protected, evaluate detour eligibility
        if (meta.ef_protected == 0) {
            evaluate_detour_eligibility();
        }
    }
}

*/

#endif  // __QOS_SCHEDULING__
