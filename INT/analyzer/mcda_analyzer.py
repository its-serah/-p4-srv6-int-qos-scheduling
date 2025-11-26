#!/usr/bin/env python3
"""
MCDA Analyzer - TOPSIS (Technique for Order of Preference by Similarity to Ideal Solution)
Implements multi-criteria decision analysis for adaptive network optimization
"""

import numpy as np
import json
from datetime import datetime
from influxdb import InfluxDBClient

class MCDAAnalyzer:
    """Multi-Criteria Decision Analysis for network optimization"""
    
    def __init__(self, db_host='localhost', db_port=8086, db_name='int'):
        """Initialize MCDA analyzer"""
        self.client = InfluxDBClient(host=db_host, port=db_port, database=db_name)
        self.criteria = {
            'latency': {'weight': 0.40, 'type': 'min'},      # 40% importance, lower is better
            'throughput': {'weight': 0.25, 'type': 'max'},   # 25% importance, higher is better
            'packet_loss': {'weight': 0.20, 'type': 'min'},  # 20% importance, lower is better
            'recovery_time': {'weight': 0.15, 'type': 'min'} # 15% importance, lower is better
        }
    
    def collect_network_metrics(self, time_window='5m'):
        """Collect metrics from InfluxDB for analysis"""
        metrics = {}
        
        try:
            # Average latency
            result = list(self.client.query(
                f'SELECT MEAN(latency) FROM switch_stats WHERE time > now() - {time_window}'
            ))
            metrics['latency'] = float(result[0][0]['mean']) if result and result[0] else 100.0
            
            # Average throughput
            result = list(self.client.query(
                f'SELECT MEAN(throughput) FROM switch_stats WHERE time > now() - {time_window}'
            ))
            metrics['throughput'] = float(result[0][0]['mean']) if result and result[0] else 1000.0
            
            # Packet loss (calculate from queue overflow events)
            result = list(self.client.query(
                f'SELECT COUNT(*) FROM switch_stats WHERE queue_occupancy > 90 AND time > now() - {time_window}'
            ))
            total_events = list(self.client.query(
                f'SELECT COUNT(*) FROM switch_stats WHERE time > now() - {time_window}'
            ))
            loss_count = float(result[0][0]['count']) if result and result[0] else 0
            total_count = float(total_events[0][0]['count']) if total_events and total_events[0] else 1
            metrics['packet_loss'] = (loss_count / total_count * 100) if total_count > 0 else 0.0
            
            # Recovery time from FRR events
            result = list(self.client.query(
                f'SELECT MEAN(recovery_time_ms) FROM link_failure_events WHERE time > now() - {time_window}'
            ))
            metrics['recovery_time'] = float(result[0][0]['mean']) if result and result[0] else 5000.0
            
        except Exception as e:
            print(f"Error collecting metrics: {e}")
            # Use defaults if collection fails
            metrics = {
                'latency': 18.17,
                'throughput': 12500,
                'packet_loss': 0.1,
                'recovery_time': 5085
            }
        
        return metrics
    
    def normalize_decision_matrix(self, alternatives):
        """Normalize criteria values to 0-1 range"""
        normalized = {}
        
        for criterion, values in alternatives.items():
            if criterion not in self.criteria:
                continue
            
            crit_type = self.criteria[criterion]['type']
            max_val = max(values.values())
            min_val = min(values.values())
            
            normalized[criterion] = {}
            
            if crit_type == 'max':
                # Higher is better: normalize to max
                for alt, val in values.items():
                    if max_val == 0:
                        normalized[criterion][alt] = 0
                    else:
                        normalized[criterion][alt] = val / max_val
            else:
                # Lower is better: invert normalization
                for alt, val in values.items():
                    if max_val == min_val:
                        normalized[criterion][alt] = 0
                    else:
                        normalized[criterion][alt] = (max_val - val) / (max_val - min_val)
        
        return normalized
    
    def calculate_weighted_matrix(self, normalized_matrix):
        """Apply weights to normalized matrix"""
        weighted = {}
        
        for criterion, values in normalized_matrix.items():
            weight = self.criteria[criterion]['weight']
            weighted[criterion] = {}
            for alt, score in values.items():
                weighted[criterion][alt] = score * weight
        
        return weighted
    
    def calculate_ideal_worst_solutions(self, weighted_matrix):
        """Calculate ideal (+) and worst (-) solutions"""
        ideal_positive = {}
        ideal_negative = {}
        
        for criterion, values in weighted_matrix.items():
            crit_type = self.criteria[criterion]['type']
            
            if crit_type == 'max':
                ideal_positive[criterion] = max(values.values())
                ideal_negative[criterion] = min(values.values())
            else:
                ideal_positive[criterion] = min(values.values())  # For min criteria, best is lowest
                ideal_negative[criterion] = max(values.values())
        
        return ideal_positive, ideal_negative
    
    def calculate_separations(self, weighted_matrix, ideal_pos, ideal_neg):
        """Calculate distance from ideal positive and negative solutions"""
        separations = {'positive': {}, 'negative': {}}
        
        # Get all alternatives
        alt_names = list(list(weighted_matrix.values())[0].keys())
        
        for alt in alt_names:
            dist_pos = 0
            dist_neg = 0
            
            for criterion, values in weighted_matrix.items():
                alt_value = values[alt]
                dist_pos += (alt_value - ideal_pos[criterion]) ** 2
                dist_neg += (alt_value - ideal_neg[criterion]) ** 2
            
            separations['positive'][alt] = np.sqrt(dist_pos)
            separations['negative'][alt] = np.sqrt(dist_neg)
        
        return separations
    
    def calculate_topsis_scores(self, separations):
        """Calculate TOPSIS scores (0-1, higher is better)"""
        scores = {}
        
        for alt in separations['positive'].keys():
            sep_pos = separations['positive'][alt]
            sep_neg = separations['negative'][alt]
            
            if sep_pos + sep_neg == 0:
                scores[alt] = 0.5
            else:
                scores[alt] = sep_neg / (sep_pos + sep_neg)
        
        return scores
    
    def rank_alternatives(self, scores):
        """Rank alternatives by TOPSIS score"""
        sorted_alts = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ranking = []
        
        for rank, (alt, score) in enumerate(sorted_alts, 1):
            ranking.append({
                'rank': rank,
                'alternative': alt,
                'score': score,
                'recommendation': 'PRIMARY' if rank == 1 else 'SECONDARY' if rank == 2 else 'TERTIARY'
            })
        
        return ranking
    
    def analyze(self, alternatives, debug=False):
        """Run MCDA analysis using TOPSIS method"""
        
        if debug:
            print("\n" + "="*80)
            print("MCDA ANALYSIS (TOPSIS METHOD)")
            print("="*80)
        
        # Step 1: Normalize decision matrix
        normalized = self.normalize_decision_matrix(alternatives)
        if debug:
            print("\n1. NORMALIZED MATRIX:")
            print(json.dumps({k: {ak: round(av, 4) for ak, av in v.items()} 
                            for k, v in normalized.items()}, indent=2))
        
        # Step 2: Calculate weighted matrix
        weighted = self.calculate_weighted_matrix(normalized)
        if debug:
            print("\n2. WEIGHTED MATRIX (after applying criteria weights):")
            weights = {k: v['weight'] for k, v in self.criteria.items()}
            print(f"Weights: {weights}")
            print(json.dumps({k: {ak: round(av, 4) for ak, av in v.items()} 
                            for k, v in weighted.items()}, indent=2))
        
        # Step 3: Calculate ideal solutions
        ideal_pos, ideal_neg = self.calculate_ideal_worst_solutions(weighted)
        if debug:
            print("\n3. IDEAL SOLUTIONS:")
            print(f"Ideal Positive (Best): {ideal_pos}")
            print(f"Ideal Negative (Worst): {ideal_neg}")
        
        # Step 4: Calculate separations
        separations = self.calculate_separations(weighted, ideal_pos, ideal_neg)
        if debug:
            print("\n4. SEPARATIONS FROM IDEAL:")
            print("Distance to Ideal Positive (lower is better):")
            for alt, dist in separations['positive'].items():
                print(f"  {alt}: {dist:.6f}")
            print("Distance to Ideal Negative (higher is better):")
            for alt, dist in separations['negative'].items():
                print(f"  {alt}: {dist:.6f}")
        
        # Step 5: Calculate TOPSIS scores
        scores = self.calculate_topsis_scores(separations)
        if debug:
            print("\n5. TOPSIS SCORES (0-1, higher is better):")
            for alt, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
                print(f"  {alt}: {score:.6f}")
        
        # Step 6: Rank alternatives
        ranking = self.rank_alternatives(scores)
        if debug:
            print("\n6. FINAL RANKING:")
            for item in ranking:
                print(f"  {item['rank']}. {item['alternative']}: {item['score']:.4f} ({item['recommendation']})")
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'method': 'TOPSIS',
            'criteria': self.criteria,
            'scores': scores,
            'ranking': ranking,
            'decision': ranking[0]['alternative'] if ranking else None,
            'confidence': ranking[0]['score'] if ranking else 0
        }
    
    def make_decision(self, network_metrics):
        """Make network optimization decision based on metrics"""
        
        # Define alternative network configurations
        alternatives = {
            'latency': {
                'current_config': network_metrics.get('latency', 18.17),
                'aggressive_qos': network_metrics.get('latency', 18.17) * 0.85,  # 15% improvement
                'conservative_qos': network_metrics.get('latency', 18.17) * 0.95
            },
            'throughput': {
                'current_config': network_metrics.get('throughput', 12500),
                'aggressive_qos': network_metrics.get('throughput', 12500) * 0.95,
                'conservative_qos': network_metrics.get('throughput', 12500) * 0.98
            },
            'packet_loss': {
                'current_config': network_metrics.get('packet_loss', 0.1),
                'aggressive_qos': network_metrics.get('packet_loss', 0.1) * 0.8,
                'conservative_qos': network_metrics.get('packet_loss', 0.1) * 0.95
            },
            'recovery_time': {
                'current_config': network_metrics.get('recovery_time', 5085),
                'aggressive_qos': network_metrics.get('recovery_time', 5085) * 0.9,
                'conservative_qos': network_metrics.get('recovery_time', 5085) * 0.98
            }
        }
        
        # Run MCDA analysis
        result = self.analyze(alternatives, debug=True)
        
        # Store result in InfluxDB
        try:
            json_body = [{
                "measurement": "mcda_decisions",
                "time": datetime.utcnow().isoformat(),
                "fields": {
                    "decision_score": float(result['confidence']),
                    "current_config_score": float(result['scores'].get('current_config', 0)),
                    "aggressive_qos_score": float(result['scores'].get('aggressive_qos', 0)),
                    "conservative_qos_score": float(result['scores'].get('conservative_qos', 0))
                },
                "tags": {
                    "decision": result['decision'],
                    "confidence": "high" if result['confidence'] > 0.7 else "medium" if result['confidence'] > 0.5 else "low"
                }
            }]
            self.client.write_points(json_body)
        except Exception as e:
            print(f"Error writing MCDA decision to InfluxDB: {e}")
        
        return result

def main():
    """Test MCDA analyzer"""
    analyzer = MCDAAnalyzer()
    
    # Collect real metrics from network
    print("Collecting network metrics...")
    metrics = analyzer.collect_network_metrics()
    print(f"Metrics collected: {metrics}")
    
    # Make decision
    print("\nRunning MCDA analysis...")
    decision = analyzer.make_decision(metrics)
    
    print("\n" + "="*80)
    print("MCDA DECISION RESULT")
    print("="*80)
    print(f"Recommended Configuration: {decision['decision']}")
    print(f"Confidence Level: {decision['confidence']:.2%}")
    print(f"Method: {decision['method']}")

if __name__ == '__main__':
    main()
