# Distributed Redis Cluster on AWS EC2 — Sharding, Replication & Failover Testing

A 6-node Redis Cluster deployed on AWS EC2 to study horizontal scaling,
automatic failover, and performance under load. Includes a multithreaded
Python workload generator that benchmarks throughput and latency, plus
a documented failover experiment.

## Architecture

- **6 EC2 instances** (t3.small, Ubuntu 22.04, us-east-2)
- **3 master nodes**, 3 replica nodes (1:1 master-replica mapping)
- **16,384 hash slots** sharded across masters
- Gossip-protocol coordination for cluster state
- VPC security group with restricted SSH + Redis cluster bus ports (6379, 16379)

## Results

Baseline workload: 10 threads, 60s, 10,000 keys, 60/40 GET/SET ratio.

| Metric | Value |
|--------|-------|
| Throughput | **4,023 ops/sec** |
| Avg latency | 2.47 ms |
| P95 latency | 6.22 ms |
| P99 latency | 9.86 ms |
| Total operations | 241,000+ |

### Failover test
Killed a master node mid-workload. Cluster auto-promoted its replica,
reassigned hash slot ownership, and recovered to steady state.
Throughput dipped ~42% during the transition; latency stayed stable.

## Files

- `workload.py` — multithreaded Redis workload generator (argparse-driven)
- `redis.conf` — Redis cluster configuration
- `start_node.sh` / `stop_node.sh` — node lifecycle helpers
- `check_cluster.sh` — cluster health verification

## Running

\`\`\`bash
# On each EC2 node
sudo systemctl start redis-server

# From the bootstrap node
redis-cli --cluster create <ip1>:6379 <ip2>:6379 ... --cluster-replicas 1

# Run the workload
python3 workload.py --host <node-ip> --threads 10 --duration 60 \
  --keyspace 10000 --get-ratio 0.6 --set-ratio 0.4
\`\`\`

## Tech

Redis 7, AWS EC2, Python 3.11, redis-py-cluster, Ubuntu 22.04

## Context

Built for CSCI 346 (Cloud Computing), CUNY Queens College, Spring 2026.
