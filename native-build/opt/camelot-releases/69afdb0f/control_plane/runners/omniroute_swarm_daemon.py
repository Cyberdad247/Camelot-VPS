import time
import sys
import os

# Add routers directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'routers'))
from round_robin_router import FallbackRouter

def run_endless_mode():
    print("[DAEMON] Initializing OmniRoute Swarm Daemon in Endless Mode...")
    
    # Locate OmniRoute Master Config
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '03_VAULT', 'training', 'configs', 'config', 'omniroute.json'))
    
    # Initialize the Bio-Kinetic Fallback Router
    router = FallbackRouter(config_path)
    
    print("[DAEMON] Token Buckets online. Connecting to Mesh...")
    
    # Endless execution loop
    task_counter = 0
    while True:
        endpoint = router.get_available_endpoint()
        
        if endpoint:
            provider = endpoint['provider']
            print(f"[DAEMON] Task {task_counter}: Routed to {provider} successfully. Tokens consumed.")
            task_counter += 1
            time.sleep(0.1) # Simulate high-velocity task execution
        else:
            print("[DAEMON] ALERT: All API Token Buckets exhausted. Entering hibernation to prevent HTTP 429 bans...")
            print("[DAEMON] Awaiting quota reset...")
            time.sleep(5) # Hibernation simulation
            break # Break for simulation purposes so daemon doesn't hang forever

if __name__ == "__main__":
    run_endless_mode()
