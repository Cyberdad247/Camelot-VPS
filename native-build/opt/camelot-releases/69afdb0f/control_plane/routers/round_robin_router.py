import json
import os
from token_bucket import TokenBucket

class FallbackRouter:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.nodes = self.config.get("nodes", [])
        self.buckets = {}
        
        # Initialize Token Buckets based on provider limits
        for node in self.nodes:
            if node["provider"] == "openrouter":
                # Free tier max 50 requests. 0 fill rate means it relies on daily external reset
                self.buckets[node["provider"]] = TokenBucket(capacity=50, fill_rate=0)
            elif node["provider"] == "chatanywhere":
                # Assume massive limit for ChatAnywhere fallback
                self.buckets[node["provider"]] = TokenBucket(capacity=1000, fill_rate=1.0)
            else:
                self.buckets[node["provider"]] = TokenBucket(capacity=100, fill_rate=0.1)
                
        self.current_idx = 0

    def get_available_endpoint(self):
        attempts = 0
        while attempts < len(self.nodes):
            node = self.nodes[self.current_idx]
            provider = node["provider"]
            
            # Check if this provider has tokens
            if self.buckets[provider].consume(1):
                # If round-robin strategy, rotate for next request. If cascade, stay on this one until dead.
                if node.get("strategy") == "round_robin":
                    self.current_idx = (self.current_idx + 1) % len(self.nodes)
                return node
            
            # Exhausted, try next provider in mesh
            self.current_idx = (self.current_idx + 1) % len(self.nodes)
            attempts += 1
        
        # All providers exhausted (Endless Mode trigger: Sleep required)
        return None
