// SPDX-License-Identifier: MIT

package main

import (
	"context"
	"errors"
	"net/http"
	"testing"
)

func TestMultiKeyRotation(t *testing.T) {
	ch := &Channel{
		ID:       "ch_test_keys",
		Name:     "Test Multi-Key",
		Keys:     []string{"sk-key-1", "sk-key-2", "sk-key-3"},
		Status:   ChannelStatusEnabled,
		Priority: 10,
		Weight:   100,
	}

	keysSeen := make(map[string]int)
	for i := 0; i < 9; i++ {
		key := ch.GetNextKey()
		keysSeen[key]++
	}

	if keysSeen["sk-key-1"] != 3 || keysSeen["sk-key-2"] != 3 || keysSeen["sk-key-3"] != 3 {
		t.Fatalf("expected each key to be rotated evenly 3 times, got: %+v", keysSeen)
	}
}

func TestPriorityAndSmoothedWeightSelection(t *testing.T) {
	pool := NewChannelPool()

	// Register 2 high-priority channels (Priority 10) with different weights
	ch1 := &Channel{
		ID:       "ch_p10_w80",
		Name:     "High Priority Heavy",
		Group:    "default",
		Models:   []string{"gpt-4o"},
		Priority: 10,
		Weight:   80,
		Status:   ChannelStatusEnabled,
	}
	ch2 := &Channel{
		ID:       "ch_p10_w20",
		Name:     "High Priority Light",
		Group:    "default",
		Models:   []string{"gpt-4o"},
		Priority: 10,
		Weight:   20,
		Status:   ChannelStatusEnabled,
	}
	// Register 1 low-priority fallback channel (Priority 5)
	ch3 := &Channel{
		ID:       "ch_p5",
		Name:     "Low Priority Fallback",
		Group:    "default",
		Models:   []string{"gpt-4o"},
		Priority: 5,
		Weight:   100,
		Status:   ChannelStatusEnabled,
	}

	pool.RegisterChannel(ch1)
	pool.RegisterChannel(ch2)
	pool.RegisterChannel(ch3)

	// Retry 0: must pick from Priority 10 bucket (ch1 or ch2)
	counts := make(map[string]int)
	for i := 0; i < 1000; i++ {
		selected, err := pool.SelectChannel("default", "gpt-4o", 0, "")
		if err != nil {
			t.Fatalf("unexpected select error: %v", err)
		}
		counts[selected.ID]++
	}

	if counts["ch_p5"] > 0 {
		t.Fatalf("expected 0 selections for ch_p5 on retry 0, got %d", counts["ch_p5"])
	}
	if counts["ch_p10_w80"] < 600 || counts["ch_p10_w20"] < 100 {
		t.Fatalf("expected weighted distribution favoring ch1 over ch2, got: %+v", counts)
	}

	// Retry 1: must fallback to Priority 5 bucket (ch3)
	fallbackSelected, err := pool.SelectChannel("default", "gpt-4o", 1, "")
	if err != nil {
		t.Fatalf("unexpected fallback select error: %v", err)
	}
	if fallbackSelected.ID != "ch_p5" {
		t.Fatalf("expected ch_p5 on retry 1, got %s", fallbackSelected.ID)
	}
}

func TestZeroCostFailover(t *testing.T) {
	pool := NewChannelPool()
	probe := NewHealthProbeEngine(pool)
	relay := NewChannelRelay(pool, probe)

	// Primary zero-cost channel: e.g. Local Ollama (Priority 10, CostTier=zero_cost)
	chLocalPrimary := &Channel{
		ID:           "ch_ollama_primary",
		Name:         "Ollama Primary (Zero-Cost)",
		Type:         "ollama",
		Group:        "zero_cost",
		Models:       []string{"llama3", "gpt-4o"},
		Priority:     10,
		Weight:       100,
		Status:       ChannelStatusEnabled,
		CostTier:     CostTierZeroCost,
		CostPerToken: 0,
		AutoBan:      true,
	}

	// Secondary zero-cost channel: e.g. Gemini Free Tier (Priority 8, CostTier=zero_cost)
	chGeminiSecondary := &Channel{
		ID:           "ch_gemini_free",
		Name:         "Gemini Free Tier (Zero-Cost)",
		Type:         "gemini",
		Group:        "zero_cost",
		Models:       []string{"llama3", "gpt-4o"},
		Priority:     8,
		Weight:       100,
		Status:       ChannelStatusEnabled,
		CostTier:     CostTierZeroCost,
		CostPerToken: 0,
		AutoBan:      true,
	}

	// Paid fallback channel (Priority 1, CostTier=paid)
	chPaid := &Channel{
		ID:           "ch_openai_paid",
		Name:         "OpenAI Commercial Paid",
		Type:         "openai",
		Group:        "default",
		Models:       []string{"llama3", "gpt-4o"},
		Priority:     1,
		Weight:       100,
		Status:       ChannelStatusEnabled,
		CostTier:     CostTierPaid,
		CostPerToken: 0.00002,
		AutoBan:      true,
	}

	pool.RegisterChannel(chLocalPrimary)
	pool.RegisterChannel(chGeminiSecondary)
	pool.RegisterChannel(chPaid)

	// Simulation: Primary Ollama fails with 503 Service Unavailable (outage / memory limit).
	// Relay should seamlessly failover to Gemini Free Tier (Zero-Cost), auto-ban chLocalPrimary, and succeed with zero cost.
	callCount := 0
	executor := func(ctx context.Context, ch *Channel, key string) (string, int, error) {
		callCount++
		if ch.ID == "ch_ollama_primary" {
			return "", http.StatusServiceUnavailable, errors.New("upstream service unavailable: 503")
		}
		if ch.ID == "ch_gemini_free" {
			return `{"response": "Zero-cost synthesis complete", "model": "gemini-flash"}`, http.StatusOK, nil
		}
		return "", http.StatusBadRequest, errors.New("unexpected channel called")
	}

	req := &RelayRequest{
		Group:        "zero_cost",
		Model:        "gpt-4o",
		Prompt:       "Analyze sovereign kernel memory",
		ZeroCostOnly: true,
		MaxRetries:   3,
	}

	resp, err := relay.ExecuteRelay(context.Background(), req, executor)
	if err != nil {
		t.Fatalf("relay failed unexpectedly: %v", err)
	}

	if !resp.Success {
		t.Fatalf("expected relay response to succeed, got error: %s", resp.Error)
	}
	if resp.ChannelID != "ch_gemini_free" {
		t.Fatalf("expected failover to ch_gemini_free, got %s", resp.ChannelID)
	}
	if !resp.ZeroCost {
		t.Fatalf("expected ZeroCost=true, got false")
	}
	if resp.RetriesUsed != 1 {
		t.Fatalf("expected exactly 1 failover retry, got %d", resp.RetriesUsed)
	}
	if len(resp.FailoverTrail) != 2 {
		t.Fatalf("expected failover trail of 2 items, got %+v", resp.FailoverTrail)
	}

	// Verify that failing primary channel was auto-banned
	if chLocalPrimary.Status != ChannelStatusAutoDisabled {
		t.Fatalf("expected primary channel to be AutoDisabled, got status=%d", chLocalPrimary.Status)
	}

	// Verify consecutive requests automatically bypass the banned channel without retry penalty
	req2 := &RelayRequest{
		Group:        "zero_cost",
		Model:        "gpt-4o",
		ZeroCostOnly: true,
		MaxRetries:   3,
	}
	resp2, err2 := relay.ExecuteRelay(context.Background(), req2, executor)
	if err2 != nil {
		t.Fatalf("second relay failed: %v", err2)
	}
	if resp2.RetriesUsed != 0 {
		t.Fatalf("expected 0 retries on second request due to active auto-ban, got %d", resp2.RetriesUsed)
	}
	if resp2.ChannelID != "ch_gemini_free" {
		t.Fatalf("expected direct routing to ch_gemini_free, got %s", resp2.ChannelID)
	}
}

func TestAutoEnableRecovery(t *testing.T) {
	pool := NewChannelPool()
	probe := NewHealthProbeEngine(pool)

	ch := &Channel{
		ID:         "ch_recoverable",
		Name:       "Recoverable Node",
		Status:     ChannelStatusAutoDisabled,
		AutoEnable: true,
	}
	pool.RegisterChannel(ch)

	if ch.IsAvailable() {
		t.Fatal("channel should not be available when auto-disabled")
	}

	probe.AutoEnable(ch)

	if !ch.IsAvailable() {
		t.Fatal("channel should be available after AutoEnable")
	}
	if ch.Status != ChannelStatusEnabled {
		t.Fatalf("expected ChannelStatusEnabled, got %d", ch.Status)
	}
}
