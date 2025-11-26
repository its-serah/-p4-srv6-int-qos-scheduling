package org.p4srv6int;

import org.onosproject.net.device.DeviceService;
import org.onosproject.net.Device;
import org.onosproject.net.DeviceId;
import org.onosproject.p4runtime.api.P4RuntimeClient;
import org.onosproject.p4runtime.api.P4RuntimeController;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * QoS Policy Manager for P4-NEON Contribution 3
 * 
 * Enforces DSCP-based traffic prioritization in the data plane.
 * Manages queue selection, bandwidth reservation, and detour eligibility
 * based on traffic class and congestion level.
 * 
 * Traffic Classes:
 *   - EF (DSCP 46):  Expedited Forwarding - highest priority, critical for latency
 *   - AF (DSCP 34):  Assured Forwarding - medium priority
 *   - BE (DSCP 0):   Best Effort - lowest priority
 */
public class QoSPolicyManager {
    
    private static final Logger log = LoggerFactory.getLogger(QoSPolicyManager.class);
    
    // DSCP and Priority Constants
    private static final int DSCP_EF = 46;      // Expedited Forwarding
    private static final int DSCP_AF = 34;      // Assured Forwarding
    private static final int DSCP_BE = 0;       // Best Effort
    
    private static final int PRIORITY_EF = 0;   // Highest priority
    private static final int PRIORITY_AF = 1;   // Medium priority
    private static final int PRIORITY_BE = 2;   // Lowest priority
    
    // QoS Thresholds for Detour Decisions
    private static final int EF_DETOUR_THRESHOLD = 90;    // Never detour unless >90%
    private static final int AF_DETOUR_THRESHOLD = 75;    // Detour when >75%
    private static final int BE_DETOUR_THRESHOLD = 70;    // First to detour at >70%
    private static final int EF_PROTECTION_ACTIVATE = 70; // Activate protection at >70%
    
    // Bandwidth Reservation for EF
    private static final int EF_RESERVED_BANDWIDTH_PCT = 20;  // Reserve 20% for EF
    
    // Queue IDs for scheduling
    private static final int QUEUE_EF = 0;      // Highest priority queue
    private static final int QUEUE_AF = 1;      // Medium priority queue
    private static final int QUEUE_BE = 2;      // Lowest priority queue
    private static final int QUEUE_CONTROL = 3; // Control plane queue
    
    private final DeviceService deviceService;
    private final P4RuntimeController p4RuntimeController;
    
    // Track QoS statistics per port
    private final Map<String, QoSPortStats> portStats = new ConcurrentHashMap<>();
    
    // Track active QoS policies per switch
    private final Map<DeviceId, QoSPolicy> activePolicies = new ConcurrentHashMap<>();
    
    /**
     * Initialize QoS Policy Manager with required services
     */
    public QoSPolicyManager(DeviceService deviceService, P4RuntimeController p4RuntimeController) {
        this.deviceService = deviceService;
        this.p4RuntimeController = p4RuntimeController;
        log.info("QoS Policy Manager initialized");
    }
    
    /**
     * Initialize QoS registers on a switch with default policies
     */
    public void initializeQoSPolicies(DeviceId deviceId) {
        try {
            if (p4RuntimeController == null) {
                log.warn("P4Runtime controller not available for device {}", deviceId);
                return;
            }
            
            // Initialize default QoS policy for this switch
            QoSPolicy policy = new QoSPolicy();
            policy.deviceId = deviceId;
            policy.efReservedBandwidth = EF_RESERVED_BANDWIDTH_PCT;
            policy.efDetourThreshold = EF_DETOUR_THRESHOLD;
            policy.afDetourThreshold = AF_DETOUR_THRESHOLD;
            policy.beDetourThreshold = BE_DETOUR_THRESHOLD;
            
            activePolicies.put(deviceId, policy);
            
            log.info("Initialized QoS policy for device {}: EF reserve={}%, "
                    + "AF threshold={}%, BE threshold={}%",
                    deviceId, EF_RESERVED_BANDWIDTH_PCT, AF_DETOUR_THRESHOLD, BE_DETOUR_THRESHOLD);
            
        } catch (Exception e) {
            log.error("Error initializing QoS policies on {}: {}", deviceId, e.getMessage());
        }
    }
    
    /**
     * Classify traffic based on DSCP value
     * 
     * @param dscp The DSCP value from packet
     * @return Traffic class priority (0=EF, 1=AF, 2=BE)
     */
    public int classifyTraffic(int dscp) {
        if (dscp == DSCP_EF) {
            return PRIORITY_EF;
        } else if (dscp == DSCP_AF) {
            return PRIORITY_AF;
        } else {
            return PRIORITY_BE;
        }
    }
    
    /**
     * Determine if traffic is eligible for detour based on QoS class and congestion
     * 
     * @param priority QoS priority class (0=EF, 1=AF, 2=BE)
     * @param congestionLevel Current queue fill percentage (0-100)
     * @return true if packet can be detoured, false if must use primary path
     */
    public boolean isEligibleForDetour(int priority, int congestionLevel) {
        switch (priority) {
            case PRIORITY_EF:
                // EF: Never detour unless extreme congestion
                return congestionLevel >= EF_DETOUR_THRESHOLD;
                
            case PRIORITY_AF:
                // AF: Detour when moderately congested
                return congestionLevel >= AF_DETOUR_THRESHOLD;
                
            case PRIORITY_BE:
                // BE: Detour when congestion begins
                return congestionLevel >= BE_DETOUR_THRESHOLD;
                
            default:
                return false;
        }
    }
    
    /**
     * Select output queue based on QoS priority
     * 
     * @param priority QoS priority class (0=EF, 1=AF, 2=BE)
     * @return Queue ID (0=EF queue, 1=AF queue, 2=BE queue, 3=control)
     */
    public int selectOutputQueue(int priority) {
        switch (priority) {
            case PRIORITY_EF:
                return QUEUE_EF;
            case PRIORITY_AF:
                return QUEUE_AF;
            case PRIORITY_BE:
                return QUEUE_BE;
            default:
                return QUEUE_CONTROL;
        }
    }
    
    /**
     * Check if EF traffic protection should be activated
     * 
     * @param congestionLevel Current queue fill percentage
     * @return true if protection should be active
     */
    public boolean shouldActivateEFProtection(int congestionLevel) {
        return congestionLevel >= EF_PROTECTION_ACTIVATE;
    }
    
    /**
     * Update congestion level for a port and trigger QoS adjustments
     * 
     * @param deviceId Device identifier
     * @param portNumber Port number
     * @param queueFillPercentage Queue occupancy percentage
     */
    public void updateCongestionLevel(DeviceId deviceId, int portNumber, int queueFillPercentage) {
        String key = deviceId.toString() + ":" + portNumber;
        
        QoSPortStats stats = portStats.computeIfAbsent(key, k -> new QoSPortStats());
        stats.deviceId = deviceId;
        stats.portNumber = portNumber;
        stats.congestionLevel = Math.min(100, Math.max(0, queueFillPercentage));
        stats.lastUpdate = System.currentTimeMillis();
        
        // Check if EF protection needs to be activated/deactivated
        boolean protectionNeeded = shouldActivateEFProtection(stats.congestionLevel);
        if (protectionNeeded != stats.efProtectionActive) {
            stats.efProtectionActive = protectionNeeded;
            
            String action = protectionNeeded ? "ACTIVATING" : "DEACTIVATING";
            log.info("{} EF protection on {}:{} (congestion={}%)",
                    action, deviceId, portNumber, queueFillPercentage);
        }
    }
    
    /**
     * Get current QoS statistics for a port
     * 
     * @param deviceId Device identifier
     * @param portNumber Port number
     * @return QoS statistics if available, null otherwise
     */
    public QoSPortStats getPortStats(DeviceId deviceId, int portNumber) {
        String key = deviceId.toString() + ":" + portNumber;
        return portStats.get(key);
    }
    
    /**
     * Get current QoS policy for a switch
     * 
     * @param deviceId Device identifier
     * @return Active QoS policy if available, null otherwise
     */
    public QoSPolicy getPolicy(DeviceId deviceId) {
        return activePolicies.get(deviceId);
    }
    
    /**
     * Update QoS policy thresholds for a switch
     * 
     * @param deviceId Device identifier
     * @param efThreshold EF detour threshold (%)
     * @param afThreshold AF detour threshold (%)
     * @param beThreshold BE detour threshold (%)
     */
    public void updateDetourThresholds(DeviceId deviceId, int efThreshold, 
                                       int afThreshold, int beThreshold) {
        QoSPolicy policy = activePolicies.get(deviceId);
        if (policy != null) {
            policy.efDetourThreshold = efThreshold;
            policy.afDetourThreshold = afThreshold;
            policy.beDetourThreshold = beThreshold;
            
            log.info("Updated QoS thresholds for {}: EF={}%, AF={}%, BE={}%",
                    deviceId, efThreshold, afThreshold, beThreshold);
        }
    }
    
    /**
     * Inner class: QoS Statistics per Port
     */
    public static class QoSPortStats {
        public DeviceId deviceId;
        public int portNumber;
        public int congestionLevel;     // 0-100%
        public long efPackets;          // Count of EF packets
        public long afPackets;          // Count of AF packets
        public long bePackets;          // Count of BE packets
        public long efBytes;            // Total bytes of EF traffic
        public long afBytes;            // Total bytes of AF traffic
        public long beBytes;            // Total bytes of BE traffic
        public boolean efProtectionActive;
        public long lastUpdate;
        
        @Override
        public String toString() {
            return String.format("Port %d: congestion=%d%%, EF=%d/%d, AF=%d/%d, BE=%d/%d, "
                    + "protection=%s",
                    portNumber, congestionLevel,
                    efPackets, efBytes, afPackets, afBytes, bePackets, beBytes,
                    efProtectionActive ? "ON" : "OFF");
        }
    }
    
    /**
     * Inner class: QoS Policy for a Switch
     */
    public static class QoSPolicy {
        public DeviceId deviceId;
        public int efReservedBandwidth;    // % of bandwidth reserved for EF
        public int efDetourThreshold;      // % congestion threshold for EF detour
        public int afDetourThreshold;      // % congestion threshold for AF detour
        public int beDetourThreshold;      // % congestion threshold for BE detour
        public boolean efProtectionEnabled;
        public long createdAt;
        
        public QoSPolicy() {
            this.createdAt = System.currentTimeMillis();
            this.efProtectionEnabled = true;
        }
        
        @Override
        public String toString() {
            return String.format("QoSPolicy[device=%s, EF_reserved=%d%%, "
                    + "EF_threshold=%d%%, AF_threshold=%d%%, BE_threshold=%d%%]",
                    deviceId, efReservedBandwidth,
                    efDetourThreshold, afDetourThreshold, beDetourThreshold);
        }
    }
    
    /**
     * Helper: Get traffic class name for logging
     */
    public static String getTrafficClassName(int priority) {
        switch (priority) {
            case 0: return "EF (Expedited Forwarding)";
            case 1: return "AF (Assured Forwarding)";
            case 2: return "BE (Best Effort)";
            default: return "UNKNOWN";
        }
    }
}
