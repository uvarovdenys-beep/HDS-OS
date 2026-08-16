#!/usr/bin/env python3
# agent/port_checker.py
"""
HDS Port Checker - System port availability verification
Checks socket.bind(), lsof, netstat to identify occupied ports
"""

import os
import socket
import subprocess
import platform
import sys
import time
from typing import Dict, List, Tuple, Optional

class PortChecker:
    """
    System port availability verification across platforms
    Works on Linux, macOS, Windows
    """

    OS = platform.system()  # Linux, Darwin (macOS), Windows

    @staticmethod
    def is_port_available(port: int) -> Tuple[bool, str]:
        """
        Check if port is available
        Returns: (is_available, reason)
        """

        # 1. Basic socket.bind() check
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('127.0.0.1', port))
            s.close()
        except OSError as e:
            return False, f"Socket bind failed: {e}"

        # 2. Check via lsof (Linux/macOS)
        if PortChecker.OS in ['Linux', 'Darwin']:
            try:
                result = subprocess.run(
                    ['lsof', '-i', f':{port}'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0 and result.stdout:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:  # First line is the header
                        process_info = lines[1]
                        parts = process_info.split()
                        if len(parts) > 1:
                            pid = parts[1]
                            process_name = parts[0]
                            return False, f"Port occupied by {process_name} (PID: {pid})"
            except (FileNotFoundError, subprocess.TimeoutExpired, IndexError):
                pass  # lsof not installed, continue

        # 3. Check via netstat (Windows, Linux)
        if PortChecker.OS == 'Windows':
            try:
                result = subprocess.run(
                    ['netstat', '-ano'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                for line in result.stdout.split('\n'):
                    if f':{port}' in line and 'LISTENING' in line:
                        parts = line.split()
                        if len(parts) > 0:
                            pid = parts[-1]
                            return False, f"Port occupied (Windows PID: {pid})"
            except (FileNotFoundError, subprocess.TimeoutExpired, IndexError):
                pass

        return True, "Port is available"

    @staticmethod
    def get_process_info(port: int) -> Dict:
        """
        Get detailed information about process using the port
        """
        info = {
            'port': port,
            'available': False,
            'pid': None,
            'process_name': None,
            'process_cmd': None,
            'user': None,
            'status': None
        }

        if PortChecker.OS in ['Linux', 'Darwin']:
            try:
                result = subprocess.run(
                    ['lsof', '-i', f':{port}'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0 and result.stdout:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        process_line = lines[1]
                        parts = process_line.split()
                        if len(parts) > 1:
                            info['pid'] = parts[1]
                            info['process_name'] = parts[0]

                            # Get full process command
                            try:
                                cmd_result = subprocess.run(
                                    ['ps', '-p', info['pid'], '-o', 'cmd='],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                if cmd_result.returncode == 0:
                                    info['process_cmd'] = cmd_result.stdout.strip()
                            except:
                                pass
            except (FileNotFoundError, subprocess.TimeoutExpired, IndexError):
                pass

        return info

    @staticmethod
    def find_available_ports(start_port: int, count: int = 3) -> List[int]:
        """
        Find N available ports starting from start_port
        Important: checks one by one, cannot check all at once!
        """
        available = []
        port = start_port
        max_attempts = 500  # Do not search beyond this

        while len(available) < count and (port - start_port) < max_attempts:
            is_available, reason = PortChecker.is_port_available(port)

            if is_available:
                available.append(port)
                print(f"  ✅ Port {port}: {reason}")
            else:
                # Show which process occupies the port
                info = PortChecker.get_process_info(port)
                if info['process_name']:
                    print(f"  ❌ Port {port}: {reason}")
                    if info['process_cmd']:
                        cmd_short = info['process_cmd'][:45]
                        print(f"     └─ {cmd_short}{'...' if len(info['process_cmd']) > 45 else ''}")

            port += 1

        if len(available) < count:
            raise RuntimeError(
                f"Could not find {count} available ports starting from {start_port}. "
                f"Found only {len(available)}: {available}\n"
                f"Try: --auto-kill to terminate conflicting processes"
            )

        return available

    @staticmethod
    def print_port_status(ports: List[int]) -> None:
        """
        Print formatted port status report
        """
        print("\n" + "="*70)
        print("PORT STATUS REPORT")
        print("="*70)

        for port in ports:
            is_available, reason = PortChecker.is_port_available(port)

            if is_available:
                print(f"  ✅ {port:5d} | AVAILABLE")
            else:
                info = PortChecker.get_process_info(port)
                if info['process_name']:
                    print(f"  ❌ {port:5d} | OCCUPIED by {info['process_name']} (PID: {info['pid']})")
                    if info['process_cmd']:
                        cmd_short = info['process_cmd'][:50]
                        print(f"            | {cmd_short}{'...' if len(info['process_cmd']) > 50 else ''}")
                else:
                    print(f"  ⚠️  {port:5d} | UNKNOWN - {reason}")

        print("="*70 + "\n")

    @staticmethod
    def kill_process_on_port(port: int, force: bool = False) -> bool:
        """
        Terminate process on port (when restart needed)
        force=True → kill -9 (SIGKILL), force=False → graceful shutdown (SIGTERM)
        """
        info = PortChecker.get_process_info(port)

        if not info['pid']:
            print(f"  ❓ No process found on port {port}")
            return False

        pid = info['pid']
        process_name = info['process_name']

        print(f"  🔄 Terminating {process_name} (PID: {pid})...", end=' ')

        try:
            if PortChecker.OS == 'Windows':
                os.kill(int(pid), 9)
                print("✅")
            else:
                # Linux/macOS: first SIGTERM, then SIGKILL
                signal_num = 9 if force else 15
                signal_name = 'SIGKILL' if force else 'SIGTERM'

                subprocess.run(
                    ['kill', f'-{signal_num}', pid],
                    timeout=5,
                    capture_output=True
                )

                if not force:
                    # Wait 2 seconds, then SIGKILL if needed
                    time.sleep(2)
                    is_available, _ = PortChecker.is_port_available(int(port))
                    if not is_available:
                        print(f"\n  ⚠️  Process didn't exit, forcing...", end=' ')
                        subprocess.run(['kill', '-9', pid], timeout=5, capture_output=True)
                        print("✅")
                    else:
                        print("✅")
                else:
                    print("✅")

            return True
        except Exception as e:
            print(f"❌\n  Error: {e}")
            return False


def main():
    """CLI for port_checker testing"""
    if len(sys.argv) < 2:
        print("Usage: python3 port_checker.py [check|kill] [port]")
        print("       python3 port_checker.py find [start_port] [count]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "check":
        port = int(sys.argv[2])
        is_available, reason = PortChecker.is_port_available(port)
        print(f"Port {port}: {'AVAILABLE' if is_available else 'OCCUPIED'}")
        print(f"Reason: {reason}")

        if not is_available:
            info = PortChecker.get_process_info(port)
            print(f"Process: {info['process_name']} (PID: {info['pid']})")
            if info['process_cmd']:
                print(f"Command: {info['process_cmd']}")

    elif command == "find":
        start = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 3

        print(f"Looking for {count} available ports starting from {start}...\n")
        ports = PortChecker.find_available_ports(start, count)
        print(f"\n✅ Found ports: {ports}")

    elif command == "kill":
        port = int(sys.argv[2])
        force = '--force' in sys.argv
        PortChecker.kill_process_on_port(port, force=force)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
