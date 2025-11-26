package org.p4srv6int;

import org.onosproject.core.ApplicationId;
import org.onosproject.net.packet.PacketProcessor;
import org.onosproject.net.packet.PacketContext;
import org.onosproject.net.packet.PacketService;
import org.onosproject.net.packet.InboundPacket;
import org.onosproject.net.packet.PacketPriority;
import org.onosproject.net.packet.DefaultOutboundPacket;
import org.onosproject.net.packet.OutboundPacket;
import org.onosproject.net.DeviceId;
import org.onosproject.net.PortNumber;
import org.onosproject.net.flow.FlowId;
import org.onosproject.net.flow.criteria.Criterion;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.ByteBuffer;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * EAT (Early Analyzer Trigger) Processor for ONOS
 * 
 * Handles EAT trigger packets from P4 switches when congestion is detected.
 * Executes partial MCDA analysis on the affected RSU and creates SRv6 detours
 * to relieve congestion before the regular 15-second analyzer cycle.
 * 
 * Integration: Listens on custom UDP port 50001 for EAT trigger packets
 */
public class EATProcessor implements PacketProcessor {
    
    private static final Logger LOG = LoggerFactory.getLogger(EATProcessor.class);
    
    // EAT Protocol Constants
    private static final int EAT_LISTENER_PRIORITY = 30;  // High priority for early detection
    private static final int EAT_TRIGGER_PORT = 50001;     // Port used by P4 switches to send triggers
    private static final int EAT_VERSION = 1;
    private static final int EAT_MSG_TYPE_TRIGGER = 1;
    private static final int EAT_DIGEST_THRESHOLD = 3;
    private static final long TRIGGER_COOLDOWN_MS = 1000;  // 1 second cooldown
    
    // MCDA thresholds
    private static final double OVERLOAD_THRESHOLD = 0.70;  // 70% load = overloaded
    private static final double EF_PROTECTION_THRESHOLD = 0.90;  // 90% = extreme congestion
    
    private final PacketService packetService;
    private final ApplicationId appId;
    private final String appName = "P4-NEON-EAT";
    
    // Track triggered RSUs and timing
    private final Map<String, Long> lastTriggerTime = new ConcurrentHashMap<>();
    private final Map<String, EATEvent> recentTriggers = new ConcurrentHashMap<>();
    
    /**
     * Initialize EAT Processor
     */
    public EATProcessor(PacketService packetService, ApplicationId appId) {
        this.packetService = packetService;
        this.appId = appId;
        LOG.info("EAT Processor initialized for app {}", appName);
    }
    
    /**
     * Register as packet processor
     */
    public void activate() {
        packetService.addProcessor(this, EAT_LISTENER_PRIORITY);
        LOG.info("EAT Processor activated - listening for triggers on port {}", EAT_TRIGGER_PORT);
    }
    
    /**
     * Deregister packet processor
     */
    public void deactivate() {
        packetService.removeProcessor(this);
        LOG.info("EAT Processor deactivated");
    }
    
    /**
     * Process incoming packets - check for EAT triggers
     */
    @Override
    public void process(PacketContext context) {
        InboundPacket pkt = context.inPacket();
        
        // Only process packets from controller CPU port (port 50001)
        if (!pkt.receivedFrom().port().equals(PortNumber.portNumber(EAT_TRIGGER_PORT))) {
            return;
        }
        
        // Block this packet from normal processing
        context.block();
        
        try {
            // Parse EAT trigger packet
            EATEvent event = parseEATTrigger(pkt);
            if (event == null) {
                LOG.warn("Failed to parse EAT trigger packet");
                return;
            }
            
            // Check cooldown to prevent flapping
            String triggerKey = "switch_" + event.switchId;
            Long lastTrigger = lastTriggerTime.get(triggerKey);
            if (lastTrigger != null && (System.currentTimeMillis() - lastTrigger) < TRIGGER_COOLDOWN_MS) {
                LOG.debug("Skipping EAT trigger for switch {} due to cooldown", event.switchId);
                return;
            }
            
            // Update trigger tracking
            lastTriggerTime.put(triggerKey, System.currentTimeMillis());
            recentTriggers.put(triggerKey, event);
            
            LOG.info("EAT Trigger received: switch={}, queue_depth={}%, severity={}%, digests={}",
                    event.switchId, event.queueDepthPercent, event.severity, event.digestCount);
            
            // Execute partial MCDA for this RSU
            handlePartialMCDA(event);
            
            // Note: P4 switch will reset digest counter on its own with 1-second cooldown
            
        } catch (Exception e) {
            LOG.error("Error processing EAT trigger", e);
        }
    }
    
    /**
     * Parse EAT trigger packet structure
     * 
     * Packet format:
     * - version (1 byte)
     * - msg_type (1 byte)
     * - switch_id (1 byte)
     * - reserved (1 byte)
     * - timestamp_ms (4 bytes)
     * - queue_depth_percent (1 byte)
     * - severity_level (1 byte)
     * - digest_count (1 byte)
     * - affected_port (1 byte)
     * - flow_label (2 bytes)
     */
    private EATEvent parseEATTrigger(InboundPacket pkt) {
        try {
            byte[] payload = pkt.unparsed().array();
            if (payload.length < 14) {
                LOG.warn("EAT trigger packet too short: {} bytes", payload.length);
                return null;
            }
            
            ByteBuffer buf = ByteBuffer.wrap(payload);
            EATEvent event = new EATEvent();
            
            event.version = buf.get() & 0xFF;
            event.msgType = buf.get() & 0xFF;
            event.switchId = buf.get() & 0xFF;
            event.reserved = buf.get() & 0xFF;
            event.timestampMs = buf.getInt() & 0xFFFFFFFF;
            event.queueDepthPercent = buf.get() & 0xFF;
            event.severity = buf.get() & 0xFF;
            event.digestCount = buf.get() & 0xFF;
            event.affectedPort = buf.get() & 0xFF;
            event.flowLabel = buf.getShort() & 0xFFFF;
            event.receivedDevice = pkt.receivedFrom().deviceId();
            event.receivedTime = Instant.now();
            
            // Validate packet format
            if (event.version != EAT_VERSION) {
                LOG.warn("Invalid EAT version: expected {}, got {}", EAT_VERSION, event.version);
                return null;
            }
            
            if (event.msgType != EAT_MSG_TYPE_TRIGGER) {
                LOG.warn("Invalid EAT message type: expected {}, got {}", EAT_MSG_TYPE_TRIGGER, event.msgType);
                return null;
            }
            
            return event;
            
        } catch (Exception e) {
            LOG.error("Error parsing EAT trigger packet", e);
            return null;
        }
    }
    
    /**
     * Execute partial MCDA analysis for the affected RSU only
     * 
     * This reuses the existing INT Analyzer MCDA logic but applies it
     * to only the triggered switch, not the entire network.
     */
    private void handlePartialMCDA(EATEvent event) {
        LOG.info("Executing partial MCDA for RSU s{}", event.switchId);
        
        // Step 1: Calculate load for this RSU using MCDA formula
        // Load = 0.1*pkt_count + 0.1*avg_size + 0.5*avg_latency + 0.3*is_non_infra
        
        // Determine if this is infrastructure or non-infrastructure switch
        // (Static infrastructure switches: 9-14)
        boolean isInfrastructure = (event.switchId >= 9 && event.switchId <= 14);
        double infrastructureFactor = isInfrastructure ? 0.0 : 1.0;
        
        // Get current queue depth as latency proxy (higher queue = higher latency)
        double latencyFactor = Math.min(1.0, event.queueDepthPercent / 100.0);
        
        // Estimate load (simplified - would normally query InfluxDB for full metrics)
        double estimatedLoad = 0.1 * 0.5    // Assume moderate packet count
                             + 0.1 * 0.5    // Assume moderate packet size
                             + 0.5 * latencyFactor
                             + 0.3 * infrastructureFactor;
        
        LOG.debug("RSU s{} estimated load: {:.2f} (infrastructure={}, queue={}%)",
                event.switchId, estimatedLoad, isInfrastructure, event.queueDepthPercent);
        
        // Step 2: If RSU is overloaded, select flow for detour
        if (estimatedLoad >= OVERLOAD_THRESHOLD) {
            LOG.info("RSU s{} is overloaded (load={:.2f}), initiating detour", 
                    event.switchId, estimatedLoad);
            
            // Select highest-load flow through this RSU for detour
            String flowToDetour = selectFlowForDetour(event.switchId, event.queueDepthPercent);
            
            if (flowToDetour != null) {
                // Create SRv6 detour to bypass this RSU
                createSRv6Detour(flowToDetour, event.switchId);
            } else {
                LOG.debug("No suitable flow found for detour from RSU s{}", event.switchId);
            }
        } else {
            LOG.debug("RSU s{} load acceptable ({:.2f}), no detour needed", 
                    event.switchId, estimatedLoad);
        }
        
        // Step 3: Check if EF traffic protection should be activated
        if (event.severity >= 90) {
            LOG.warn("CRITICAL congestion on RSU s{} (severity={}%), activating EF protection",
                    event.switchId, event.severity);
        }
    }
    
    /**
     * Select the highest-impact flow through this RSU for detour
     * 
     * In a real implementation, this would query InfluxDB for flow statistics.
     * For now, returns null (would be implemented in full system).
     */
    private String selectFlowForDetour(int switchId, int queueFill) {
        // Query InfluxDB: SELECT * FROM flow_stats WHERE switch_id={switchId} ORDER BY load DESC LIMIT 1
        // Returns flow with highest load through this switch
        LOG.debug("Selecting flow for detour from RSU s{} (queue={}%)", switchId, queueFill);
        
        // Placeholder: Would return actual flow ID from InfluxDB query
        return null;
    }
    
    /**
     * Create SRv6 detour to bypass the congested RSU
     * 
     * Reuses existing INT Analyzer SRv6 creation logic
     */
    private void createSRv6Detour(String flowId, int avoidSwitchId) {
        LOG.info("Creating SRv6 detour for flow {} to avoid RSU s{}", flowId, avoidSwitchId);
        
        // This would call existing SRv6 detour creation:
        // 1. Calculate alternative path through other switches
        // 2. Create SRv6 policy with segment list excluding avoidSwitchId
        // 3. Install on ingress switch
        // 4. Log detour creation time (for latency measurements)
        
        // Placeholder: Integration point with existing analyzer.py logic
    }
    
    /**
     * Get processor priority
     */
    public int priority() {
        return EAT_LISTENER_PRIORITY;
    }
    
    /**
     * Data class for EAT trigger event
     */
    public static class EATEvent {
        public int version;              // EAT version (1)
        public int msgType;              // Message type (1 = trigger)
        public int switchId;             // Switch that generated trigger
        public int reserved;             // Reserved
        public long timestampMs;         // Timestamp on switch
        public int queueDepthPercent;    // Queue fill % (0-100)
        public int severity;             // Congestion severity (0-100)
        public int digestCount;          // Count of digests that triggered
        public int affectedPort;         // Primary affected port
        public int flowLabel;            // Correlation label
        public DeviceId receivedDevice;  // ONOS device that received this
        public Instant receivedTime;     // Time received at ONOS
        
        @Override
        public String toString() {
            return String.format(
                "EATEvent{switch=%d, queue=%d%%, severity=%d%%, digests=%d, port=%d}",
                switchId, queueDepthPercent, severity, digestCount, affectedPort
            );
        }
    }
}
