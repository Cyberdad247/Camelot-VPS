// SPDX-License-Identifier: MIT

// CloudBrain memo lane — Redis-backed synthesis cache.
//
// Why: CloudBrain synthesis (NotebookLM round-trip) costs seconds and tokens
// per prompt. Repeated prompts (router retries, dashboard polls, swarm fan-out)
// hit this memo first: key = sha256(prompt), TTL-bounded, prefix-isolated.
// Same role Redis Agent Memory plays for CloudBrain recall: speed via RAM,
// token reduction via never re-synthesizing the same prompt.
//
// Wiring: MemoCache wraps any KV; production passes the shared go-redis
// client (see NewRedisKV), tests pass MapKV. No new dependencies.
package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"time"

	"github.com/go-redis/redis/v8"
)

// MemoPrefix isolates synthesis memos from BullMQ queue keys.
const MemoPrefix = "cb:memo:"

// DefaultMemoTTL bounds staleness: syntheses refresh at most this often.
const DefaultMemoTTL = 10 * time.Minute

// KV is the minimal store surface the memo needs (redis-backed or in-memory).
type KV interface {
	Get(ctx context.Context, key string) (string, error)
	Set(ctx context.Context, key string, value string, ttl time.Duration) error
}

// RedisKV adapts *redis.Client to KV.
type RedisKV struct {
	client *redis.Client
}

// NewRedisKV wraps an existing client (e.g. BifrostServer.redisClient).
func NewRedisKV(client *redis.Client) *RedisKV {
	return &RedisKV{client: client}
}

func (k *RedisKV) Get(ctx context.Context, key string) (string, error) {
	return k.client.Get(ctx, key).Result()
}

func (k *RedisKV) Set(ctx context.Context, key string, value string, ttl time.Duration) error {
	return k.client.Set(ctx, key, value, ttl).Err()
}

// MapKV is an in-memory KV for tests and offline dev.
type MapKV struct {
	items map[string]string
}

// NewMapKV returns an empty in-memory store.
func NewMapKV() *MapKV {
	return &MapKV{items: make(map[string]string)}
}

func (k *MapKV) Get(_ context.Context, key string) (string, error) {
	v, ok := k.items[key]
	if !ok {
		return "", redis.Nil
	}
	return v, nil
}

func (k *MapKV) Set(_ context.Context, key string, value string, _ time.Duration) error {
	k.items[key] = value
	return nil
}

// MemoKey derives the stable cache key for a synthesis prompt.
func MemoKey(prompt string) string {
	sum := sha256.Sum256([]byte(prompt))
	return MemoPrefix + hex.EncodeToString(sum[:])
}

// MemoCache caches expensive syntheses behind MemoKey.
type MemoCache struct {
	store KV
	ttl   time.Duration
}

// NewMemoCache builds a cache over store with the given TTL.
func NewMemoCache(store KV, ttl time.Duration) *MemoCache {
	return &MemoCache{store: store, ttl: ttl}
}

// Lookup returns the cached synthesis and true on hit.
func (m *MemoCache) Lookup(ctx context.Context, prompt string) (string, bool) {
	v, err := m.store.Get(ctx, MemoKey(prompt))
	if err != nil || v == "" {
		return "", false
	}
	return v, true
}

// StoreMemo records a synthesis for future identical prompts.
func (m *MemoCache) StoreMemo(ctx context.Context, prompt, synthesis string) error {
	if synthesis == "" {
		return nil
	}
	return m.store.Set(ctx, MemoKey(prompt), synthesis, m.ttl)
}
