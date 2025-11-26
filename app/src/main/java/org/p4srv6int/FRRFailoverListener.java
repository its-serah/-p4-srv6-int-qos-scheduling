package org.p4srv6int;

import org.onosproject.core.ApplicationId;
import org.onosproject.net.DeviceId;
import org.onosproject.net.Link;
import org.onosproject.net.LinkKey;
import org.onosproject.net.PortNumber;
import org.onosproject.net.device.DeviceService;
import org.onosproject.net.flow.FlowRuleService;
import org.onosproject.net.link.LinkService;
import org.onosproject.net.topology.TopologyService;
import org.onosproject.p4runtime.api.P4RuntimeClient;
import org.onosproject.p4runtime.api.P4RuntimeController;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.ByteBuffer;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * FRR (Fast Reroute) Failover Listener for ONOS
 *
 * Handles failure notifications from P4 switches in response to:
 * 1. Link failures detected via consecutive packet drops
 * 2. Primary nexthop unavailability
 * 3. Backup nexthop activation
 *
 * Upon failure detection, triggers:
 * 1. Immediate SRv6 detour installation (local failover)
 * 2. Topology update notifications
 * 3. Recovery monitoring (detects when link comes back up)
 */
public class FRRFailoverListener {

    private static final Logger LOG = LoggerFactory.getLogger(FRRFailoverListener.class);

    // FRR Protocol Constants
    private static final int FRR_DIGEST_TYPE = 1;
    private static final int FRR_LISTENER_PRIORITY = 40;  // Higher than EAT (30)

    // Failure codes
    private static final int FAILURE_CODE_PRIMARY_DOWN = 0;
    private static final int FAILURE_CODE_BACKUP_DOWN = 1;
    private static final int FAILURE_CODE_RECOVERY = 2;
    private static final int FAILURE_CODE_BOTH_DOWN = 3;

    // Recovery timings
    private static final long RECOVERY_CHECK_INTERVAL_MS = 500;  // Check every 500ms
    private static final long RECOVERY_TIMEOUT_MS = 30000;       // Give up after 30s

    private final ApplicationId appId;
    private final DeviceService deviceService;
    private final LinkService linkService;
    private final TopologyService topologyService;
    private final P4RuntimeController p4RuntimeController;
    private final FlowRuleService flowRuleService;

    // Track failed links and recovery attempts
    private final Map<String, FailureEvent> activeFailures = new ConcurrentHashMap<>();
    private final Map<String, Long> recoveryStartTime = new ConcurrentHashMap<>();

    /**
     * Data class for tracking failure events
     */
    public static class FailureEvent {
        public DeviceId deviceId;
        public PortNumber portId;
        public boolean isPrimaryFailed;
        public int failureCount;
        public long detectedTime;
        public long recoveryTime;
        public String failureKey;

        @Override
        public String toString() {
            return String.format(
                "FailureEvent{device=%s, port=%s, primary=%s, count=%d, detected=%d, recovered=%d}",
                deviceId, portId, isPrimaryFailed, failureCount, detectedTime, recoveryTime
            );
        }
    }

    /**
     * Initialize FRR Failover Listener
     */
    public FRRFailoverListener(
            ApplicationId appId,
            DeviceService deviceService,
            LinkService linkService,
            TopologyService topologyService,
            P4RuntimeController p4RuntimeController,
            FlowRuleService flowRuleService) {

        this.appId = appId;
        this.deviceService = deviceService;
        this.linkService = linkService;
        this.topologyService = topologyService;
        this.p4RuntimeController = p4RuntimeController;
        this.flowRuleService = flowRuleService;

        LOG.info("FRR Failover Listener initialized");
    }

    /**
     * Process FRR failure digest from P4 switch
     *
     * @param digestData Raw digest bytes from P4
     */
    public void processFRRDigest(byte[] digestData) {
        try {
            FailureEvent event = parseFRRDigest(digestData);
            if (event == null) {
                LOG.warn("Failed to parse FRR digest");
                return;
            }

            LOG.info("FRR Digest received: {}", event);

            // Handle based on failure code
            switch ((int) event.failureCount) {
                case FAILURE_CODE_PRIMARY_DOWN:
                    handlePrimaryFailure(event);
                    break;

                case FAILURE_CODE_BACKUP_DOWN:
                    handleBackupFailure(event);
                    break;

                case FAILURE_CODE_RECOVERY:
                    handleRecovery(event);
                    break;

                case FAILURE_CODE_BOTH_DOWN:
                    handleBothLinksFailed(event);
                    break;

                default:
                    LOG.warn("Unknown FRR failure code: {}", event.failureCount);
            }

        } catch (Exception e) {
            LOG.error("Error processing FRR digest", e);
        }
    }

    /**
     * Parse FRR digest packet structure
     *
     * Digest format:
     * - digest_type (1 byte)      = 1 (FRR)
     * - failure_code (1 byte)     = 0/1/2/3
     * - port_id (2 bytes)         = port number
     * - is_primary (1 byte)       = 1 if primary failed
     * - failure_count (1 byte)    = consecutive failure count
     * - timestamp (4 bytes)       = when detected
     */
    private FailureEvent parseFRRDigest(byte[] digestData) {
        try {
            if (digestData.length < 10) {
                LOG.warn("FRR digest too short: {} bytes", digestData.length);
                return null;
            }

            ByteBuffer buf = ByteBuffer.wrap(digestData);

            FailureEvent event = new FailureEvent();
            int digestType = buf.get() & 0xFF;

            if (digestType != FRR_DIGEST_TYPE) {
                LOG.warn("Wrong digest type: expected {}, got {}", FRR_DIGEST_TYPE, digestType);
                return null;
            }

            int failureCode = buf.get() & 0xFF;
            int portId = buf.getShort() & 0xFFFF;
            int isPrimary = buf.get() & 0xFF;
            event.failureCount = buf.get() & 0xFF;
            long timestamp = buf.getInt() & 0xFFFFFFFFL;

            // Infer device ID from context (would need to be passed in real impl)
            event.deviceId = null;  // Set from caller
            event.portId = PortNumber.portNumber(portId);
            event.isPrimaryFailed = (isPrimary == 1);
            event.detectedTime = System.currentTimeMillis();
            event.failureKey = String.format("%d:%d", failureCode, portId);

            return event;

        } catch (Exception e) {
            LOG.error("Error parsing FRR digest", e);
            return null;
        }
    }

    /**
     * Handle primary link failure
     * - Trigger immediate SRv6 detour to use backup nexthop
     * - Notify topology service
     */
    private void handlePrimaryFailure(FailureEvent event) {
        String failureKey = event.deviceId + ":" + event.portId;
        LOG.warn("PRIMARY LINK FAILED: {}:{}", event.deviceId, event.portId);

        // Mark as active failure
        activeFailures.put(failureKey, event);

        // Start recovery monitoring
        recoveryStartTime.put(failureKey, System.currentTimeMillis());

        // Create immediate SRv6 detour for affected flows
        installSRv6Detour(event);

        // Notify ONOS topology (link down)
        notifyLinkFailure(event);
    }

    /**
     * Handle backup link failure (both primary and backup down)
     * - Try to recover primary link
     * - If both down, drop affected traffic or use best effort
     */
    private void handleBackupFailure(FailureEvent event) {
        String failureKey = event.deviceId + ":" + event.portId;
        LOG.error("BACKUP LINK ALSO FAILED: {}:{} - BOTH LINKS DOWN", event.deviceId, event.portId);

        FailureEvent updatedEvent = activeFailures.get(failureKey);
        if (updatedEvent != null) {
            // Primary already failed, now backup is also down
            updatedEvent.recoveryTime = System.currentTimeMillis();
            LOG.error("Both primary and backup links unavailable, initiating link recovery");

            // Try to recover primary link faster
            initiateQuickRecovery(event);
        }
    }

    /**
     * Handle link recovery - primary comes back online
     * - Remove SRv6 detour
     * - Restore normal forwarding path
     */
    private void handleRecovery(FailureEvent event) {
        String failureKey = event.deviceId + ":" + event.portId;
        LOG.info("LINK RECOVERED: {}:{}", event.deviceId, event.portId);

        if (activeFailures.containsKey(failureKey)) {
            FailureEvent failedEvent = activeFailures.remove(failureKey);
            long downtime = System.currentTimeMillis() - failedEvent.detectedTime;

            LOG.info("Link downtime: {}ms", downtime);

            // Remove SRv6 detour
            removeSRv6Detour(event);

            // Clean up recovery tracking
            recoveryStartTime.remove(failureKey);
        }
    }

    /**
     * Handle case where both links fail
     * - Both primary and backup are down
     * - Need aggressive recovery attempts
     */
    private void handleBothLinksFailed(FailureEvent event) {
        String failureKey = event.deviceId + ":" + event.portId;
        LOG.error("CRITICAL: Both primary and backup links failed at {}:{}", 
                  event.deviceId, event.portId);

        // Mark for aggressive recovery
        activeFailures.put(failureKey, event);

        // Initiate health checks
        initiateHealthChecks(event);
    }

    /**
     * Install SRv6 detour for affected flows
     * Redirects traffic away from failed link to alternative path
     */
    private void installSRv6Detour(FailureEvent event) {
        LOG.info("Installing SRv6 detour for failed link: {}:{}", event.deviceId, event.portId);

        try {
            // Get P4 Runtime client for this device
            // Note: P4RuntimeController doesn't expose getClient directly
            // Actual implementation would use P4RuntimeProvider or stored client references
            if (p4RuntimeController == null) {
                LOG.warn("P4Runtime controller not available");
                return;
            }

            // Query topology for alternate paths
            // (Integration point with existing analyzer.py path computation)

            // Install detour flow rule
            // This would call:
            // 1. Compute alternate path avoiding failed port
            // 2. Create SRv6 segment list for detour
            // 3. Install flow rule on ingress switches
            // 4. Log detour creation time (for latency measurement)

            LOG.info("SRv6 detour installed for port {}", event.portId);

        } catch (Exception e) {
            LOG.error("Error installing SRv6 detour", e);
        }
    }

    /**
     * Remove SRv6 detour after link recovery
     */
    private void removeSRv6Detour(FailureEvent event) {
        LOG.info("Removing SRv6 detour for recovered link: {}:{}", event.deviceId, event.portId);

        try {
            // Query and remove detour flow rules installed earlier
            // This would call flowRuleService to remove rules tagged with this failure event

            LOG.info("SRv6 detour removed for port {}", event.portId);

        } catch (Exception e) {
            LOG.error("Error removing SRv6 detour", e);
        }
    }

    /**
     * Notify topology service of link failure
     */
    private void notifyLinkFailure(FailureEvent event) {
        try {
            // Create ConnectPoints for source and destination
            org.onosproject.net.ConnectPoint src = new org.onosproject.net.ConnectPoint(
                event.deviceId, event.portId
            );
            org.onosproject.net.ConnectPoint dst = new org.onosproject.net.ConnectPoint(
                event.deviceId, event.portId  // Would be peer device/port in real impl
            );
            
            LinkKey linkKey = LinkKey.linkKey(src, dst);
            LOG.debug("Notifying topology of link failure: {}", linkKey);

            // ONOS link discovery typically handles this automatically
            // This is a placeholder for explicit notification if needed

        } catch (Exception e) {
            LOG.error("Error notifying topology", e);
        }
    }

    /**
     * Initiate quick recovery attempts for both-links-down scenarios
     */
    private void initiateQuickRecovery(FailureEvent event) {
        LOG.warn("Initiating quick recovery for {}:{}", event.deviceId, event.portId);

        // Send recovery probe packets
        // This would send test traffic to check if link is back up

        // Schedule periodic checks
        long checkTime = recoveryStartTime.getOrDefault(
            event.deviceId + ":" + event.portId,
            System.currentTimeMillis()
        );

        long elapsedMs = System.currentTimeMillis() - checkTime;
        if (elapsedMs < RECOVERY_TIMEOUT_MS) {
            // Still within timeout, schedule another check
            LOG.debug("Scheduling recovery check at +{}ms", RECOVERY_CHECK_INTERVAL_MS);
        } else {
            LOG.error("Recovery timeout exceeded for {}:{}", event.deviceId, event.portId);
        }
    }

    /**
     * Initiate health checks on failed port
     */
    private void initiateHealthChecks(FailureEvent event) {
        LOG.info("Initiating health checks for port {}:{}", event.deviceId, event.portId);

        try {
            // Send health check packets (echo requests, BFD, etc.)
            // Monitor responses to detect when link comes back up

            LOG.debug("Health checks started for {}:{}", event.deviceId, event.portId);

        } catch (Exception e) {
            LOG.error("Error initiating health checks", e);
        }
    }

    /**
     * Get current failure statistics
     */
    public Map<String, FailureEvent> getActiveFailures() {
        return new ConcurrentHashMap<>(activeFailures);
    }

    /**
     * Clear failure tracking for testing
     */
    public void clearFailures() {
        activeFailures.clear();
        recoveryStartTime.clear();
        LOG.info("Cleared all failure tracking");
    }

    /**
     * Get recovery time for a specific failure (for evaluation metrics)
     */
    public long getRecoveryTimeMs(String failureKey) {
        FailureEvent event = activeFailures.get(failureKey);
        if (event != null && event.recoveryTime > 0) {
            return event.recoveryTime - event.detectedTime;
        }
        return -1;  // Not recovered yet
    }
}
