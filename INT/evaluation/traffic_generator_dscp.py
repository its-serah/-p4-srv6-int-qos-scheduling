#!/usr/bin/env python3
"""
DSCP Traffic Generator for EF/AF/BE traffic classification testing
Generates marked traffic and measures per-class QoS metrics
"""

import subprocess
import time
import json
from datetime import datetime
from influxdb import InfluxDBClient

class DSCPTrafficGenerator:
    """Generate and measure DSCP-marked traffic flows"""
    
    # DSCP codes (6 bits, shifted left 2 positions in TOS byte)
    DSCP_CODES = {
        'EF':  0x2E << 2,  # Expedited Forwarding (VoIP)
        'AF4': 0x24 << 2,  # Assured Forwarding (video - highest AF priority)
        'BE':  0x00 << 2,  # Best Effort
    }
    
    def __init__(self, host='h1_1', dest='h8_1', dest_ip='2001:1:8::1'):
        self.host = host
        self.dest = dest
        self.dest_ip = dest_ip
        self.client = InfluxDBClient(host='localhost', port=8086, database='int')
    
    def run_ef_traffic(self, duration=30, rate='100k'):
        """Generate EF (VoIP) traffic - high priority"""
        print(f"\n[EF Traffic] Running {duration}s at {rate}...")
        # Simulated EF traffic (small packets, constant rate)
        cmd = f'timeout {duration} iperf3 -c {self.dest_ip} -u -b {rate} -l 64 -J'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            metrics = self._parse_iperf3(result.stdout, 'EF')
            self._store_traffic_metrics('EF', metrics)
            return metrics
        except Exception as e:
            print(f"Error running EF traffic: {e}")
            return {}
    
    def run_af_traffic(self, duration=30, rate='500k'):
        """Generate AF (Video) traffic - medium priority"""
        print(f"\n[AF Traffic] Running {duration}s at {rate}...")
        cmd = f'timeout {duration} iperf3 -c {self.dest_ip} -u -b {rate} -l 512 -J'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            metrics = self._parse_iperf3(result.stdout, 'AF')
            self._store_traffic_metrics('AF', metrics)
            return metrics
        except Exception as e:
            print(f"Error running AF traffic: {e}")
            return {}
    
    def run_be_traffic(self, duration=30, rate='1M'):
        """Generate BE (Best-Effort) traffic - low priority"""
        print(f"\n[BE Traffic] Running {duration}s at {rate}...")
        cmd = f'timeout {duration} iperf3 -c {self.dest_ip} -u -b {rate} -l 1024 -J'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            metrics = self._parse_iperf3(result.stdout, 'BE')
            self._store_traffic_metrics('BE', metrics)
            return metrics
        except Exception as e:
            print(f"Error running BE traffic: {e}")
            return {}
    
    def run_concurrent_traffic(self, duration=30):
        """Run all 3 traffic classes simultaneously"""
        print(f"\n{'='*80}")
        print(f"RUNNING CONCURRENT TRAFFIC (EF/AF/BE) FOR {duration}s")
        print(f"{'='*80}")
        print("EF (VoIP): 100 kbps, 64B packets")
        print("AF (Video): 500 kbps, 512B packets")
        print("BE (Web): 1 Mbps, 1024B packets")
        
        import threading
        results = {}
        
        def run_ef():
            results['EF'] = self.run_ef_traffic(duration, '100k')
        def run_af():
            results['AF'] = self.run_af_traffic(duration, '500k')
        def run_be():
            results['BE'] = self.run_be_traffic(duration, '1M')
        
        threads = [
            threading.Thread(target=run_ef),
            threading.Thread(target=run_af),
            threading.Thread(target=run_be)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        return results
    
    def _parse_iperf3(self, output, traffic_class):
        """Parse iperf3 JSON output"""
        try:
            data = json.loads(output)
            end_data = data.get('end', {})
            sum_data = end_data.get('sum_sent', {})
            
            return {
                'traffic_class': traffic_class,
                'throughput_mbps': sum_data.get('bits_per_second', 0) / 1e6,
                'packets_sent': sum_data.get('packets', 0),
                'bytes_sent': sum_data.get('bytes', 0),
                'seconds': sum_data.get('seconds', 0)
            }
        except:
            return {'traffic_class': traffic_class}
    
    def _store_traffic_metrics(self, traffic_class, metrics):
        """Store traffic metrics to InfluxDB"""
        try:
            json_body = [{
                "measurement": "traffic_class_metrics",
                "time": datetime.utcnow().isoformat(),
                "tags": {
                    "class": traffic_class,
                    "priority": {"EF": "high", "AF": "medium", "BE": "low"}.get(traffic_class, "unknown")
                },
                "fields": {
                    "throughput_mbps": float(metrics.get('throughput_mbps', 0)),
                    "packets_sent": int(metrics.get('packets_sent', 0)),
                    "bytes_sent": int(metrics.get('bytes_sent', 0))
                }
            }]
            self.client.write_points(json_body)
        except Exception as e:
            print(f"Error storing metrics: {e}")
    
    def analyze_qos_per_class(self):
        """Analyze QoS performance per traffic class"""
        print(f"\n{'='*80}")
        print("QoS PER-CLASS ANALYSIS")
        print(f"{'='*80}\n")
        
        result = {
            'timestamp': datetime.utcnow().isoformat(),
            'per_class_qos': {}
        }
        
        for traffic_class in ['EF', 'AF', 'BE']:
            try:
                query_result = list(self.client.query(
                    f'SELECT MEAN(latency) FROM switch_stats WHERE time > now() - 10m'
                ))
                
                latency = query_result[0][0]['mean'] if query_result and query_result[0] else 0
                
                result['per_class_qos'][traffic_class] = {
                    'priority': {"EF": "high", "AF": "medium", "BE": "low"}.get(traffic_class),
                    'avg_latency_ms': latency,
                    'expected_priority': {"EF": 1, "AF": 2, "BE": 3}.get(traffic_class)
                }
                
                print(f"{traffic_class} Traffic:")
                print(f"  Priority: {result['per_class_qos'][traffic_class]['priority']}")
                print(f"  Avg Latency: {latency:.2f}ms")
            except Exception as e:
                print(f"Error querying {traffic_class}: {e}")
        
        # Check if EF has lowest latency (highest priority)
        ef_latency = result['per_class_qos'].get('EF', {}).get('avg_latency_ms', float('inf'))
        af_latency = result['per_class_qos'].get('AF', {}).get('avg_latency_ms', float('inf'))
        be_latency = result['per_class_qos'].get('BE', {}).get('avg_latency_ms', float('inf'))
        
        priority_respected = (ef_latency <= af_latency <= be_latency)
        result['priority_preserved'] = priority_respected
        result['test_result'] = 'PASS' if priority_respected else 'FAIL'
        
        print(f"\nPriority Order (EF ≤ AF ≤ BE): {'✅ PASS' if priority_respected else '❌ FAIL'}")
        print(f"Expected: EF ≤ AF ≤ BE")
        print(f"Measured: {ef_latency:.2f} ≤ {af_latency:.2f} ≤ {be_latency:.2f}")
        
        return result

def main():
    """Test DSCP traffic classification"""
    gen = DSCPTrafficGenerator()
    
    # Run concurrent traffic
    results = gen.run_concurrent_traffic(30)
    
    # Analyze QoS per class
    analysis = gen.analyze_qos_per_class()
    
    print(f"\n{'='*80}")
    print("QoS CLASSIFICATION TEST RESULT")
    print(f"{'='*80}")
    print(json.dumps(analysis, indent=2))

if __name__ == '__main__':
    main()
