package cache

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

// Tier1HotCache manages sub-10ms volatile state, turn counters, distributed locks,
// and live execution receipts across Camelot-OS nodes.
// Falls back seamlessly to an in-memory thread-safe map if Redis is not running locally.
type Tier1HotCache struct {
	redisClient *redis.Client
	fallbackMem sync.Map
	useRedis    bool
}

// NewTier1HotCache initializes the hot cache connection.
func NewTier1HotCache(addr string) *Tier1HotCache {
	if addr == "" {
		addr = "127.0.0.1:6379"
	}

	rdb := redis.NewClient(&redis.Options{
		Addr:         addr,
		Password:     "", // Air-gapped / local loopback
		DB:           0,
		DialTimeout:  500 * time.Millisecond,
		ReadTimeout:  200 * time.Millisecond,
		WriteTimeout: 200 * time.Millisecond,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
	defer cancel()

	cache := &Tier1HotCache{
		redisClient: rdb,
		useRedis:    false,
	}

	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Printf("⚡ [TIER-1-CACHE] Redis daemon offline (%v). Active Substrate: In-Memory Go Hot Cache (Zero-Dependency Fallback).", err)
	} else {
		log.Println("🔥 [TIER-1-CACHE] Connected to Redis Hot Flash Cache on :6379 (Sub-10ms Latency Active).")
		cache.useRedis = true
	}

	return cache
}

// Set stores a key with an expiration window.
func (c *Tier1HotCache) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	if c.useRedis {
		return c.redisClient.Set(ctx, key, value, expiration).Err()
	}
	c.fallbackMem.Store(key, value)
	return nil
}

// Get retrieves a key from the hot cache.
func (c *Tier1HotCache) Get(ctx context.Context, key string) (string, error) {
	if c.useRedis {
		return c.redisClient.Get(ctx, key).Result()
	}
	val, ok := c.fallbackMem.Load(key)
	if !ok {
		return "", fmt.Errorf("key not found in hot cache")
	}
	return fmt.Sprintf("%v", val), nil
}

// AcquireTurnLock attempts to acquire a non-blocking lock for multi-agent turn coordination.
func (c *Tier1HotCache) AcquireTurnLock(ctx context.Context, lockKey string, ttl time.Duration) (bool, error) {
	if c.useRedis {
		return c.redisClient.SetNX(ctx, "lock:"+lockKey, "LOCKED", ttl).Result()
	}
	_, loaded := c.fallbackMem.LoadOrStore("lock:"+lockKey, "LOCKED")
	return !loaded, nil
}
