#!/usr/bin/env python3
# agent/port_registry.py
"""
HDS Port Registry - Dynamic port allocation management
Each HDS instance receives unique ports: Vision, Browser, Webhook
"""

import json
import time
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional
from port_checker import PortChecker


class PortRegistry:
    """
    Port registration system for dynamic port distribution
    """

    REGISTRY_FILE = Path("ai-mind/deployment/port_registry.json")

    @staticmethod
    def init_registry_dir():
        """Initialize registry directory"""
        PortRegistry.REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def load_registry() -> Dict:
        """Load port registry from file"""
        if PortRegistry.REGISTRY_FILE.exists():
            try:
                return json.loads(PortRegistry.REGISTRY_FILE.read_text())
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def save_registry(registry: Dict) -> None:
        """Save port registry to file"""
        PortRegistry.init_registry_dir()
        PortRegistry.REGISTRY_FILE.write_text(
            json.dumps(registry, indent=2)
        )

    @staticmethod
    def allocate_instance(deploying_ai: str = "unknown",
                          auto_kill: bool = False) -> Dict:
        """
        Allocate 3 unique ports with system verification

        Args:
            deploying_ai: AI system name (GPT-4, Claude, Llama, etc.)
            auto_kill: If True, terminate processes on occupied ports

        Returns:
            config: {instance_id, vision_port, browser_port, webhook_port, ...}
        """

        print(f"\n🔍 Allocating ports for: {deploying_ai}")
        print("⚠️  Checking system for port availability...\n")

        # Load existing registry
        registry = PortRegistry.load_registry()

        # Determine instance number based on existing count
        instance_number = len(registry)  # 0 for first, 1 for second, etc.

        # Ports are allocated by pattern:
        # Instance 0: Vision=9001, Browser=9002, Webhook=8080
        # Instance 1: Vision=9011, Browser=9012, Webhook=8090
        # Instance 2: Vision=9021, Browser=9022, Webhook=8100
        # Pattern: increment by 10 for Vision/Browser, by 10 for Webhook
        vision_port = 9001 + (instance_number * 10)
        browser_port = 9002 + (instance_number * 10)
        webhook_port = 8080 + (instance_number * 10)

        # Check availability of these ports
        ports_to_check = [vision_port, browser_port, webhook_port]
        ports_available = all(
            PortChecker.is_port_available(port)[0]
            for port in ports_to_check
        )

        if not ports_available:
            if auto_kill:
                print("\n🔄 Attempting to reclaim ports by killing processes...")
                print(f"   Target ports: {vision_port}, {browser_port}, {webhook_port}\n")

                # Try to terminate processes on occupied ports
                killed_any = False
                for port in ports_to_check:
                    is_available, _ = PortChecker.is_port_available(port)
                    if not is_available:
                        if PortChecker.kill_process_on_port(port, force=True):
                            killed_any = True
                            time.sleep(0.5)  # Give the system time to recover

                if killed_any:
                    print("\n⏳ Waiting for system to stabilize...")
                    time.sleep(2)

                    # Re-check ports
                    print("🔍 Re-checking ports...\n")
                    ports_available = all(
                        PortChecker.is_port_available(port)[0]
                        for port in ports_to_check
                    )
                    if not ports_available:
                        print(f"\n❌ Still unable to allocate ports: {ports_to_check}")
                        sys.exit(1)
                else:
                    print(f"\n❌ Ports {ports_to_check} are occupied")
                    print("\n💡 Tip: Run with --auto-kill to terminate conflicting processes")
                    sys.exit(1)
            else:
                print(f"\n❌ Ports {ports_to_check} are not available")
                print("\n💡 Tip: Run with --auto-kill to terminate conflicting processes")
                sys.exit(1)

        # Create unique instance ID
        instance_id = f"hds_{int(time.time())}_{deploying_ai.replace(' ', '_').lower()}"

        # Instance config
        config = {
            "instance_id": instance_id,
            "deploying_ai": deploying_ai,
            "vision_daemon_port": vision_port,
            "browser_daemon_port": browser_port,
            "webhook_port": webhook_port,
            "created_at": time.time(),
            "status": "allocated",
            "pid": os.getpid()
        }

        # Add to registry
        registry[instance_id] = config
        PortRegistry.save_registry(registry)

        # Print result
        print(f"\n✅ PORTS ALLOCATED FOR {deploying_ai.upper()}")
        PortChecker.print_port_status(
            [vision_port, browser_port, webhook_port]
        )

        print(f"Instance ID: {instance_id}")
        print(f"Vision Daemon:  http://localhost:{vision_port}")
        print(f"Browser Daemon: http://localhost:{browser_port}")
        print(f"Webhook API:    http://localhost:{webhook_port}\n")

        return config

    @staticmethod
    def get_instance(instance_id: str) -> Optional[Dict]:
        """Get instance config by ID"""
        registry = PortRegistry.load_registry()
        return registry.get(instance_id)

    @staticmethod
    def list_instances() -> Dict:
        """List all active instances"""
        registry = PortRegistry.load_registry()

        if not registry:
            print("No HDS instances registered")
            return {}

        print("\n" + "="*80)
        print("ACTIVE HDS INSTANCES")
        print("="*80)

        for instance_id, config in registry.items():
            created = time.strftime(
                '%Y-%m-%d %H:%M:%S',
                time.localtime(config['created_at'])
            )
            print(f"\n📌 {config['deploying_ai']} ({instance_id})")
            print(f"   Created: {created}")
            print(f"   Vision:  http://localhost:{config['vision_daemon_port']}")
            print(f"   Browser: http://localhost:{config['browser_daemon_port']}")
            print(f"   Webhook: http://localhost:{config['webhook_port']}")
            print(f"   Status:  {config['status']}")

        print("\n" + "="*80 + "\n")
        return registry

    @staticmethod
    def cleanup_instance(instance_id: str) -> bool:
        """Remove instance from registry"""
        registry = PortRegistry.load_registry()

        if instance_id in registry:
            del registry[instance_id]
            PortRegistry.save_registry(registry)
            print(f"✅ Removed instance: {instance_id}")
            return True
        else:
            print(f"❌ Instance not found: {instance_id}")
            return False


def main():
    """CLI for port management"""
    import argparse

    parser = argparse.ArgumentParser(
        description='HDS Port Registry - Dynamic port allocation'
    )
    parser.add_argument('--allocate', action='store_true',
                       help='Allocate new ports for instance')
    parser.add_argument('--ai', type=str, default='unknown',
                       help='AI system name (GPT-4, Claude, Llama, etc.)')
    parser.add_argument('--auto-kill', action='store_true',
                       help='Kill conflicting processes')
    parser.add_argument('--list', action='store_true',
                       help='List all registered instances')
    parser.add_argument('--get', type=str,
                       help='Get configuration for instance ID')
    parser.add_argument('--cleanup', type=str,
                       help='Remove instance from registry')
    parser.add_argument('--check-ports', action='store_true',
                       help='Check status of specific ports')
    parser.add_argument('--ports', nargs='+', type=int,
                       help='Ports to check (with --check-ports)')

    args = parser.parse_args()

    if args.allocate:
        config = PortRegistry.allocate_instance(
            deploying_ai=args.ai,
            auto_kill=args.auto_kill
        )
        print(json.dumps(config, indent=2))

    elif args.list:
        PortRegistry.list_instances()

    elif args.get:
        config = PortRegistry.get_instance(args.get)
        if config:
            print(json.dumps(config, indent=2))
        else:
            print(f"Instance not found: {args.get}")
            sys.exit(1)

    elif args.cleanup:
        PortRegistry.cleanup_instance(args.cleanup)

    elif args.check_ports:
        if not args.ports:
            print("Use: --check-ports --ports 9001 9002 9003")
            sys.exit(1)
        PortChecker.print_port_status(args.ports)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
