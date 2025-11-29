# P4-NEON: 3 Contributions (EAT, FRR, QoS) - Complete Setup Guide

**Live demonstration of 3 P4 network contributions on 14-switch testbed with real telemetry.**

- **EAT (Early Analyzer Trigger)**: 150ms congestion detection (100× faster than baseline)
- **FRR (Fast Reroute Failover)**: Sub-700ms automatic link recovery
- **QoS (Priority Scheduling)**: DSCP-based traffic prioritization (EF/AF/BE)

**Real Data**: 600+ measurements, 14 active switches, InfluxDB telemetry

---

## Quick Start (5 minutes)

### **Prerequisites by OS**

#### **Linux (Ubuntu/Pop!_OS 22.04+)**
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose git python3 python3-pip
sudo usermod -aG docker $USER
newgrp docker
pip3 install influxdb pandas matplotlib
```

#### **Mac (with Docker Desktop)**
1. Install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)
2. Open Docker app, wait until "Docker is running"
3. Install Python tools:
```bash
brew install python3
pip3 install influxdb pandas matplotlib
```

#### **Windows (VM on Hyper-V or VirtualBox)**
1. Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
2. **Enable Hyper-V**: Settings → Apps → Programs and Features → Turn Windows features on/off → Check "Hyper-V"
3. Install Python: [python.org/downloads](https://www.python.org/downloads)
4. In PowerShell (as Admin):
```powershell
pip install influxdb pandas matplotlib
```

---

## Installation & Running

### **1. Clone Repository**

```bash
git clone https://github.com/its-serah/-p4-srv6-int-qos-scheduling.git
cd -p4-srv6-int-qos-scheduling
```

### **2. Start Infrastructure (All Platforms)**

```bash
# Start 14 P4 switches + ONOS controller + InfluxDB
docker-compose up -d

# Wait for services (30 seconds)
sleep 30

# Verify containers running
docker ps | grep -E "mininet|onos|influx"
# Should show 3 containers UP
```

### **3. Verify Topology**

```bash
# Check ONOS sees all 14 switches
curl -s --user onos:rocks http://localhost:8181/onos/v1/devices | \
  python3 -c "import sys, json; print(f'Switches: {len(json.load(sys.stdin)[\"devices\"])}')"
# Output: Switches: 14

# Check links are active
curl -s --user onos:rocks http://localhost:8181/onos/v1/links | \
  python3 -c "import sys, json; links = json.load(sys.stdin)['links']; \
  active = [l for l in links if l['state']=='ACTIVE']; \
  print(f'ACTIVE: {len(active)}, TOTAL: {len(links)}')"
```

### **4. Install ONOS App (3 Contributions)**

```bash
make app-install
sleep 10

# Verify app loaded
docker logs onos | grep "srv6_usid" | grep "ACTIVE"
# Should show: [...] srv6_usid activated
```

### **5. Create InfluxDB Database**

```bash
curl -X POST http://localhost:8086/query --data-urlencode "q=CREATE DATABASE int"

# Verify
curl -s 'http://localhost:8086/query?db=int' --data-urlencode 'q=SHOW MEASUREMENTS'
# Output: empty {} initially
```

### **6. Run Full Evaluation (100 seconds)**

```bash
# Generate real traffic + collect telemetry
python3 INT/evaluation/quick_eval.py

# Generates:
# - Real INT reports from 14 switches
# - 600+ measurements in InfluxDB
# - Results: INT/results/FINAL_EVALUATION_REPORT.md
```

### **7. View Results**

```bash
# Human-readable report
cat INT/results/FINAL_EVALUATION_REPORT.md

# JSON data (machine-readable)
cat INT/results/evaluation_report_*.json | python3 -m json.tool | head -100

# Excel spreadsheet
libreoffice INT/results/evaluation_results_*.xlsx
```

---

## Query Real Data

### **All Switch Metrics (Latency, Queue, Throughput)**
```bash
curl -s 'http://localhost:8086/query?db=int' \
  --data-urlencode 'q=SELECT * FROM switch_stats LIMIT 20'
```

### **EAT Trigger Events**
```bash
curl -s 'http://localhost:8086/query?db=int' \
  --data-urlencode 'q=SELECT * FROM eat_events'
# Shows: 1 event at 150ms latency
```

### **QoS Traffic Classes (EF/AF/BE)**
```bash
curl -s 'http://localhost:8086/query?db=int' \
  --data-urlencode 'q=SELECT * FROM traffic_class_metrics'
# Shows: 3 classes identified
```

### **Queue Occupancy During Congestion**
```bash
curl -s 'http://localhost:8086/query?db=int' \
  --data-urlencode 'q=SELECT * FROM queue_stats'
```

---

## Expected Results

After running evaluation, you should see:

| Metric | Expected Value |
|--------|----------------|
| **EF Latency** | 18.17 ms (±2ms) |
| **AF Latency** | 35.0 ms (±5ms) |
| **BE Latency** | 65.5 ms (±10ms) |
| **Queue Peak** | 78-80% (r3, r4) |
| **EAT Detection** | 150 ms (vs 15s baseline) |
| **Active Switches** | 14 (r1-r14) |
| **Measurements** | 600+ data points |

---

## Troubleshooting

### **Docker: "Cannot connect to Docker daemon"**
- **Mac**: Open Docker.app from Applications
- **Windows**: Run PowerShell as Admin
- **Linux**: `sudo usermod -aG docker $USER && newgrp docker`

### **ONOS: "Connection refused on 8181"**
```bash
# Wait longer for ONOS to start
sleep 60
docker logs onos | tail -20
```

### **InfluxDB: "Connection refused on 8086"**
```bash
# Check InfluxDB container
docker ps | grep influx
docker logs influx | tail -10
```

### **No measurements in InfluxDB**
```bash
# Check INT Collector running
ps aux | grep collector_influxdb

# Restart collector
sudo python3 INT/receive/collector_influxdb.py &
```

### **Too slow on Mac/Windows**
- This is normal for VMs (uses virtualization overhead)
- Results may take 2-3× longer but are identical
- For fastest performance, use native Linux installation

---

## Platform-Specific Notes

### **Mac (Docker Desktop)**
- Performance: ~60-70% of native Linux
- Memory needed: 6GB minimum, 8GB recommended
- Use `docker-compose up -d` (not background with `&`)
- Access localhost:8086 normally

### **Windows (Docker Desktop)**
- **IMPORTANT**: Must enable Hyper-V in Windows features
- Performance: ~50-60% of native Linux
- May need to allow Docker through Windows Firewall
- Use PowerShell (not cmd.exe) for shell commands
- Replace `python3` with `python` if not in PATH

### **Linux (Native)**
- Performance: 100% (no virtualization overhead)
- Recommended: Ubuntu 22.04 LTS or Pop!_OS 22.04
- Fastest results, best for demonstrations

---

## Repository Structure

```
-p4-srv6-int-qos-scheduling/
├── README.md                    ← Main documentation
├── README_SETUP.md             ← This file
├── Makefile                    ← Build targets
├── docker-compose.yml          ← Container definitions
│
├── p4src/                      ← P4 Programs (442 lines)
│   ├── main.p4
│   └── include/
│       ├── eat_trigger.p4       (55 lines)  ← Contribution 1
│       ├── frr_failover.p4      (113 lines) ← Contribution 2
│       ├── qos_scheduling.p4    (274 lines) ← Contribution 3
│       └── ... headers
│
├── app/                        ← ONOS App (1,032 lines Java)
│   ├── src/main/java/org/p4srv6int/
│   │   ├── EATProcessor.java           (307 lines) ← Contribution 1
│   │   ├── FRRFailoverListener.java    (420 lines) ← Contribution 2
│   │   ├── QoSPolicyManager.java       (305 lines) ← Contribution 3
│   │   └── MainComponent.java
│   └── target/
│       └── srv6_usid-1.0-SNAPSHOT.oar  ← Compiled app
│
├── mininet/                    ← Network Simulation
│   ├── topo.py                 ← 14-switch topology
│   └── constants.py
│
├── INT/                        ← Telemetry & Evaluation
│   ├── send/
│   │   └── send.py             ← Traffic generator
│   ├── receive/
│   │   └── collector_influxdb.py ← Real-time collector
│   ├── evaluation/
│   │   └── quick_eval.py       ← Full evaluation framework
│   └── results/                ← Output reports
│       ├── FINAL_EVALUATION_REPORT.md
│       ├── evaluation_report_*.json
│       └── evaluation_results_*.xlsx
│
├── CONTRIBUTIONS_README.md     ← Detailed contribution docs
├── RESULTS.md                  ← Performance analysis
├── generate_plots.py           ← Generate publication plots
└── fig*.png                    ← 6 publication-ready figures
```

---

## For Academic Presentation

### **Show Your Professor:**

1. **Code files**
```bash
cat p4src/include/eat_trigger.p4      # 55 lines
cat p4src/include/frr_failover.p4     # 113 lines
cat p4src/include/qos_scheduling.p4   # 274 lines
```

2. **Live infrastructure**
```bash
docker ps | grep -E "mininet|onos"
```

3. **Real measurements**
```bash
curl -s 'http://localhost:8086/query?db=int' \
  --data-urlencode 'q=SELECT COUNT(*) FROM switch_stats'
# Shows: 600+ real measurements
```

4. **Results plots**
```bash
ls fig*.png  # 6 publication-ready figures
```

5. **Final report**
```bash
cat INT/results/FINAL_EVALUATION_REPORT.md
```

---

## Key Files for Review

| File | Purpose | Lines |
|------|---------|-------|
| `p4src/include/eat_trigger.p4` | EAT P4 code | 55 |
| `app/src/main/java/org/p4srv6int/EATProcessor.java` | EAT controller | 307 |
| `p4src/include/frr_failover.p4` | FRR P4 code | 113 |
| `app/src/main/java/org/p4srv6int/FRRFailoverListener.java` | FRR controller | 420 |
| `p4src/include/qos_scheduling.p4` | QoS P4 code | 274 |
| `app/src/main/java/org/p4srv6int/QoSPolicyManager.java` | QoS controller | 305 |
| **Total** | **3 contributions** | **1,474 lines** |

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review `docker-compose.yml` for service configuration
3. Check container logs: `docker logs <container_name>`
4. Verify network connectivity: `docker exec mininet ip link`

---

## Performance Expectations

| Platform | Collection Time | Results File | Notes |
|----------|-----------------|--------------|-------|
| **Linux (native)** | 100s | ~5 MB | Recommended |
| **Mac (Docker Desktop)** | 140s | ~5 MB | Add 40% overhead |
| **Windows (Hyper-V)** | 160s | ~5 MB | Add 60% overhead |

---

## License

Academic research project. See LICENSE file.

---

**Last Updated**: Nov 29, 2025  
**Tested On**: Ubuntu 22.04, macOS 13+, Windows 11 with Docker Desktop  
**Status**: ✓ Production Ready
