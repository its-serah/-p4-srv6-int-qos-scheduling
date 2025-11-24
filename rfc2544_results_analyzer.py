#!/usr/bin/env python3
"""
Parse InfluxDB data and print RFC 2544 style metrics grouped by DSCP class.
"""
import subprocess
import sys
from datetime import datetime

GREEN='\033[92m'
CYAN='\033[96m'
YELLOW='\033[93m'
RED='\033[91m'
END='\033[0m'

def sh(cmd):
    out = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return out.stdout, out.returncode

class Analyzer:
    def log(self, level, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        colors={'INFO':CYAN,'OK':GREEN,'WARN':YELLOW,'ERROR':RED}
        print(f"{colors.get(level,CYAN)}[{ts} {level}]{END} {msg}")

    def query(self, query):
        cmd = f'influx -database int -execute "{query}"'
        return sh(cmd)

    def run(self):
        self.log('INFO','Collecting RFC 2544 metrics (mean latency, packet counts) by DSCP...')
        q1 = 'SELECT COUNT(latency) as packets, MEAN(latency) as mean_latency, MEAN(size) as mean_size FROM flow_stats GROUP BY dscp'
        out, rc = self.query(q1)
        if rc != 0:
            self.log('ERROR','Influx query failed. Is InfluxDB running and populated?')
            print(out)
            return False
        print(out)
        self.log('INFO','If EF (DSCP 46) shows lower mean latency than BE (0) and AF (34), QoS works as intended.')
        return True

if __name__ == '__main__':
    ok = Analyzer().run()
    sys.exit(0 if ok else 1)
