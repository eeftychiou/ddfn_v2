"""
Chaos engineering test runner.
Can be run manually or as part of CI/CD.
"""
import asyncio
import random
import argparse
from datetime import datetime
import aiohttp


class ChaosRunner:
    """Runs chaos experiments against a running DDFN cluster."""
    
    def __init__(self, broker_url: str, api_key: str = None):
        self.broker_url = broker_url
        self.api_key = api_key
        self.experiments = []
        self.results = []
    
    def add_experiment(self, name: str, func, probability: float = 0.1, description: str = ""):
        """Add a chaos experiment."""
        self.experiments.append({
            'name': name,
            'func': func,
            'probability': probability,
            'description': description
        })
    
    async def run(self, duration_minutes: int = 30):
        """Run chaos experiments for specified duration."""
        print(f"Starting chaos experiments for {duration_minutes} minutes")
        print(f"Broker URL: {self.broker_url}")
        print(f"Total experiments: {len(self.experiments)}")
        print("-" * 50)
        
        start_time = datetime.now()
        iteration = 0
        
        while (datetime.now() - start_time).seconds < duration_minutes * 60:
            iteration += 1
            print(f"\n[Iteration {iteration}] {datetime.now().strftime('%H:%M:%S')}")
            
            for exp in self.experiments:
                if random.random() < exp['probability']:
                    print(f"  Running: {exp['name']}")
                    if exp['description']:
                        print(f"    Description: {exp['description']}")
                    
                    try:
                        start = datetime.now()
                        await exp['func']()
                        duration = (datetime.now() - start).total_seconds()
                        
                        result = {
                            'experiment': exp['name'],
                            'timestamp': datetime.now().isoformat(),
                            'duration': duration,
                            'status': 'success'
                        }
                        self.results.append(result)
                        print(f"    ✓ Success ({duration:.2f}s)")
                        
                    except Exception as e:
                        result = {
                            'experiment': exp['name'],
                            'timestamp': datetime.now().isoformat(),
                            'error': str(e),
                            'status': 'failed'
                        }
                        self.results.append(result)
                        print(f"    ✗ Failed: {e}")
            
            # Wait between experiment cycles
            await asyncio.sleep(10)
        
        print("\n" + "=" * 50)
        print("Chaos experiments completed")
        self._print_summary()
    
    def _print_summary(self):
        """Print experiment results summary."""
        total = len(self.results)
        successful = sum(1 for r in self.results if r['status'] == 'success')
        failed = total - successful
        
        print(f"\nTotal experiments run: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        
        if failed > 0:
            print("\nFailed experiments:")
            for r in self.results:
                if r['status'] == 'failed':
                    print(f"  - {r['experiment']}: {r.get('error', 'Unknown error')}")


# Example chaos experiment functions
async def simulate_broker_restart():
    """Simulate broker restart."""
    print("    Action: Simulating broker restart...")
    # In real implementation, this would restart the broker container/process
    await asyncio.sleep(2)


async def simulate_network_delay():
    """Simulate network delay."""
    print("    Action: Simulating network delay...")
    # In real implementation, this would add latency to network
    await asyncio.sleep(1)


async def simulate_node_failure():
    """Simulate node failure."""
    print("    Action: Simulating node failure...")
    # In real implementation, this would stop a node
    await asyncio.sleep(1)


async def simulate_high_load():
    """Simulate high load."""
    print("    Action: Simulating high load...")
    # In real implementation, this would inject many messages
    await asyncio.sleep(0.5)


async def simulate_memory_pressure():
    """Simulate memory pressure."""
    print("    Action: Simulating memory pressure...")
    # In real implementation, this would consume memory
    await asyncio.sleep(1)


async def main():
    parser = argparse.ArgumentParser(description='Run chaos experiments against DDFN cluster')
    parser.add_argument('--broker', default='ws://127.0.0.1:8001/ws',
                        help='Broker WebSocket URL')
    parser.add_argument('--api-url', default='http://127.0.0.1:8001',
                        help='Broker HTTP API URL')
    parser.add_argument('--api-key', default=None,
                        help='API key for authentication')
    parser.add_argument('--duration', type=int, default=30,
                        help='Duration in minutes')
    parser.add_argument('--experiment', default=None,
                        help='Run specific experiment only')
    args = parser.parse_args()
    
    runner = ChaosRunner(args.broker, args.api_key)
    
    # Add available experiments
    runner.add_experiment(
        'broker_restart',
        simulate_broker_restart,
        probability=0.05,
        description='Restart broker and verify nodes reconnect'
    )
    
    runner.add_experiment(
        'network_delay',
        simulate_network_delay,
        probability=0.1,
        description='Add network latency and verify system stability'
    )
    
    runner.add_experiment(
        'node_failure',
        simulate_node_failure,
        probability=0.05,
        description='Stop a node and verify failover'
    )
    
    runner.add_experiment(
        'high_load',
        simulate_high_load,
        probability=0.15,
        description='Inject high message load'
    )
    
    runner.add_experiment(
        'memory_pressure',
        simulate_memory_pressure,
        probability=0.05,
        description='Simulate memory pressure'
    )
    
    try:
        await runner.run(args.duration)
    except KeyboardInterrupt:
        print("\n\nChaos experiments interrupted by user")
        runner._print_summary()


if __name__ == '__main__':
    asyncio.run(main())
