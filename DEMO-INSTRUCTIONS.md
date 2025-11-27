# P4-NEON Demo - Complete Instructions

## Quick Demo (5 minutes)

Run these commands **in order** from your repository directory:

```bash
cd ~/-p4-srv6-int-qos-scheduling

# 1. Start Docker containers (takes ~30 seconds)
docker-compose up -d
sleep 30

# 2. Copy pre-compiled app to ONOS
docker cp app/target/srv6_usid-1.0-SNAPSHOT.oar onos:/tmp/

# 3. Install the app in ONOS
docker exec onos /opt/onos/bin/onos-app localhost install /tmp/srv6_usid-1.0-SNAPSHOT.oar

# 4. Push network configuration
curl -X POST -H "Content-Type: application/json" --user onos:rocks -d @config/netcfg.json http://localhost:8181/onos/v1/network/configuration

# 5. Wait for app to activate (10 seconds)
sleep 10

# 6. Verify 14 devices appear (should show: 14)
curl -s --user onos:rocks http://localhost:8181/onos/v1/devices | python3 -c "import sys, json; print(len(json.load(sys.stdin)['devices']))"

# 7. Run evaluation demo (takes ~2 minutes)
python3 INT/evaluation/quick_eval.py

# 8. View results
cat INT/results/FINAL_EVALUATION_REPORT.md
```

## What You'll See

**After step 6:**
- Output should show: `14` (14 devices detected)
- If it shows 0, stop and check docker logs: `docker logs onos | tail -20`

**After step 7:**
- Evaluation runs 3 scenarios (High-Load, Link-Failure, Burst)
- Real data collected from InfluxDB
- Results generated in multiple formats

**After step 8:**
- Detailed evaluation report with all metrics
- Latency: ~18.17ms
- Recovery time: ~5,085ms (FRR working)
- EAT detection: 150ms (faster than standard 15s)

## If Something Fails

### Issue: Step 6 shows 0 devices
```bash
# Check ONOS logs
docker logs onos | tail -50 | grep -i "error\|exception"

# Check if app installed
docker exec onos onos-cli apps -a | grep srv6_usid

# Restart ONOS if needed
docker restart onos
sleep 15
# Re-run steps 2-6
```

### Issue: Step 7 hangs or fails
```bash
# Check if InfluxDB is running
docker ps | grep influxdb

# Check for InfluxDB data
curl -s 'http://localhost:8086/query?db=int' --data-urlencode 'q=SHOW MEASUREMENTS'

# Restart if needed
docker-compose down
docker-compose up -d
sleep 30
# Re-run steps 2-8
```

## Cleanup

To stop everything:
```bash
docker-compose down
```

---

**That's it! The .oar file is already compiled and ready. Just follow the commands above.**
