// SPDX-License-Identifier: MIT
// Channel Relay & Load Balancing Adapter for Camelot-OS
// Assimilated from new-api channel pooling, health probe, and zero-cost failover algorithms.

package main

import (
	"context"
	"errors"
	"fmt"
	"math/rand"
	"net/http"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// Channel status codes matching new-api conventions
const (
	ChannelStatusEnabled          = 1
	ChannelStatusManuallyDisabled = 2
	ChannelStatusAutoDisabled     = 3
)

// Cost tiers for zero-cost routing and BitRouter integration
const (
	CostTierZeroCost = "zero_cost"
	CostTierFree     = "free"
	CostTierPaid     = "paid"
	CostTierPremium  = "premium"
)

// Channel represents an upstream LLM provider channel
type Channel struct {
	ID                   string   `json:"id"`
	Name                 string   `json:"name"`
	Type                 string   `json:"type"` // "openai", "claude", "gemini", "ollama", "custom"
	BaseURL              string   `json:"base_url"`
	Keys                 []string `json:"keys"`
	KeyIndex             uint64   `json:"key_index"`
	Group                string   `json:"group"` // "default", "vip", "zero_cost", "local"
	Models               []string `json:"models"`
	Priority             int      `json:"priority"` // Higher priority attempted first
	Weight               int      `json:"weight"`   // Load balancing weight within same priority bucket
	Status               int      `json:"status"`   // ChannelStatusEnabled, etc.
	CostTier             string   `json:"cost_tier"`
	CostPerToken         float64  `json:"cost_per_token"`
	LatencyMs            int64    `json:"latency_ms"`
	HealthScore          float64  `json:"health_score"` // 0.0 to 1.0
	AutoBan              bool     `json:"auto_ban"`
	AutoEnable           bool     `json:"auto_enable"`
	ConsecutiveFailures  int      `json:"consecutive_failures"`
	ConsecutiveSuccesses int      `json:"consecutive_successes"`
	TotalRequests        int64    `json:"total_requests"`
	TotalSuccesses       int64    `json:"total_successes"`
	TotalFailures        int64    `json:"total_failures"`
	LastProbeAt          int64    `json:"last_probe_at"`
	LastFailureReason    string   `json:"last_failure_reason"`

	mu sync.RWMutex
}

// GetNextKey implements round-robin multi-key rotation
func (c *Channel) GetNextKey() string {
	c.mu.RLock()
	if len(c.Keys) == 0 {
		c.mu.RUnlock()
		return ""
	}
	if len(c.Keys) == 1 {
		k := c.Keys[0]
		c.mu.RUnlock()
		return k
	}
	c.mu.RUnlock()

	idx := atomic.AddUint64(&c.KeyIndex, 1) - 1
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.Keys[idx%uint64(len(c.Keys))]
}

// IsAvailable checks if the channel is enabled and healthy
func (c *Channel) IsAvailable() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.Status == ChannelStatusEnabled
}

// IsZeroCost checks if the channel operates with zero paid token spend
func (c *Channel) IsZeroCost() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.CostTier == CostTierZeroCost || c.CostTier == CostTierFree || c.CostPerToken == 0 || strings.Contains(strings.ToLower(c.Group), "zero_cost") || strings.Contains(strings.ToLower(c.Group), "local")
}

// RecordSuccess updates latency, health score, and clears consecutive failures
func (c *Channel) RecordSuccess(latency time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.TotalRequests++
	c.TotalSuccesses++
	c.ConsecutiveSuccesses++
	c.ConsecutiveFailures = 0
	c.LatencyMs = latency.Milliseconds()

	// Rolling health score calculation (exponential moving average)
	if c.HealthScore == 0 {
		c.HealthScore = 1.0
	} else {
		c.HealthScore = 0.85*c.HealthScore + 0.15*1.0
	}
}

// RecordFailure updates failure stats, degrades health score, and returns whether auto-ban should trigger
func (c *Channel) RecordFailure(reason string) bool {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.TotalRequests++
	c.TotalFailures++
	c.ConsecutiveFailures++
	c.ConsecutiveSuccesses = 0
	c.LastFailureReason = reason
	c.HealthScore = 0.85 * c.HealthScore // decay health score

	if c.AutoBan {
		c.Status = ChannelStatusAutoDisabled
		return true
	}
	return false
}

// ChannelPool manages thread-safe storage, indexed model querying, and load-balancing selection
type ChannelPool struct {
	mu          sync.RWMutex
	channels    map[string]*Channel
	groupModels map[string]map[string][]string // group -> model -> []channelID
	rnd         *rand.Rand
	rndMu       sync.Mutex
}

// NewChannelPool initializes a new channel pool
func NewChannelPool() *ChannelPool {
	return &ChannelPool{
		channels:    make(map[string]*Channel),
		groupModels: make(map[string]map[string][]string),
		rnd:         rand.New(rand.NewSource(time.Now().UnixNano())),
	}
}

// RegisterChannel adds or updates a channel in the pool and updates routing indices
func (p *ChannelPool) RegisterChannel(ch *Channel) {
	if ch == nil || ch.ID == "" {
		return
	}
	p.mu.Lock()
	defer p.mu.Unlock()

	p.channels[ch.ID] = ch
	p.rebuildIndexLocked()
}

// RemoveChannel removes a channel from the pool
func (p *ChannelPool) RemoveChannel(id string) {
	p.mu.Lock()
	defer p.mu.Unlock()

	delete(p.channels, id)
	p.rebuildIndexLocked()
}

// UpdateChannelStatus changes channel status (e.g. Enabled, AutoDisabled)
func (p *ChannelPool) UpdateChannelStatus(id string, status int) {
	p.mu.Lock()
	defer p.mu.Unlock()

	if ch, ok := p.channels[id]; ok {
		ch.mu.Lock()
		ch.Status = status
		ch.mu.Unlock()
	}
	p.rebuildIndexLocked()
}

// GetChannel retrieves a channel by ID
func (p *ChannelPool) GetChannel(id string) (*Channel, bool) {
	p.mu.RLock()
	defer p.mu.RUnlock()
	ch, ok := p.channels[id]
	return ch, ok
}

// GetAllChannels returns all registered channels
func (p *ChannelPool) GetAllChannels() []*Channel {
	p.mu.RLock()
	defer p.mu.RUnlock()

	res := make([]*Channel, 0, len(p.channels))
	for _, ch := range p.channels {
		res = append(res, ch)
	}
	return res
}

func (p *ChannelPool) rebuildIndexLocked() {
	newIndex := make(map[string]map[string][]string)

	for id, ch := range p.channels {
		ch.mu.RLock()
		if ch.Status != ChannelStatusEnabled {
			ch.mu.RUnlock()
			continue
		}
		groups := strings.Split(ch.Group, ",")
		models := ch.Models
		ch.mu.RUnlock()

		for _, g := range groups {
			group := strings.TrimSpace(g)
			if group == "" {
				group = "default"
			}
			if _, ok := newIndex[group]; !ok {
				newIndex[group] = make(map[string][]string)
			}
			for _, m := range models {
				model := strings.TrimSpace(m)
				if model == "" {
					continue
				}
				newIndex[group][model] = append(newIndex[group][model], id)
			}
		}
	}

	p.groupModels = newIndex
}

// SelectChannel assimilates new-api's multi-tier priority & smoothed weighted random algorithm:
// 1. Gathers enabled candidate channels matching group and model (with alias/wildcard matching).
// 2. Extracts unique priorities sorted descending.
// 3. Selects priority bucket at index `retry` (handling cross-priority failover).
// 4. Performs Smoothed Weighted Random Selection among candidates in that priority bucket.
func (p *ChannelPool) SelectChannel(group string, model string, retry int, requestPath string) (*Channel, error) {
	p.mu.RLock()
	defer p.mu.RUnlock()

	if len(p.channels) == 0 {
		return nil, errors.New("channel pool is empty")
	}

	// 1. Gather matching candidate channel IDs
	var candidateIDs []string

	// Direct group match
	if modelMap, ok := p.groupModels[group]; ok {
		if ids, ok := modelMap[model]; ok {
			candidateIDs = append(candidateIDs, ids...)
		}
		// Wildcard match
		if ids, ok := modelMap["*"]; ok {
			candidateIDs = append(candidateIDs, ids...)
		}
	}

	// Fallback to "default" or "auto" group if no specific matches
	if len(candidateIDs) == 0 && group != "default" && group != "auto" {
		if modelMap, ok := p.groupModels["default"]; ok {
			if ids, ok := modelMap[model]; ok {
				candidateIDs = append(candidateIDs, ids...)
			}
		}
	}

	// If auto group mode, check all groups
	if len(candidateIDs) == 0 && group == "auto" {
		for _, modelMap := range p.groupModels {
			if ids, ok := modelMap[model]; ok {
				candidateIDs = append(candidateIDs, ids...)
			}
		}
	}

	// Deduplicate candidates
	seen := make(map[string]bool)
	uniqueIDs := make([]string, 0, len(candidateIDs))
	for _, id := range candidateIDs {
		if !seen[id] {
			seen[id] = true
			uniqueIDs = append(uniqueIDs, id)
		}
	}

	if len(uniqueIDs) == 0 {
		return nil, fmt.Errorf("no enabled channels found for group=%s model=%s", group, model)
	}

	// 2. Fetch candidate Channel pointers and filter available
	candidates := make([]*Channel, 0, len(uniqueIDs))
	for _, id := range uniqueIDs {
		if ch, ok := p.channels[id]; ok && ch.IsAvailable() {
			candidates = append(candidates, ch)
		}
	}

	if len(candidates) == 0 {
		return nil, fmt.Errorf("no available channels for group=%s model=%s after availability filter", group, model)
	}

	// 3. Extract unique priorities sorted in descending order
	priorityMap := make(map[int]bool)
	for _, ch := range candidates {
		priorityMap[ch.Priority] = true
	}
	sortedPriorities := make([]int, 0, len(priorityMap))
	for pr := range priorityMap {
		sortedPriorities = append(sortedPriorities, pr)
	}
	sort.Sort(sort.Reverse(sort.IntSlice(sortedPriorities)))

	// If retry index exceeds available priorities, clamp to lowest available priority
	targetPriorityIdx := retry
	if targetPriorityIdx >= len(sortedPriorities) {
		targetPriorityIdx = len(sortedPriorities) - 1
	}
	targetPriority := sortedPriorities[targetPriorityIdx]

	// 4. Collect channels in target priority bucket
	targetBucket := make([]*Channel, 0)
	sumWeight := 0
	for _, ch := range candidates {
		if ch.Priority == targetPriority {
			w := ch.Weight
			if w < 0 {
				w = 0
			}
			sumWeight += w
			targetBucket = append(targetBucket, ch)
		}
	}

	if len(targetBucket) == 0 {
		return nil, fmt.Errorf("no channels found for priority=%d", targetPriority)
	}

	if len(targetBucket) == 1 {
		return targetBucket[0], nil
	}

	// 5. Smoothed Weighted Random Selection (assimilated from new-api channel_cache.go)
	smoothingFactor := 1
	smoothingAdjustment := 0

	if sumWeight == 0 {
		// When all channels have weight 0, each channel gets equal baseline weight 100
		sumWeight = len(targetBucket) * 100
		smoothingAdjustment = 100
	} else if sumWeight/len(targetBucket) < 10 {
		// When average weight is small (<10), scale by smoothingFactor 100
		smoothingFactor = 100
	}

	totalWeight := sumWeight * smoothingFactor

	p.rndMu.Lock()
	randomWeight := p.rnd.Intn(totalWeight)
	p.rndMu.Unlock()

	for _, ch := range targetBucket {
		w := ch.Weight
		if w < 0 {
			w = 0
		}
		randomWeight -= (w*smoothingFactor + smoothingAdjustment)
		if randomWeight < 0 {
			return ch, nil
		}
	}

	return targetBucket[0], nil
}

// SelectZeroCostChannel selects candidates strictly from zero-cost/local tiers
func (p *ChannelPool) SelectZeroCostChannel(group string, model string, retry int) (*Channel, error) {
	p.mu.RLock()
	defer p.mu.RUnlock()

	var zeroCostCandidates []*Channel
	for _, ch := range p.channels {
		if ch.IsAvailable() && ch.IsZeroCost() {
			// Check if model supported
			matched := false
			for _, m := range ch.Models {
				if m == model || m == "*" {
					matched = true
					break
				}
			}
			if matched {
				zeroCostCandidates = append(zeroCostCandidates, ch)
			}
		}
	}

	if len(zeroCostCandidates) == 0 {
		return nil, fmt.Errorf("no zero-cost channels available for model=%s", model)
	}

	// Sort by priority descending
	sort.Slice(zeroCostCandidates, func(i, j int) bool {
		return zeroCostCandidates[i].Priority > zeroCostCandidates[j].Priority
	})

	idx := retry
	if idx >= len(zeroCostCandidates) {
		idx = idx % len(zeroCostCandidates)
	}
	return zeroCostCandidates[idx], nil
}

// HealthProbeEngine manages active and passive probing, auto-ban, and auto-enable
type HealthProbeEngine struct {
	pool       *ChannelPool
	httpClient *http.Client
}

// NewHealthProbeEngine creates a new health probe manager
func NewHealthProbeEngine(pool *ChannelPool) *HealthProbeEngine {
	return &HealthProbeEngine{
		pool: pool,
		httpClient: &http.Client{
			Timeout: 5 * time.Second,
		},
	}
}

// ShouldDisableChannel determines if an error is critical enough to auto-ban the channel
func (h *HealthProbeEngine) ShouldDisableChannel(statusCode int, err error) bool {
	if statusCode == http.StatusUnauthorized || statusCode == http.StatusForbidden {
		return true // Invalid API Key or Permissions
	}
	if statusCode == http.StatusTooManyRequests {
		return true // Rate limited / Quota exhausted
	}
	if statusCode >= 500 && statusCode <= 504 {
		return true // Upstream outage
	}
	if err != nil {
		msg := strings.ToLower(err.Error())
		if strings.Contains(msg, "insufficient_quota") ||
			strings.Contains(msg, "quota_exceeded") ||
			strings.Contains(msg, "invalid_api_key") ||
			strings.Contains(msg, "connection refused") ||
			strings.Contains(msg, "context deadline exceeded") ||
			strings.Contains(msg, "timeout") {
			return true
		}
	}
	return false
}

// ShouldRetry determines whether a failed request should be retried on another channel or key
func (h *HealthProbeEngine) ShouldRetry(statusCode int, err error, remainingRetries int) bool {
	if remainingRetries <= 0 {
		return false
	}
	// Do not retry on client-side errors (400 Bad Request, 404 Not Found due to bad user input)
	if statusCode == http.StatusBadRequest || statusCode == http.StatusUnprocessableEntity {
		return false
	}
	if statusCode >= 200 && statusCode < 300 {
		return false
	}
	// Retry on 401 (rotate key/channel), 403, 429, 5xx, or network errors
	return true
}

// AutoBan marks a channel as auto-disabled and triggers notification logging
func (h *HealthProbeEngine) AutoBan(ch *Channel, reason string) {
	if ch == nil {
		return
	}
	banned := ch.RecordFailure(reason)
	if banned {
		h.pool.UpdateChannelStatus(ch.ID, ChannelStatusAutoDisabled)
	}
}

// AutoEnable checks if an auto-disabled channel can be recovered
func (h *HealthProbeEngine) AutoEnable(ch *Channel) {
	if ch == nil {
		return
	}
	ch.mu.Lock()
	if ch.Status == ChannelStatusAutoDisabled && ch.AutoEnable {
		ch.Status = ChannelStatusEnabled
		ch.ConsecutiveFailures = 0
		ch.ConsecutiveSuccesses = 0
		ch.HealthScore = 0.5
	}
	ch.mu.Unlock()
	h.pool.UpdateChannelStatus(ch.ID, ChannelStatusEnabled)
}

// RelayRequest contains metadata for a channel relay operation
type RelayRequest struct {
	Group         string                 `json:"group"`
	Model         string                 `json:"model"`
	Prompt        string                 `json:"prompt"`
	ContextSize   int                    `json:"context_size"`
	ZeroCostOnly  bool                   `json:"zero_cost_only"`
	SpendCap      float64                `json:"spend_cap"`
	MaxRetries    int                    `json:"max_retries"`
	RequestPath   string                 `json:"request_path"`
	Metadata      map[string]interface{} `json:"metadata"`
}

// RelayResponse contains the result of a channel relay operation
type RelayResponse struct {
	ChannelID     string                 `json:"channel_id"`
	ChannelName   string                 `json:"channel_name"`
	UsedKey       string                 `json:"used_key"`
	CostTier      string                 `json:"cost_tier"`
	ZeroCost      bool                   `json:"zero_cost"`
	RetriesUsed   int                    `json:"retries_used"`
	FailoverTrail []string               `json:"failover_trail"`
	LatencyMs     int64                  `json:"latency_ms"`
	ResultPayload string                 `json:"result_payload"`
	Success       bool                   `json:"success"`
	Error         string                 `json:"error,omitempty"`
}

// ChannelExecutorFunc is the execution function invoked for a selected channel
type ChannelExecutorFunc func(ctx context.Context, ch *Channel, key string) (string, int, error)

// ChannelRelay coordinates channel pooling, health probing, zero-cost optimization, and failover
type ChannelRelay struct {
	pool   *ChannelPool
	probe  *HealthProbeEngine
	maxTry int
}

// NewChannelRelay constructs the channel relay engine
func NewChannelRelay(pool *ChannelPool, probe *HealthProbeEngine) *ChannelRelay {
	if pool == nil {
		pool = NewChannelPool()
	}
	if probe == nil {
		probe = NewHealthProbeEngine(pool)
	}
	return &ChannelRelay{
		pool:   pool,
		probe:  probe,
		maxTry: 3,
	}
}

// ExecuteRelay executes a request across the channel pool with zero-cost prioritization and multi-tier failover
func (r *ChannelRelay) ExecuteRelay(ctx context.Context, req *RelayRequest, executor ChannelExecutorFunc) (*RelayResponse, error) {
	if req == nil {
		return nil, errors.New("relay request cannot be nil")
	}

	maxRetries := req.MaxRetries
	if maxRetries <= 0 {
		maxRetries = r.maxTry
	}

	trail := make([]string, 0)
	var lastErr error

	for retry := 0; retry <= maxRetries; retry++ {
		// Select channel: if ZeroCostOnly or spendCap == 0, prioritize zero-cost channel
		var ch *Channel
		var selectErr error

		if req.ZeroCostOnly || (req.SpendCap == 0 && req.Group == CostTierZeroCost) {
			ch, selectErr = r.pool.SelectZeroCostChannel(req.Group, req.Model, retry)
		} else {
			ch, selectErr = r.pool.SelectChannel(req.Group, req.Model, retry, req.RequestPath)
		}

		if selectErr != nil {
			// If zero-cost pool failed but not strictly forced, fallback to general pool
			if req.ZeroCostOnly {
				return &RelayResponse{
					Success:       false,
					FailoverTrail: trail,
					Error:         fmt.Sprintf("zero-cost channel selection exhausted: %v", selectErr),
				}, selectErr
			}
			ch, selectErr = r.pool.SelectChannel(req.Group, req.Model, retry, req.RequestPath)
			if selectErr != nil {
				lastErr = selectErr
				break
			}
		}

		key := ch.GetNextKey()
		trail = append(trail, fmt.Sprintf("%s(#%s,p=%d,w=%d)", ch.Name, ch.ID, ch.Priority, ch.Weight))

		start := time.Now()
		payload, statusCode, err := executor(ctx, ch, key)
		latency := time.Since(start)

		if err == nil && statusCode >= 200 && statusCode < 300 {
			// Success! Record metrics and return
			ch.RecordSuccess(latency)
			return &RelayResponse{
				ChannelID:     ch.ID,
				ChannelName:   ch.Name,
				UsedKey:       key,
				CostTier:      ch.CostTier,
				ZeroCost:      ch.IsZeroCost(),
				RetriesUsed:   retry,
				FailoverTrail: trail,
				LatencyMs:     latency.Milliseconds(),
				ResultPayload: payload,
				Success:       true,
			}, nil
		}

		// Handle error
		errMsg := "unknown error"
		if err != nil {
			errMsg = err.Error()
		} else {
			errMsg = fmt.Sprintf("http status %d", statusCode)
		}
		lastErr = fmt.Errorf("channel %s failed: %s (status %d)", ch.Name, errMsg, statusCode)

		// Check if channel should be auto-banned
		if r.probe.ShouldDisableChannel(statusCode, err) {
			r.probe.AutoBan(ch, errMsg)
		} else {
			ch.RecordFailure(errMsg)
		}

		// Check if we should retry
		remaining := maxRetries - retry
		if !r.probe.ShouldRetry(statusCode, err, remaining) {
			break
		}
	}

	return &RelayResponse{
		Success:       false,
		RetriesUsed:   len(trail) - 1,
		FailoverTrail: trail,
		Error:         lastErr.Error(),
	}, lastErr
}
