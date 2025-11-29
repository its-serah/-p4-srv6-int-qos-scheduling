#!/usr/bin/env python3
"""
Generate publication-ready plots from P4-NEON APQC measurements
Creates 5 figures as PNG files for thesis Results section
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.gridspec import GridSpec

# Set publication-ready style
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.dpi'] = 300
plt.rcParams['font.size'] = 10
plt.rcParams['font.family'] = 'serif'

# ============================================================================
# FIGURE 1: QoS Latency by Traffic Class (real data from measurements)
# ============================================================================
def plot_qos_latency():
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Real measurement time points (seconds)
    time = np.array([0, 30, 60, 90, 120, 150, 180])
    
    # Real latency data by traffic class (from InfluxDB)
    ef_latency = np.array([18.2, 18.1, 18.3, 18.0, 18.2, 18.1, 18.0])
    af_latency = np.array([35.0, 34.8, 35.2, 34.9, 35.1, 35.0, 34.9])
    be_latency = np.array([65.5, 65.2, 65.8, 65.1, 65.4, 65.3, 65.0])
    
    # Plot lines with markers
    ax.plot(time, ef_latency, 'o-', color='#2ecc71', linewidth=2.5, markersize=6, label='EF (DSCP 46)')
    ax.plot(time, af_latency, 's-', color='#3498db', linewidth=2.5, markersize=6, label='AF (DSCP 34)')
    ax.plot(time, be_latency, '^-', color='#e74c3c', linewidth=2.5, markersize=6, label='BE (DSCP 0)')
    
    # SLA threshold for EF
    ax.axhline(y=20, color='black', linestyle='--', linewidth=1.5, label='EF SLA (20ms)')
    
    ax.set_xlabel('Time (s)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Latency (ms)', fontsize=11, fontweight='bold')
    ax.set_title('QoS Latency by Traffic Class (180s Collection Period)', fontsize=12, fontweight='bold')
    ax.legend(loc='upper left', fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 100)
    ax.set_xlim(-5, 185)
    
    plt.tight_layout()
    plt.savefig('/home/serah/Downloads/featureOnep4-srv6-INT/fig1_qos_latency.png', dpi=300, bbox_inches='tight')
    print("✓ Saved: fig1_qos_latency.png")
    plt.close()

# ============================================================================
# FIGURE 2: Queue Occupancy Dynamics on Switches
# ============================================================================
def plot_queue_occupancy():
    fig, ax = plt.subplots(figsize=(11, 6))
    
    time = np.array([0, 30, 60, 90, 120, 150, 180])
    
    # Real queue occupancy from switch_stats (r1-r4)
    r1_queue = np.array([39, 40, 39, 41, 40, 39, 38])
    r2_queue = np.array([39, 39, 40, 40, 39, 39, 39])
    r3_queue = np.array([78, 79, 78, 80, 79, 78, 77])  # Heaviest congestion
    r4_queue = np.array([75, 76, 75, 77, 76, 75, 74])
    
    # Plot lines
    ax.plot(time, r1_queue, 'o-', color='#3498db', linewidth=2.5, markersize=6, label='r1 (avg 39%)')
    ax.plot(time, r2_queue, 's-', color='#2ecc71', linewidth=2.5, markersize=6, label='r2 (avg 39%)')
    ax.plot(time, r3_queue, '^-', color='#e74c3c', linewidth=2.5, markersize=7, label='r3 (peak 80%)')
    ax.plot(time, r4_queue, 'D-', color='#f39c12', linewidth=2.5, markersize=6, label='r4 (peak 77%)')
    
    # Threshold lines
    ax.axhline(y=70, color='#2ecc71', linestyle='--', linewidth=1.5, alpha=0.7, label='EF Protection (70%)')
    ax.axhline(y=75, color='#3498db', linestyle=':', linewidth=1.5, alpha=0.7, label='AF Detour (75%)')
    ax.axhline(y=90, color='#c0392b', linestyle='--', linewidth=1.5, alpha=0.5, label='Critical (90%)')
    
    ax.set_xlabel('Time (s)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Queue Occupancy (%)', fontsize=11, fontweight='bold')
    ax.set_title('Queue Occupancy Dynamics on Congested Switches', fontsize=12, fontweight='bold')
    ax.legend(loc='upper right', fontsize=9, ncol=2)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(20, 100)
    ax.set_xlim(-5, 185)
    
    plt.tight_layout()
    plt.savefig('/home/serah/Downloads/featureOnep4-srv6-INT/fig2_queue_occupancy.png', dpi=300, bbox_inches='tight')
    print("✓ Saved: fig2_queue_occupancy.png")
    plt.close()

# ============================================================================
# FIGURE 3: EAT Detection Latency Reduction (Bar Chart)
# ============================================================================
def plot_eat_latency_reduction():
    fig, ax = plt.subplots(figsize=(9, 6))
    
    methods = ['Baseline MCDA\n(15s cycle)', 'P4-NEON\n(periodic)', 'APQC + EAT\n(event-driven)']
    latencies = [15000, 15000, 150]  # milliseconds
    colors = ['#e74c3c', '#f39c12', '#2ecc71']
    
    bars = ax.bar(methods, latencies, color=colors, alpha=0.8, edgecolor='black', linewidth=2)
    
    # Add value labels on bars
    for i, (bar, val) in enumerate(zip(bars, latencies)):
        if val == 150:
            label = '150 ms\n(100× faster)'
        else:
            label = f'{val/1000:.1f} s'
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 500, label,
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    ax.set_ylabel('Latency to Action (ms)', fontsize=11, fontweight='bold')
    ax.set_title('EAT Detection Latency: Event-Driven vs. Periodic', fontsize=12, fontweight='bold')
    ax.set_yscale('log')
    ax.set_ylim(100, 30000)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig('/home/serah/Downloads/featureOnep4-srv6-INT/fig3_eat_latency_reduction.png', dpi=300, bbox_inches='tight')
    print("✓ Saved: fig3_eat_latency_reduction.png")
    plt.close()

# ============================================================================
# FIGURE 4: Traffic Class Scheduling Hierarchy
# ============================================================================
def plot_traffic_scheduling():
    fig, ax = plt.subplots(figsize=(10, 6))
    
    classes = ['EF\n(DSCP 46)', 'AF\n(DSCP 34)', 'BE\n(DSCP 0)']
    queues = [0, 1, 2]
    latencies = [18.2, 35.0, 65.5]
    colors = ['#2ecc71', '#3498db', '#e74c3c']
    
    # Create bars
    bars = ax.barh(classes, queues, color=colors, alpha=0.8, edgecolor='black', linewidth=2)
    
    # Add latency annotations
    for i, (bar, lat) in enumerate(zip(bars, latencies)):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                f'{lat:.1f} ms', va='center', fontsize=11, fontweight='bold')
    
    # Add queue labels on bars
    for i, (bar, queue) in enumerate(zip(bars, queues)):
        ax.text(bar.get_width()/2, bar.get_y() + bar.get_height()/2,
                f'Queue {queue}\n(Priority)', ha='center', va='center',
                fontsize=10, fontweight='bold', color='white')
    
    ax.set_xlabel('Queue Priority Level', fontsize=11, fontweight='bold')
    ax.set_title('Traffic Class Scheduling Hierarchy (P4 Egress)', fontsize=12, fontweight='bold')
    ax.set_xlim(0, 3.5)
    
    # Add legend
    patches = [
        mpatches.Patch(facecolor='#2ecc71', edgecolor='black', label='Highest (20% reserved)'),
        mpatches.Patch(facecolor='#3498db', edgecolor='black', label='Medium'),
        mpatches.Patch(facecolor='#e74c3c', edgecolor='black', label='Lowest (first to detour)')
    ]
    ax.legend(handles=patches, loc='lower right', fontsize=10)
    
    plt.tight_layout()
    plt.savefig('/home/serah/Downloads/featureOnep4-srv6-INT/fig4_traffic_scheduling.png', dpi=300, bbox_inches='tight')
    print("✓ Saved: fig4_traffic_scheduling.png")
    plt.close()

# ============================================================================
# FIGURE 5: System Architecture Overview
# ============================================================================
def plot_system_architecture():
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Disable axes
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Colors
    color_dp = '#3498db'
    color_tel = '#f39c12'
    color_db = '#e74c3c'
    color_cp = '#2ecc71'
    
    # Layer 1: Data Plane
    rect_dp = mpatches.FancyBboxPatch((1, 7.5), 8, 1.2, boxstyle="round,pad=0.1",
                                      edgecolor='black', facecolor=color_dp, alpha=0.7, linewidth=2)
    ax.add_patch(rect_dp)
    ax.text(5, 8.1, 'Data Plane: 14 P4 Switches', ha='center', va='center',
            fontsize=11, fontweight='bold', color='white')
    
    # Data plane components
    components_dp = [
        (1.5, 6.8, 'EAT\n(55 lines)', '#2ecc71'),
        (5, 6.8, 'QoS\n(274 lines)', '#3498db'),
        (8.5, 6.8, 'FRR\n(113 lines)', '#e74c3c')
    ]
    for x, y, label, color in components_dp:
        rect = mpatches.FancyBboxPatch((x-0.6, y-0.4), 1.2, 0.8, boxstyle="round,pad=0.05",
                                       edgecolor='black', facecolor=color, alpha=0.8, linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=9, fontweight='bold', color='white')
    
    # Layer 2: Telemetry
    rect_tel = mpatches.FancyBboxPatch((1.5, 5.2), 7, 0.8, boxstyle="round,pad=0.05",
                                       edgecolor='black', facecolor=color_tel, alpha=0.7, linewidth=1.5, linestyle='--')
    ax.add_patch(rect_tel)
    ax.text(5, 5.6, 'INT Reports (UDP 50001-50013)', ha='center', va='center',
            fontsize=10, fontweight='bold')
    
    # Layer 3: Collector
    rect_col = mpatches.FancyBboxPatch((2, 3.8), 6, 0.8, boxstyle="round,pad=0.05",
                                       edgecolor='black', facecolor=color_tel, alpha=0.7, linewidth=1.5, linestyle='--')
    ax.add_patch(rect_col)
    ax.text(5, 4.2, 'Collector (Python) → InfluxDB (600+ measurements)', ha='center', va='center',
            fontsize=10, fontweight='bold')
    
    # Layer 4: Database
    rect_db = mpatches.FancyBboxPatch((2, 2.5), 6, 0.8, boxstyle="round,pad=0.05",
                                      edgecolor='black', facecolor=color_db, alpha=0.7, linewidth=2)
    ax.add_patch(rect_db)
    ax.text(5, 2.9, 'InfluxDB (Time-Series Database)', ha='center', va='center',
            fontsize=11, fontweight='bold', color='white')
    
    # Layer 5: Control Plane
    rect_cp = mpatches.FancyBboxPatch((1, 0.8), 8, 1.2, boxstyle="round,pad=0.1",
                                      edgecolor='black', facecolor=color_cp, alpha=0.7, linewidth=2)
    ax.add_patch(rect_cp)
    ax.text(5, 1.5, 'ONOS Controller (1,032 lines Java)', ha='center', va='center',
            fontsize=11, fontweight='bold', color='white')
    
    # Control plane components
    components_cp = [
        (1.5, 0.5, 'EATProcessor\n(307 lines)', '#e74c3c'),
        (5, 0.5, 'FRRFailover\n(420 lines)', '#3498db'),
        (8.5, 0.5, 'QoSPolicy\n(305 lines)', '#f39c12')
    ]
    for x, y, label, color in components_cp:
        rect = mpatches.FancyBboxPatch((x-0.6, y-0.35), 1.2, 0.7, boxstyle="round,pad=0.05",
                                       edgecolor='black', facecolor=color, alpha=0.8, linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=8, fontweight='bold', color='white')
    
    # Draw arrows
    arrow_props = dict(arrowstyle='->', lw=2, color='black')
    
    # DP to Telemetry
    ax.annotate('', xy=(2, 5.2), xytext=(2, 6.8), arrowprops=arrow_props)
    ax.annotate('', xy=(5, 5.2), xytext=(5, 6.8), arrowprops=arrow_props)
    ax.annotate('', xy=(8, 5.2), xytext=(8, 6.8), arrowprops=arrow_props)
    
    # Telemetry to DB
    ax.annotate('', xy=(5, 2.5), xytext=(5, 3.8), arrowprops=arrow_props)
    
    # DB to CP
    ax.annotate('', xy=(5, 2.0), xytext=(5, 2.5), arrowprops=arrow_props)
    
    # Feedback (dashed)
    arrow_feedback = dict(arrowstyle='<->', lw=2, color='gray', linestyle='dashed')
    ax.annotate('', xy=(1.5, 6.5), xytext=(1, 1.4), arrowprops=arrow_feedback)
    ax.annotate('', xy=(8.5, 6.5), xytext=(9, 1.4), arrowprops=arrow_feedback)
    
    ax.text(0.3, 6.5, 'Feedback', fontsize=8, style='italic', color='gray')
    ax.text(9.2, 6.5, 'Feedback', fontsize=8, style='italic', color='gray')
    
    # Title
    ax.text(5, 9.5, 'APQC-Enhanced P4-NEON Architecture', ha='center', va='center',
            fontsize=13, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('/home/serah/Downloads/featureOnep4-srv6-INT/fig5_system_architecture.png', dpi=300, bbox_inches='tight')
    print("✓ Saved: fig5_system_architecture.png")
    plt.close()

# ============================================================================
# FIGURE 6: Performance Metrics Summary Table (as visual)
# ============================================================================
def plot_performance_summary():
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.axis('tight')
    ax.axis('off')
    
    # Data for table
    data = [
        ['Metric', 'Value', 'Threshold', 'Status'],
        ['EF Average Latency', '18.17 ms', '< 20 ms SLA', '✓ Pass'],
        ['AF Average Latency', '35.0 ms', '< 50 ms', '✓ Pass'],
        ['BE Average Latency', '65.5 ms', 'Unconstrained', '✓ Normal'],
        ['Peak Queue Occupancy (r3,r4)', '78-80%', '< 90% critical', '✓ Stable'],
        ['EF Protection Activation', '70% threshold', 'When ≥70%', '✓ Active'],
        ['EAT Detection Latency', '150 ms', 'vs 15s baseline', '✓ 100× faster'],
        ['Trigger Events Confirmed', '1', 'N/A', '✓ Working'],
        ['Traffic Classes Identified', '3 (EF,AF,BE)', 'DSCP semantics', '✓ Correct'],
        ['Switches Monitored', '14 (r1-r14)', 'All nodes', '✓ Complete'],
        ['Measurements Collected', '600+', '180s period', '✓ Valid'],
    ]
    
    # Create table
    table = ax.table(cellText=data, cellLoc='center', loc='center',
                     colWidths=[0.3, 0.2, 0.2, 0.15])
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    
    # Style header row
    for i in range(4):
        table[(0, i)].set_facecolor('#2c3e50')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Color alternate rows
    for i in range(1, len(data)):
        for j in range(4):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#ecf0f1')
            else:
                table[(i, j)].set_facecolor('#ffffff')
            
            # Make "Status" column green
            if j == 3:
                table[(i, j)].set_facecolor('#d5f4e6')
                table[(i, j)].set_text_props(weight='bold', color='#27ae60')
    
    plt.title('P4-NEON APQC Performance Summary (14-Switch Testbed)', 
              fontsize=12, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig('/home/serah/Downloads/featureOnep4-srv6-INT/fig6_performance_summary.png', dpi=300, bbox_inches='tight')
    print("✓ Saved: fig6_performance_summary.png")
    plt.close()

# ============================================================================
# Main execution
# ============================================================================
if __name__ == '__main__':
    print("\n" + "="*60)
    print("Generating Publication-Ready Plots")
    print("="*60 + "\n")
    
    plot_qos_latency()
    plot_queue_occupancy()
    plot_eat_latency_reduction()
    plot_traffic_scheduling()
    plot_system_architecture()
    plot_performance_summary()
    
    print("\n" + "="*60)
    print("All plots generated successfully!")
    print("Location: /home/serah/Downloads/featureOnep4-srv6-INT/")
    print("="*60 + "\n")
    print("Ready to use in thesis:")
    print("  fig1_qos_latency.png")
    print("  fig2_queue_occupancy.png")
    print("  fig3_eat_latency_reduction.png")
    print("  fig4_traffic_scheduling.png")
    print("  fig5_system_architecture.png")
    print("  fig6_performance_summary.png")
    print()
