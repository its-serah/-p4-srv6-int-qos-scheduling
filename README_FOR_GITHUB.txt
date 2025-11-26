================================================================================
                    P4-SRv6-INT: Network Telemetry & QoS
================================================================================

STATUS: Base system + APQC removed (clean slate for feature branch)

================================================================================
                                  FILE STRUCTURE
================================================================================

📁 /p4-srv6-INT/
├── QUICKSTART.md              ← START HERE: 5-min guide to run the system
├── README.md                  ← Full documentation (detailed)
│
├── 📁 p4src/                  ← P4 code for switches
│   ├── p4info.txt            (compiled P4 info)
│   ├── bmv2.json             (compiled P4 data plane)
│   └── srv6-usid.p4          (P4 program source)
│
├── 📁 app/                    ← ONOS SDN controller app (Java)
│   ├── src/
│   ├── pom.xml
│   └── target/srv6-usid-1.0-SNAPSHOT.oar  (compiled app)
│
├── 📁 config/                 ← Configuration files
│   ├── netcfg.json            (network topology config)
│   ├── INT_Tables/            (INT switch rules)
│   └── ua_config.txt          (SRv6 anycast config)
│
├── 📁 mininet/                ← Network emulation
│   ├── topology.py            (8-switch mesh topology)
│   └── menu.py                (interactive test scenarios)
│
├── 📁 INT/                    ← Telemetry pipeline
│   ├── receiver/
│   │   └── collector_influxdb.py   (sniffs INT packets, stores in DB)
│   ├── send/
│   │   └── send.py                 (generates test traffic)
│   ├── analyzer/
│   │   ├── analyzer.py             (INT Analyzer - core component)
│   │   ├── High-ECMP-SRv6_rules.log
│   │   ├── High+Emergency-ECMP-SRv6_rules.log
│   │   └── Medium-ECMP-SRv6_rules.log
│   ├── visualizer/
│   │   └── visualizer.py      (real-time topology view)
│   └── grafana/
│       └── INT_statistics.json  (Grafana dashboard)
│
├── 📁 utils/                  ← Utilities
│   ├── docker/
│   │   └── Dockerfile         (custom stratum image)
│   └── wireshark/             (INT packet dissector)
│
├── 📁 commands/               ← Example CLI commands
│   ├── test_INT_Telemetry.txt
│   ├── srv6_insert.txt
│   └── Process Test Results.txt
│
├── docker-compose.yml         ← Docker setup (ONOS + Mininet)
├── Makefile                   ← Build & run commands
└── tmp/                       ← Generated logs (created at runtime)

================================================================================
                              QUICK START
================================================================================

1. Install deps (one-time):
   sudo apt-get install -y docker.io docker-compose python3-pip influxdb
   sudo pip3 install influxdb networkx matplotlib
   
2. Start system:
   cd p4-srv6-INT
   sudo make start       # ONOS + Mininet
   
3. Configure network (new terminal):
   sudo make netcfg      # Push topology to ONOS
   sudo make app-reload  # Load app
   
4. Collect telemetry (new terminal):
   sudo python3 INT/receive/collector_influxdb.py
   
5. Monitor & create detours (new terminal):
   sudo python3 INT/analyzer/analyzer.py --routing ECMP --num_iterations 20 --iterations_timer 15
   
6. Test it:
   sudo make mn-cli       # Mininet CLI
   h1 ping h8            # Basic test
   
7. Watch dashboards:
   ONOS UI:    http://localhost:8181/onos/ui
   Grafana:    http://localhost:3000 (admin/admin)

See QUICKSTART.md for detailed steps and troubleshooting.

================================================================================
                           WHAT THIS SYSTEM DOES
================================================================================

✅ Programmable Network (P4)
   - All switches run custom P4 code
   - DSCP-based traffic prioritization (BE, AF, EF)
   - IPv6 segment routing (SRv6) support
   
✅ In-Band Telemetry (INT)
   - Switch headers collect: latency, queue depth, path
   - Telemetry packets sent to INT Collector
   - Data stored in InfluxDB (time-series)
   
✅ Network Monitoring (Grafana)
   - Real-time queue occupancy per switch
   - Packet processing latency
   - End-to-end flow latency
   - Link utilization (packets/sec)
   
✅ Automated Congestion Mitigation
   - INT Analyzer reads telemetry from InfluxDB
   - Detects overloaded switches (>70% load)
   - Creates SRv6 detours via ONOS (avoids congestion)
   - Clears detours when congestion subsides (<60% load)
   - Protects EF traffic (VoIP, critical flows)
   
✅ SDN Control (ONOS)
   - KShortest path routing
   - ECMP (Equal-Cost Multi-Path) routing
   - Dynamic SRv6 rule injection/removal
   - Real-time path optimization

================================================================================
                              ARCHITECTURE
================================================================================

                    Mininet (8-switch mesh topology)
                    h1-h4 on r1-r4 (leaf)
                    h5-h8 on r5-r8 (leaf)
                            │
                    ┌───────┴─────────┐
                    │                 │
                INT Collector      ONOS Controller
                    │ (writes)       │ (reads/writes)
                    │                │
                    └────────┬────────┘
                             │
                         InfluxDB
                        (Telemetry)
                             │
                    INT Analyzer (Python)
                    - Reads queue stats
                    - Detects congestion
                    - Creates SRv6 detours
                             │
                         Grafana
                      (Dashboards)

================================================================================
                           TRAFFIC FLOW
================================================================================

1. Host sends packet → P4 switch
2. P4 code adds INT header (if enabled for flow)
3. Packet traverses switches, INT header accumulates metadata
4. P4 switch duplicates INT report packet → INT Collector interface
5. INT Collector receives report → parses → writes to InfluxDB
6. INT Analyzer reads from InfluxDB every 15s
7. If congestion detected → INT Analyzer calls ONOS to inject SRv6 detour
8. ONOS programs affected switches via P4Runtime
9. Next packets from that flow take alternate path (detour)
10. When congestion clears → INT Analyzer removes detour
11. Traffic returns to normal path

================================================================================
                              COMMANDS
================================================================================

Make commands (from project root):
  sudo make start          - Start ONOS + Mininet containers
  sudo make stop           - Stop containers
  sudo make restart        - Restart
  sudo make reset          - Clean everything
  sudo make netcfg         - Push network config to ONOS
  sudo make app-reload     - Reload ONOS app
  sudo make app-build      - Compile P4 + ONOS app
  sudo make onos-cli       - Access ONOS CLI
  sudo make onos-log       - Watch ONOS logs
  sudo make onos-ui        - Open ONOS Web UI (http://localhost:8181)
  sudo make mn-cli         - Access Mininet CLI
  sudo make mn-log         - Watch Mininet logs

Python scripts:
  sudo python3 INT/receive/collector_influxdb.py
    → Collect INT telemetry from switches
    
  sudo python3 INT/analyzer/analyzer.py --routing ECMP --num_iterations 20 --iterations_timer 15
    → Run INT Analyzer (detect congestion, create detours)
    
  sudo python3 INT/visualizer/visualizer.py
    → Visualize topology + live flows
    
  sudo python3 INT/send/send.py --dest 2001:1:8::8 --sport 1000 --dport 1001 --num 1000
    → Send test traffic

================================================================================
                           EXPECTED OUTPUTS
================================================================================

ONOS CLI (sudo make onos-cli):
  onos> summary              # Network overview
  onos> devices              # Connected switches (should be 8)
  onos> links                # Detected links
  onos> flows                # Active flow rules
  onos> paths <src> <dst>    # Calculate path

INT Analyzer (running):
  [2025-11-26 13:00:45] Analyzed 1500 packets in 15s
  [OVERLOADED] Switch r3 @ 75% load (latency spike)
  [DETOUR] Creating SRv6 rule for flow h1→h8
  [SUCCESS] SRv6 rule created, packets rerouting
  ...
  [CLEARED] Switch r3 @ 55% load, removing detour

Grafana Dashboards:
  - Queue occupancy: 0-1000 packets per queue
  - Latency: 1-5ms per switch
  - Flow latency: E2E latency per flow
  - Link utilization: packets/sec on each link

================================================================================
                              CREDITS
================================================================================

Base project: Fork of netgroup/p4-srv6
Topology Visualizer & Grafana: Tiago Mustra
INT implementation: P4INT_Mininet project
KShortest: ONOS-Framework project
ECMP: simple-ecmp project

================================================================================
                             NEXT STEPS
================================================================================

1. Read QUICKSTART.md for step-by-step guide
2. Run basic test: "sudo make start" → ONOS UI
3. Generate traffic: Use Mininet CLI menu
4. Monitor: Open Grafana dashboard
5. Experiment: Increase traffic to trigger congestion + detours
6. Analyze: Use INT Analyzer output + dashboards

For detailed info, see README.md

================================================================================
