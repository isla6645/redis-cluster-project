import argparse
import random
import string
import threading
import time
import statistics
from collections import defaultdict

from redis.cluster import RedisCluster

stop_event = threading.Event()
lock = threading.Lock()

latencies_ms = []
op_counts = defaultdict(int)
error_counts = defaultdict(int)


def random_key(keyspace_size: int) -> str:
    idx = random.randint(1, keyspace_size)
    return f"key:{idx}"


def random_value(length: int = 32) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def choose_operation(get_ratio: float, set_ratio: float, incr_ratio: float, del_ratio: float) -> str:
    r = random.random()
    if r < get_ratio:
        return "GET"
    elif r < get_ratio + set_ratio:
        return "SET"
    elif r < get_ratio + set_ratio + incr_ratio:
        return "INCR"
    else:
        return "DEL"


def worker(
    startup_host: str,
    startup_port: int,
    keyspace_size: int,
    get_ratio: float,
    set_ratio: float,
    incr_ratio: float,
    del_ratio: float
):
    try:
        rc = RedisCluster(
            host=startup_host,
            port=startup_port,
            decode_responses=True
        )
    except Exception as e:
        with lock:
            error_counts["connect"] += 1
        return

    while not stop_event.is_set():
        op = choose_operation(get_ratio, set_ratio, incr_ratio, del_ratio)
        key = random_key(keyspace_size)
        start = time.perf_counter()

        try:
            if op == "GET":
                rc.get(key)
            elif op == "SET":
                rc.set(key, random_value())
            elif op == "INCR":
                rc.incr(key)
            elif op == "DEL":
                rc.delete(key)

            elapsed_ms = (time.perf_counter() - start) * 1000.0

            with lock:
                latencies_ms.append(elapsed_ms)
                op_counts[op] += 1

        except Exception:
            with lock:
                error_counts[op] += 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True, help="Startup node host")
    parser.add_argument("--port", type=int, default=6379, help="Startup node port")
    parser.add_argument("--threads", type=int, default=8, help="Number of worker threads")
    parser.add_argument("--duration", type=int, default=60, help="Benchmark duration in seconds")
    parser.add_argument("--keyspace", type=int, default=10000, help="Number of distinct keys")
    parser.add_argument("--get-ratio", type=float, default=0.50)
    parser.add_argument("--set-ratio", type=float, default=0.30)
    parser.add_argument("--incr-ratio", type=float, default=0.10)
    parser.add_argument("--del-ratio", type=float, default=0.10)
    args = parser.parse_args()

    total_ratio = args.get_ratio + args.set_ratio + args.incr_ratio + args.del_ratio
    if abs(total_ratio - 1.0) > 1e-9:
        raise ValueError("Operation ratios must sum to 1.0")

    threads = []
    start_time = time.time()

    for _ in range(args.threads):
        t = threading.Thread(
            target=worker,
            args=(
                args.host,
                args.port,
                args.keyspace,
                args.get_ratio,
                args.set_ratio,
                args.incr_ratio,
                args.del_ratio
            ),
            daemon=True
        )
        t.start()
        threads.append(t)

    time.sleep(args.duration)
    stop_event.set()

    for t in threads:
        t.join(timeout=2)

    end_time = time.time()
    runtime = end_time - start_time

    total_ops = sum(op_counts.values())
    throughput = total_ops / runtime if runtime > 0 else 0

    print("\n===== Workload Summary =====")
    print(f"Runtime (s): {runtime:.2f}")
    print(f"Threads: {args.threads}")
    print(f"Keyspace size: {args.keyspace}")
    print(f"Total operations: {total_ops}")
    print(f"Throughput (ops/sec): {throughput:.2f}")

    for op, count in sorted(op_counts.items()):
        print(f"{op} count: {count}")

    for op, count in sorted(error_counts.items()):
        print(f"{op} errors: {count}")

    if latencies_ms:
        print(f"Average latency (ms): {statistics.mean(latencies_ms):.3f}")
        print(f"Median latency (ms): {statistics.median(latencies_ms):.3f}")
        if len(latencies_ms) >= 20:
            sorted_lat = sorted(latencies_ms)
            p95_index = int(0.95 * len(sorted_lat)) - 1
            p99_index = int(0.99 * len(sorted_lat)) - 1
            print(f"P95 latency (ms): {sorted_lat[max(p95_index, 0)]:.3f}")
            print(f"P99 latency (ms): {sorted_lat[max(p99_index, 0)]:.3f}")
    else:
        print("No successful operations recorded.")


if __name__ == "__main__":
    main()