# P4-SRv6-INT: Quick Start Guide

**TL;DR**: Start the network with a few commands, then test it.

---

## Prerequisites (One-Time Setup)

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y docker.io docker-compose sshpass python3-pip python3-scapy mininet
sudo pip3 install influxdb networkx matplotlib

# Enable your user to run Docker without sudo
sudo usermod -aG docker $USER
newgrp docker

# Install InfluxDB
sudo apt-get install -y influxdb
sudo systemctl start influxdb
sudo systemctl enable influxdb

# Create InfluxDB database
influx << EOF
create database int
exit
EOF
```

---

## Quick Start (5 minutes)

### Step 1: Navigate to the project
```bash
cd /path/to/p4-srv6-INT
```

### Step 2: Start the infrastructure
```bash
# Clean up any previous runs
sudo make stop
sudo mn -c

# Start ONOS and Mininet
sudo make start
```

Wait ~30 seconds for containers to boot. You'll see logs from ONOS and Mininet.

### Step 3: Configure the network
```bash
# In a new terminal:
sudo make netcfg          # Push network config to ONOS
sudo make app-reload      # Reload ONOS app
```

### Step 4: Start INT collection
```bash
# In another terminal, start collecting telemetry:
sudo python3 INT/receive/collector_influxdb.py
```

### Step 5: Run a test scenario
```bash
# In the Mininet CLI (from the first terminal):
sudo make mn-cli

# Then run a pre-configured scenario from the menu
```

---

## What You Get

**Live topology visualization** (http://localhost:8181/onos/ui)
- Press `h` to show hosts
- Press `l` to show labels  
- Press `a` to show link utilization

 **Grafana dashboards** (http://localhost:3000)
- Login: admin / admin
- See real-time queue depths, latency, flow paths

 **Automated congestion detection**
- INT Analyzer monitors queue occupancy
- Automatically creates SRv6 detours to avoid congestion
- Clears detours when congestion subsides

---

## Common Commands

| Task | Command |
|------|---------|
| **Start system** | `sudo make start` |
| **Stop system** | `sudo make stop` |
| **Access ONOS CLI** | `sudo make onos-cli` |
| **View ONOS logs** | `sudo make onos-log` |
| **Access Mininet CLI** | `sudo make mn-cli` |
| **Run INT analyzer** | `sudo python3 INT/analyzer/analyzer.py --routing ECMP --num_iterations 10 --iterations_timer 300` |
| **View Mininet logs** | `sudo make mn-log` |

---

## Testing Congestion & Detours

### Scenario 1: Normal Traffic
```bash
# In Mininet CLI
h1 ping h8  # Should see ~1-2ms latency
```

### Scenario 2: Generate INT Data
```bash
# Run the pre-configured test from Mininet menu
# This generates traffic with INT enabled
```

### Scenario 3: Monitor Congestion
```bash
# Terminal 1: Start INT Analyzer
sudo python3 INT/analyzer/analyzer.py --routing ECMP --num_iterations 20 --iterations_timer 15

# Terminal 2: Generate traffic
sudo python3 INT/send/send.py --dest 2001:1:8::8 --sport 1000 --dport 1001 --num 10000

# Terminal 3: Watch for detours in ONOS CLI
sudo make onos-cli
onos> summary                    # Check current routing
onos> flows                      # See active rules
```

---

## Understanding the Output

### ONOS CLI Shows:
```
Active SRv6 rules        → Detours currently active
Switch loads             → Queue utilization
Link utilization         → Packets per second
```

### INT Analyzer Reports:
```
[OVERLOADED] Switch S1 @ 75% load
[DETOUR] Creating SRv6 rule for flow H1→H8
[CLEARED] Switch S1 now @ 55%, removing detour
```

### Grafana Dashboards:
- **Queue Occupancy**: Real-time queue depth per switch
- **Packet Processing Time**: Per-switch latency
- **Flow Latency**: End-to-end latency per data flow
- **Link Utilization**: Packets/sec on each link

---

## Troubleshooting

### Issue: Containers won't start
```bash
# Clean everything
sudo make reset
sudo docker system prune -a

# Start fresh
sudo make start
```

### Issue: No telemetry data in InfluxDB
```bash
# Check INT collector is running
ps aux | grep collector

# Check database exists
influx -execute 'use int; show measurements'

# Restart collector
sudo pkill -f collector_influxdb.py
sudo python3 INT/receive/collector_influxdb.py
```

### Issue: Grafana dashboards empty
```bash
# Verify InfluxDB connection in Grafana
# http://localhost:3000 → Configuration → Data Sources
# URL should be: http://localhost:8086
# Database: int
```

### Issue: SRv6 detours not appearing
```bash
# Check ONOS is connected to switches
sudo make onos-cli
onos> devices              # Should show 8 switches
onos> links                # Should show all links

# Restart the analysis
sudo python3 INT/analyzer/analyzer.py --routing ECMP --num_iterations 10 --iterations_timer 15
```

---

## Key Architecture

```
┌─────────────────────────────────────┐
│  Traffic Generation (Mininet hosts) │
│  h1-h4 (leaf switches r1-r4)        │
│  h5-h8 (leaf switches r5-r8)        │
└──────────────┬──────────────────────┘
               │
        ┌──────▼─────────┐
        │  P4 Switches   │
        │  (r1-r8)       │
        │  w/ INT header │
        └──────┬─────────┘
               │
      ┌────────┴────────┐
      │                 │
  ┌───▼────┐      ┌────▼────┐
  │ INT    │      │  ONOS   │
  │Collector      │Controller
  │        │      │          │
  └───┬────┘      └────┬─────┘
      │ (writes)       │ (reads, writes rules)
      │                │
      └────────┬───────┘
               │
          ┌────▼────────┐
          │  InfluxDB   │
          │  (Telemetry)│
          └────┬────────┘
               │ (reads)
          ┌────▼──────────┐
          │ INT Analyzer  │
          │ + Grafana     │
          └───────────────┘
```

---

## What Each Component Does

| Component | Purpose | Access |
|-----------|---------|--------|
| **ONOS** | SDN controller, programs switches | `sudo make onos-cli` or :8181/onos/ui |
| **Mininet** | Network emulation, creates topology | `sudo make mn-cli` or Terminal |
| **INT Collector** | Sniffs telemetry packets, stores in DB | Runs as background process |
| **InfluxDB** | Time-series database for metrics | Port 8086 (from INT Collector) |
| **INT Analyzer** | Detects congestion, creates detours | `sudo python3 INT/analyzer/analyzer.py` |
| **Grafana** | Visualize metrics | http://localhost:3000 |

---

## Real Example: Full Workflow

```bash
# Terminal 1: Start infrastructure
cd p4-srv6-INT
sudo make start

# Terminal 2: Configure network (after ~30 sec)
sudo make netcfg
sudo make app-reload

# Terminal 3: Collect INT data
sudo python3 INT/receive/collector_influxdb.py

# Terminal 4: Run analyzer (detects congestion, creates detours)
sudo python3 INT/analyzer/analyzer.py --routing ECMP --num_iterations 20 --iterations_timer 15

# Terminal 5: Mininet CLI
sudo make mn-cli
# From menu, select: "Generate INT test scenario"

# Terminal 6: Watch real-time in ONOS
sudo make onos-cli
onos> summary    # See network state
onos> flows      # See active rules
onos> summary    # See if detours were created
```

Then watch:
- **ONOS UI** (localhost:8181): See detours being created/removed
- **Grafana** (localhost:3000): See queue depths and latency changing
- **Terminal 4**: See INT Analyzer making decisions
- **Terminal 6**: See SRv6 rules being added/removed

---

## Next Steps

- **Modify traffic**: Edit `INT/send/send.py` to change packet rates
- **Adjust detection thresholds**: Edit `INT/analyzer/analyzer.py` (lines ~350-370)
- **Change topology**: Edit `mininet/topology.py`
- **Monitor performance**: Export results via `INT/process_results.py`

---

## Still Stuck?

1. Check logs: `sudo make mn-log` and `sudo make onos-log`
2. Verify connectivity: `sudo make onos-cli` → `devices` → should show 8 switches
3. Check InfluxDB: `influx -execute 'use int; select * from switch_stats limit 5'`
4. Restart everything: `sudo make reset && sudo make start`

---

**That's it!** The system automatically detects congestion and reroutes traffic. Watch it work in real-time on the dashboards.
