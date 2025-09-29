"""
可配置的局域网端口扫描器（TCP）

功能：
- 支持通过 CIDR（如 192.168.1.0/24）或从文件读取主机列表扫描
- 支持单端口 / 多端口 / 端口范围（例如: 22,80,8000-8010）
- 支持超时、并发数等参数
- 支持输出到 CSV 或 JSON 文件
- 可选先 ping 主机以减少不必要端口探测（可能需要管理员权限）
"""

import argparse
import socket
import ipaddress
import concurrent.futures
import csv
import json
import sys
from typing import List, Tuple, Iterable
import subprocess
import platform
import os

def parse_ports(ports_str: str) -> List[int]:
    """解析端口字符串，支持 '22', '22,80', '8000-8010' 的组合"""
    parts = [p.strip() for p in ports_str.split(",") if p.strip()]
    ports = set()
    for p in parts:
        if "-" in p:
            lo, hi = p.split("-", 1)
            lo_i = int(lo)
            hi_i = int(hi)
            if lo_i > hi_i:
                lo_i, hi_i = hi_i, lo_i
            ports.update(range(lo_i, hi_i + 1))
        else:
            ports.add(int(p))
    return sorted(p for p in ports if 0 < p <= 65535)

def load_hosts_from_file(path: str) -> List[str]:
    """从文件读取每行一个 IP/host（忽略空行和注释）"""
    hosts = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            hosts.append(line)
    return hosts

def expand_network(network_cidr: str) -> List[str]:
    """将 CIDR 展开为主机 IP 列表（排除网络地址和广播）"""
    net = ipaddress.ip_network(network_cidr, strict=False)
    return [str(ip) for ip in net.hosts()]

def expand_ip_range(start_ip: str, end_ip: str) -> List[str]:
    """根据开始和结束 IP（包含两端）生成主机列表"""
    start = int(ipaddress.IPv4Address(start_ip))
    end = int(ipaddress.IPv4Address(end_ip))
    if start > end:
        start, end = end, start
    return [str(ipaddress.IPv4Address(i)) for i in range(start, end + 1)]

def is_host_alive_ping(host: str, timeout: float = 1.0) -> bool:
    """使用系统 ping 判断主机是否在线（跨平台）"""
    system = platform.system().lower()
    # windows: -n count, -w timeout(ms)
    # linux/mac: -c count, -W timeout(s) (note: mac uses -W in milliseconds on some systems — 兼容性有限)
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), host]
    else:
        # 优先使用 ping 的短超时参数（大多数 linux 支持 -W 秒）
        cmd = ["ping", "-c", "1", "-W", str(int(timeout)), host]
    try:
        with open(os.devnull, "wb") as devnull:
            return subprocess.call(cmd, stdout=devnull, stderr=devnull) == 0
    except Exception:
        return False

def check_tcp_port(host: str, port: int, timeout: float = 0.5) -> bool:
    """检查 TCP 端口是否开放，返回 True/False"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            return result == 0
    except Exception:
        return False

def scan_targets(hosts: Iterable[str], ports: Iterable[int], timeout: float, workers: int,
                 ping_first: bool = False) -> List[Tuple[str, int]]:
    """
    并发扫描
    返回开放的 (host, port) 列表
    """
    tasks = []
    open_list = []

    # 如果启用 ping_first，先筛选存活主机
    if ping_first:
        alive_hosts = []
        print("正在 ping 主机以筛选存活目标...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(200, workers)) as pool:
            fut_to_host = {pool.submit(is_host_alive_ping, h, max(1, int(timeout))): h for h in hosts}
            for fut in concurrent.futures.as_completed(fut_to_host):
                h = fut_to_host[fut]
                try:
                    if fut.result():
                        alive_hosts.append(h)
                    else:
                        # 可选：打印不可达
                        pass
                except Exception:
                    pass
        hosts = alive_hosts
        print(f"存活主机数: {len(hosts)}")

    # 生成 (host,port) 任务
    for h in hosts:
        for p in ports:
            tasks.append((h, p))

    total = len(tasks)
    if total == 0:
        return []

    print(f"将并发检测 {len(hosts)} 台主机上的 {len(ports)} 个端口，共 {total} 个任务，workers={workers}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_task = {
            executor.submit(check_tcp_port, host, port, timeout): (host, port) for host, port in tasks
        }
        completed = 0
        for fut in concurrent.futures.as_completed(future_to_task):
            host, port = future_to_task[fut]
            completed += 1
            try:
                if fut.result():
                    print(f"[+] {host}:{port} 开放")
                    open_list.append((host, port))
            except Exception as e:
                # 忽略单个任务错误
                pass
            # 简单进度显示
            if completed % 100 == 0 or completed == total:
                print(f"进度: {completed}/{total}")
    return open_list

def save_results(open_list: List[Tuple[str, int]], out_path: str, fmt: str = "csv"):
    """保存结果到 CSV 或 JSON"""
    if fmt == "csv":
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["host", "port"])
            for host, port in open_list:
                writer.writerow([host, port])
    elif fmt == "json":
        data = [{"host": h, "port": p} for h, p in open_list]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    else:
        raise ValueError("不支持的输出格式: " + fmt)

def main():
    """运行主函数"""
    parser = argparse.ArgumentParser(description="可配置的局域网端口扫描器（仅 TCP）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--network", "-n", help="要扫描的网段，CIDR 格式，例如 192.168.1.0/24")
    group.add_argument("--hosts-file", "-f", help="从文件读取主机列表（每行一个 IP/hostname）")
    group.add_argument("--start-end", nargs=2, metavar=("START_IP", "END_IP"),
                       help="指定起止 IP（包含），例如 --start-end 192.168.1.10 192.168.1.50")
    group.add_argument("--host", "-H", help="单个主机或 IP，例如 192.168.1.15")

    parser.add_argument("--ports", "-p", required=True,
                        help="要扫描的端口：单端口/逗号分隔/范围，例如 22 或 22,80,8000-8010")
    parser.add_argument("--timeout", type=float, default=0.5, help="端口连接超时（秒），默认 0.5")
    parser.add_argument("--workers", type=int, default=200, help="并发线程数（默认 200）")
    parser.add_argument("--ping-first", action="store_true", help="先 ping 主机，跳过不可达的主机（可选）")
    parser.add_argument("--output", "-o", help="输出文件路径（可选），根据扩展名选择 csv/json，例如 out.csv 或 out.json")
    parser.add_argument("--no-print", action="store_true", help="不在控制台打印每个开放端口，只保存到文件（若指定了 --output）")
    args = parser.parse_args()

    # 准备主机列表
    hosts = []
    if args.network:
        try:
            hosts = expand_network(args.network)
        except Exception as e:
            print("解析网络失败:", e, file=sys.stderr)
            sys.exit(1)
    elif args.hosts_file:
        try:
            hosts = load_hosts_from_file(args.hosts_file)
        except Exception as e:
            print("读取 hosts 文件失败:", e, file=sys.stderr)
            sys.exit(1)
    elif args.start_end:
        hosts = expand_ip_range(args.start_end[0], args.start_end[1])
    elif args.host:
        hosts = [args.host]

    if not hosts:
        print("没有目标主机，退出。", file=sys.stderr)
        sys.exit(1)

    # 解析端口
    try:
        ports = parse_ports(args.ports)
    except Exception as e:
        print("解析端口失败:", e, file=sys.stderr)
        sys.exit(1)
    if not ports:
        print("没有有效端口，退出。", file=sys.stderr)
        sys.exit(1)

    open_list = scan_targets(hosts, ports, timeout=args.timeout, workers=args.workers, ping_first=args.ping_first)

    # 输出
    if args.output:
        fmt = "csv" if args.output.lower().endswith(".csv") else "json" if args.output.lower().endswith(".json") else None
        if not fmt:
            print("输出文件请使用 .csv 或 .json 扩展名。", file=sys.stderr)
            sys.exit(1)
        try:
            save_results(open_list, args.output, fmt)
            print(f"结果已保存到 {args.output}，共 {len(open_list)} 条开放记录。")
        except Exception as e:
            print("保存结果失败:", e, file=sys.stderr)
            sys.exit(1)

    if not args.no_print and not args.output:
        # 控制台打印
        if open_list:
            print("\n扫描结果（开放端口）:")
            for host, port in sorted(open_list):
                print(f"{host}:{port}")
        else:
            print("\n未发现开放端口。")

if __name__ == "__main__":
    main()
