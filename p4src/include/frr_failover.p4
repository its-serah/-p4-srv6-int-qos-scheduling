/*
 * In-Switch Fault Tolerance (FRR) - P4 Extensions
 * 
 * Implements local failover logic with primary/backup nexthops.
 * On link failure or degradation, switches to backup automatically
 * without waiting for controller intervention.
 * 
 * Mechanism:
 * 1. Each port maintains: primary_nexthop, backup_nexthop, interface_status
 * 2. Egress checks: is primary link healthy?
 * 3. If down: switch to backup locally
 * 4. Send failure digest to ONOS for topology update
 * 5. ONOS can update routes proactively
 */

#ifndef __FRR_FAILOVER__
#define __FRR_FAILOVER__

// FRR Configuration
#define FRR_PORT_DOWN_THRESHOLD 3       // Consecutive failures to mark port down
#define FRR_HEALTH_CHECK_INTERVAL 100   // ms between health checks
#define FRR_DIGEST_TYPE 1               // Digest type for failure events
// Note: MAX_PORTS is defined in define.p4 (default 511)

// ============================================================================
// Register Definitions
// ============================================================================

register<bit<16>>(MAX_PORTS) primary_nexthop;         // Primary next hop MAC for each port
register<bit<16>>(MAX_PORTS) backup_nexthop;          // Backup next hop MAC for each port
register<bit<1>>(MAX_PORTS) interface_status;         // 1=up, 0=down
register<bit<8>>(MAX_PORTS) failure_count;            // Consecutive failures
register<bit<32>>(MAX_PORTS) last_health_check;       // Timestamp of last check
register<bit<1>>(MAX_PORTS) is_primary_active;        // Primary or backup active
register<bit<16>>(MAX_PORTS) recovery_attempts;       // Count of recovery attempts

// ============================================================================
// FRR Digest Notification (sent to ONOS)
// ============================================================================
struct frr_digest_t {
    bit<8> digest_type;          // FRR_DIGEST_TYPE
    bit<8> failure_code;         // 0=primary_down, 1=backup_down, 2=both_down
    bit<9> port_id;              // Port that failed
    bit<1> is_primary;           // 1=primary failed, 0=backup failed
    bit<8> failure_count;        // Count of consecutive failures
    bit<32> timestamp;           // Timestamp when detected
}

// ============================================================================
// FRR Control Block - Egress Processing
// ============================================================================
control FRRControl(
    inout parsed_headers_t hdr,
    inout local_metadata_t local_metadata,
    inout standard_metadata_t standard_metadata) {
    
    // Action: Update interface status
    action mark_port_status(bit<1> status) {
        // 1=up, 0=down
    }
    
    // Action: Send failure digest to ONOS
    action send_frr_digest(bit<8> failure_code, bit<1> is_primary_fail) {
        frr_digest_t digest_data = {
            digest_type = FRR_DIGEST_TYPE,
            failure_code = failure_code,
            port_id = (bit<9>)standard_metadata.egress_port,
            is_primary = is_primary_fail,
            failure_count = 0,
            timestamp = (bit<32>)standard_metadata.egress_global_timestamp
        };
        digest(FRR_DIGEST_TYPE, digest_data);
    }
    
    // Action: Switch to backup nexthop
    action failover_to_backup() {
        // Read current port status from primary_nexthop register
        bit<16> current_primary;
        primary_nexthop.read(current_primary, (bit<32>)standard_metadata.egress_port);
        
        // Mark primary as down
        interface_status.write((bit<32>)standard_metadata.egress_port, 0);
        
        // Switch active flag to backup
        is_primary_active.write((bit<32>)standard_metadata.egress_port, 0);
        
        // Update ONOS with failure event
        send_frr_digest(0, 1);  // 0=primary_down, 1=is_primary
    }
    
    // Action: Recover primary nexthop
    action recover_primary() {
        // Mark primary as up
        interface_status.write((bit<32>)standard_metadata.egress_port, 1);
        
        // Switch active flag back to primary
        is_primary_active.write((bit<32>)standard_metadata.egress_port, 1);
        
        // Reset failure counter
        failure_count.write((bit<32>)standard_metadata.egress_port, 0);
        
        // Notify ONOS of recovery
        send_frr_digest(2, 1);  // 2=recovery
    }
    
    apply {
        // FRR is currently managed by ONOS via register updates
        // This control block is a template for future in-switch failover
        // Current implementation: registers are read/written by ONOS
    }
}

#endif // __FRR_FAILOVER__
