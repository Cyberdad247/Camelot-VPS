// SPDX-License-Identifier: MIT

package main

import (
	"context"
	"strings"
	"testing"
	"time"
)

func TestMemoKeyStable(t *testing.T) {
	a := MemoKey("route this intent")
	b := MemoKey("route this intent")
	if a != b {
		t.Fatalf("MemoKey unstable: %q != %q", a, b)
	}
	if !strings.HasPrefix(a, MemoPrefix) {
		t.Fatalf("MemoKey missing prefix: %q", a)
	}
	if MemoKey("other prompt") == a {
		t.Fatal("MemoKey collision on distinct prompts")
	}
	if len(a) != len(MemoPrefix)+64 {
		t.Fatalf("MemoKey wrong length: %q", a)
	}
}

func TestMemoCacheRoundTrip(t *testing.T) {
	ctx := context.Background()
	m := NewMemoCache(NewMapKV(), DefaultMemoTTL)

	if _, hit := m.Lookup(ctx, "q"); hit {
		t.Fatal("empty cache must miss")
	}
	if err := m.StoreMemo(ctx, "q", "synthesis"); err != nil {
		t.Fatalf("StoreMemo: %v", err)
	}
	v, hit := m.Lookup(ctx, "q")
	if !hit || v != "synthesis" {
		t.Fatalf("expected hit with synthesis, got %q hit=%v", v, hit)
	}
	if _, hit := m.Lookup(ctx, "other"); hit {
		t.Fatal("distinct prompt must miss")
	}
}

func TestMemoCacheSkipsEmpty(t *testing.T) {
	ctx := context.Background()
	m := NewMemoCache(NewMapKV(), time.Minute)
	if err := m.StoreMemo(ctx, "q", ""); err != nil {
		t.Fatalf("StoreMemo empty: %v", err)
	}
	if _, hit := m.Lookup(ctx, "q"); hit {
		t.Fatal("empty synthesis must not be cached")
	}
}

func TestServerMemoWiredToRedis(t *testing.T) {
	s := NewBifrostServer()
	if s.memo == nil {
		t.Fatal("BifrostServer.memo must be constructed (Redis-backed production wiring)")
	}
	stats := s.MemoStats()
	if stats["prefix"] != MemoPrefix {
		t.Fatalf("memo prefix = %v, want %q", stats["prefix"], MemoPrefix)
	}
	if stats["ttl_seconds"] != int(DefaultMemoTTL.Seconds()) {
		t.Fatalf("memo ttl = %v, want %v", stats["ttl_seconds"], int(DefaultMemoTTL.Seconds()))
	}
	if _, ok := stats["redis_ok"].(bool); !ok {
		t.Fatalf("memo stats must report redis_ok bool, got %v", stats)
	}
}
