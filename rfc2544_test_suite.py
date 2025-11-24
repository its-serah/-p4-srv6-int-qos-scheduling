#!/usr/bin/env python3
"""
RFC 2544 Test Suite for P4-SRv6-INT with QoS-Aware Scheduling
- Throughput, Latency, Frame Loss, and Jitter tests
- Congestion scenarios with mixed traffic classes (BE, AF, EF)
"""
import subprocess
import time
import sys
from datetime import datetime

GREEN = '\033[92m'
BLUE = '\033[94m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
END = '\033[0m'

class RFC2544:
    def __init__(self):
        self.start = datetime.now()

    def log(self, level, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        colors = {'INFO': CYAN, 'OK': GREEN, 'WARN': YELLOW, 'ERROR': RED, 'TEST': BLUE}
        print(f"{colors.get(level, CYAN)}[{ts} {level}]{END} {msg}")

    def sh(self, cmd, timeout=60):
        try:
            out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return out.stdout, out.returncode
        except subprocess.TimeoutExpired:
            self.log('ERROR', f'Timeout: {cmd}')
            return '', -1

    def ensure_env(self):
        # Check docker containers
        out, rc = self.sh('sudo docker-compose --no-ansi ps -q')
        if rc != 0 or len(out.strip().split('\n')) < 2:
            self.log('ERROR', 'Required containers not running (mininet, onos). Start with: sudo docker-compose up -d')
            return False
        self.log('OK', 'Docker containers are up')
        return True

    def start_receiver(self, seconds=30):
        self.log('INFO', f'Starting receiver for {seconds}s on h2_1')
        self.sh(f"sudo docker exec -d mininet python3 /mininet/tools/receive.py --duration {seconds}")

    def send_flow(self, dscp, count, interval, size=483, dst='h2_1', me='h1_1', flow_label=1, l4='udp'):
        cmd = f"""
        sudo docker exec mininet python3 /mininet/tools/send.py \
          --dst_ip {dst} --me {me} \
          --flow_label {flow_label} --dscp {dscp} \
          --port 443 --l4 {l4} --s {size} \
          --c {count} --i {interval}
        """
        return self.sh(cmd)

    def test_throughput(self):
        self.log('TEST', 'RFC2544: Throughput under mixed traffic + congestion')
        self.start_receiver(40)
        # Create congestion with BE and AF, then send EF
        self.send_flow(0,   2000, 0.002, flow_label=10)  # BE
        self.send_flow(34,  1200, 0.003, flow_label=20)  # AF
        self.send_flow(46,   800, 0.003, flow_label=30)  # EF
        time.sleep(40)
        self.log('OK', 'Throughput test complete')

    def test_latency(self):
        self.log('TEST', 'RFC2544: Latency under low load (baseline)')
        self.start_receiver(20)
        self.send_flow(0,  200, 0.01, flow_label=101)
        self.send_flow(34, 200, 0.01, flow_label=102)
        self.send_flow(46, 200, 0.01, flow_label=103)
        time.sleep(20)
        self.log('OK', 'Latency baseline test complete')

    def test_frame_loss(self):
        self.log('TEST', 'RFC2544: Frame Loss under congestion')
        self.start_receiver(35)
        self.send_flow(0,  3000, 0.0015, size=512, flow_label=201)
        self.send_flow(34, 1500, 0.0020, size=512, flow_label=202)
        self.send_flow(46,  800, 0.0025, size=512, flow_label=203)
        time.sleep(35)
        self.log('OK', 'Frame loss test complete')

    def test_jitter(self):
        self.log('TEST', 'RFC2544: Jitter under mixed traffic')
        self.start_receiver(30)
        # Mixed small bursts
        for i in range(5):
            self.send_flow(0,  200, 0.002, size=256, flow_label=301+i)
            self.send_flow(46, 150, 0.003, size=256, flow_label=311+i)
            time.sleep(2)
        time.sleep(30)
        self.log('OK', 'Jitter test complete')

    def run(self):
        if not self.ensure_env():
            return False
        # Verify QoS mapping in P4
        out, rc = self.sh("grep -c 'dscp_qos_mapping' /home/serah/p4-srv6-INT/p4src/include/Ingress.p4")
        if rc != 0 or int(out.strip() or '0') == 0:
            self.log('ERROR', 'QoS table not found in P4. Aborting.')
            return False
        # Run tests
        print()
        self.test_latency()
        print()
        self.test_throughput()
        print()
        self.test_frame_loss()
        print()
        self.test_jitter()
        print()
        self.log('OK', 'RFC 2544 test suite completed')
        return True

if __name__ == '__main__':
    suite = RFC2544()
    ok = suite.run()
    sys.exit(0 if ok else 1)
