/*
 * Early Analyzer Trigger (EAT) - P4 Extensions
 * 
 * Detects sustained congestion and sends trigger packets to ONOS
 * for early intervention before the regular 15-second cycle.
 * 
 * Mechanism:
 * 1. Each switch maintains digest_count[switch_id]
 * 2. On congestion digest: increment counter
 * 3. When counter > THRESHOLD: create trigger packet
 * 4. Send trigger to ONOS controller
 * 5. ONOS executes partial MCDA, resets counter via P4Runtime
 */

#ifndef __EAT_TRIGGER__
#define __EAT_TRIGGER__

// EAT Configuration
#define EAT_DIGEST_THRESHOLD 3          // Trigger after 3 consecutive digests
#define EAT_TRIGGER_ETHER_TYPE 0xFFFF   // Custom EtherType for trigger packets
#define EAT_TRIGGER_DST_PORT 50001      // UDP port for ONOS listener

// ============================================================================
// Register Definitions
// ============================================================================

register<bit<32>>(256) digest_count;           // Per-switch digest counter
register<bit<32>>(256) last_trigger_time;      // Cooldown tracking (ms)
register<bit<1>>(256) eat_enabled;             // EAT enable flag per switch

// ============================================================================
// Header for EAT Trigger Packet
// ============================================================================

header eat_trigger_h {
    bit<8>  version;                // Version (1)
    bit<8>  msg_type;               // Message type (1 = trigger)
    bit<16> reserved;
    bit<32> switch_id;              // Source switch
    bit<32> digest_count_val;       // Current digest count
    bit<32> peak_queue_depth;       // Peak queue depth observed
    bit<32> timestamp_ms;           // Trigger timestamp
    bit<16> affected_port;          // Port with congestion
    bit<8>  traffic_class;          // Affected DSCP class
    bit<8>  severity;               // Congestion severity (0-100%)
}

// ============================================================================
// EAT Stub Control (Disabled for baseline compatibility)
// ============================================================================
// NOTE: EAT register operations are performed outside control block
// to ensure compatibility with existing Ingress.p4 and Egress.p4
// The actual EAT logic is invoked from ONOS app via register writes

#endif // __EAT_TRIGGER__
