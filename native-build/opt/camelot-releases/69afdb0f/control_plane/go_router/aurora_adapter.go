// SPDX-License-Identifier: MIT
// Aurora Adapter & Simulated Tool-Call Engine for Camelot-OS Go Router
// Assimilated from aurora token pooling, session health checks, and <tool_call> emulation.

package main

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

// ── Account Types and Status Constants ──────────────────────────────────────

type AuroraAccountType int

const (
	AuroraAccountTypeNoAuth AuroraAccountType = iota // Anonymous UUID
	AuroraAccountTypeFree                            // ChatGPT Free Account
	AuroraAccountTypePUID                            // ChatGPT Paid/Pro Account (PUID)
)

func (t AuroraAccountType) String() string {
	switch t {
	case AuroraAccountTypeNoAuth:
		return "noauth"
	case AuroraAccountTypeFree:
		return "free"
	case AuroraAccountTypePUID:
		return "puid"
	default:
		return fmt.Sprintf("unknown(%d)", t)
	}
}

type AuroraAccountStatus int

const (
	AuroraStatusPending AuroraAccountStatus = iota
	AuroraStatusActive
	AuroraStatusExpired
	AuroraStatusRateLimited
	AuroraStatusDisabled
	AuroraStatusBanned
)

func (s AuroraAccountStatus) String() string {
	switch s {
	case AuroraStatusPending:
		return "pending"
	case AuroraStatusActive:
		return "active"
	case AuroraStatusExpired:
		return "expired"
	case AuroraStatusRateLimited:
		return "rate_limited"
	case AuroraStatusDisabled:
		return "disabled"
	case AuroraStatusBanned:
		return "banned"
	default:
		return fmt.Sprintf("unknown(%d)", s)
	}
}

// ── Fingerprint Profiles ────────────────────────────────────────────────────

type AuroraBrowserFingerprint struct {
	OaiDeviceID         string `json:"oai_device_id"`
	OaiSessionID        string `json:"oai_session_id"`
	UserAgent           string `json:"user_agent"`
	ScreenWidth         int    `json:"screen_width"`
	ScreenHeight        int    `json:"screen_height"`
	HardwareConcurrency int    `json:"hardware_concurrency"`
	Platform            string `json:"platform"`
	TLSProfileName      string `json:"tls_profile_name"`
}

type AuroraFingerprintProfile struct {
	Name                string
	TLSProfileName      string
	UserAgent           string
	ScreenWidth         int
	ScreenHeight        int
	HardwareConcurrency int
	Platform            string
}

var AuroraDefaultProfiles = []AuroraFingerprintProfile{
	{
		Name: "chrome_win_high", TLSProfileName: "chrome_146",
		UserAgent:           "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
		ScreenWidth: 2560, ScreenHeight: 1440, HardwareConcurrency: 16, Platform: "Win32",
	},
	{
		Name: "chrome_win_medium", TLSProfileName: "chrome_146",
		UserAgent:           "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
		ScreenWidth: 1920, ScreenHeight: 1080, HardwareConcurrency: 8, Platform: "Win32",
	},
	{
		Name: "chrome_win_low", TLSProfileName: "chrome_146",
		UserAgent:           "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
		ScreenWidth: 1366, ScreenHeight: 768, HardwareConcurrency: 4, Platform: "Win32",
	},
	{
		Name: "chrome_mac", TLSProfileName: "chrome_146",
		UserAgent:           "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
		ScreenWidth: 3024, ScreenHeight: 1964, HardwareConcurrency: 12, Platform: "MacIntel",
	},
	{
		Name: "safari_mac", TLSProfileName: "safari_16_0",
		UserAgent:           "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
		ScreenWidth: 3024, ScreenHeight: 1964, HardwareConcurrency: 10, Platform: "MacIntel",
	},
	{
		Name: "safari_iphone_pro", TLSProfileName: "safari_ios_18_5",
		UserAgent:           "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
		ScreenWidth: 393, ScreenHeight: 852, HardwareConcurrency: 6, Platform: "iPhone",
	},
}

// ── Aurora Account Model ────────────────────────────────────────────────────

type AuroraAccount struct {
	ID               string                   `json:"id"`
	Type             AuroraAccountType        `json:"type"`
	Token            string                   `json:"token"`
	RefreshToken     string                   `json:"refresh_token,omitempty"`
	SessionToken     string                   `json:"session_token,omitempty"`
	IsTemporary      bool                     `json:"is_temporary"`
	PUID             string                   `json:"puid,omitempty"`
	TeamUserID       string                   `json:"team_user_id,omitempty"`
	ChatGPTAccountID string                   `json:"chatgpt_account_id,omitempty"`
	Proxy            string                   `json:"proxy,omitempty"`
	Fingerprint      AuroraBrowserFingerprint `json:"fingerprint"`
	Status           AuroraAccountStatus      `json:"status"`
	ExpiresAt        time.Time                `json:"expires_at"`
	TotalCalls       int64                    `json:"total_calls"`
	FailedCalls      int64                    `json:"failed_calls"`
	LastUsed         time.Time                `json:"last_used"`
	LastChecked      time.Time                `json:"last_checked"`
	CreatedAt        time.Time                `json:"created_at"`

	mu sync.RWMutex
}

func generateUUID() string {
	var b [16]byte
	_, _ = rand.Read(b[:])
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:])
}

func NewAuroraAccount(id string, acctType AuroraAccountType, token string) *AuroraAccount {
	if id == "" {
		id = generateUUID()
	}
	now := time.Now()
	return &AuroraAccount{
		ID:        id,
		Type:      acctType,
		Token:     token,
		Status:    AuroraStatusPending,
		CreatedAt: now,
		LastUsed:  now,
	}
}

// ── JWT Claims Utilities ────────────────────────────────────────────────────

func ParseJWTClaims(jwt string) (map[string]interface{}, error) {
	parts := strings.Split(jwt, ".")
	if len(parts) < 2 {
		return nil, errors.New("invalid JWT: not enough segments")
	}
	payload := parts[1]

	var decoded []byte
	var err error
	if decoded, err = base64.RawURLEncoding.DecodeString(payload); err != nil {
		if decoded, err = base64.StdEncoding.DecodeString(payload); err != nil {
			if pad := len(payload) % 4; pad != 0 {
				payload += strings.Repeat("=", 4-pad)
			}
			if decoded, err = base64.StdEncoding.DecodeString(payload); err != nil {
				return nil, err
			}
		}
	}

	var claims map[string]interface{}
	if err := json.Unmarshal(decoded, &claims); err != nil {
		return nil, err
	}
	return claims, nil
}

func ExtractChatGPTAccountID(jwt string) string {
	claims, err := ParseJWTClaims(jwt)
	if err != nil {
		return ""
	}
	auth, ok := claims["https://api.openai.com/auth"].(map[string]interface{})
	if !ok {
		return ""
	}
	id, _ := auth["chatgpt_account_id"].(string)
	return id
}

func ExtractChatGPTUserID(jwt string) string {
	claims, err := ParseJWTClaims(jwt)
	if err != nil {
		return ""
	}
	auth, ok := claims["https://api.openai.com/auth"].(map[string]interface{})
	if !ok {
		return ""
	}
	uid, _ := auth["chatgpt_user_id"].(string)
	return uid
}

func ExtractPlanType(jwt string) string {
	claims, err := ParseJWTClaims(jwt)
	if err != nil {
		return ""
	}
	plan, _ := claims["chatgpt_plan_type"].(string)
	return plan
}

// ── Aurora Account Pool ─────────────────────────────────────────────────────

var ErrNoAuroraAccountAvailable = errors.New("no available aurora account of requested type")

type AuroraPool struct {
	mu        sync.Mutex
	noauth    []*AuroraAccount
	free      []*AuroraAccount
	puid      []*AuroraAccount
	cursors   [3]uint64
	tempMu    sync.RWMutex
	temporary map[string]*AuroraAccount // key = tokenHash
	profiles  []AuroraFingerprintProfile
}

func NewAuroraPool(initial []*AuroraAccount) *AuroraPool {
	p := &AuroraPool{
		temporary: make(map[string]*AuroraAccount),
		profiles:  AuroraDefaultProfiles,
	}
	for _, a := range initial {
		p.AddAccount(a)
	}
	return p
}

func (p *AuroraPool) AddAccount(acct *AuroraAccount) {
	if acct == nil {
		return
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	switch acct.Type {
	case AuroraAccountTypeNoAuth:
		p.noauth = append(p.noauth, acct)
	case AuroraAccountTypeFree:
		p.free = append(p.free, acct)
	case AuroraAccountTypePUID:
		p.puid = append(p.puid, acct)
	}
}

func (p *AuroraPool) sliceFor(t AuroraAccountType) *[]*AuroraAccount {
	switch t {
	case AuroraAccountTypeNoAuth:
		return &p.noauth
	case AuroraAccountTypeFree:
		return &p.free
	case AuroraAccountTypePUID:
		return &p.puid
	default:
		return nil
	}
}

func auroraTypeIndex(t AuroraAccountType) int {
	switch t {
	case AuroraAccountTypeNoAuth:
		return 0
	case AuroraAccountTypeFree:
		return 1
	case AuroraAccountTypePUID:
		return 2
	default:
		return -1
	}
}

func (p *AuroraPool) Acquire(acctType AuroraAccountType) (*AuroraAccount, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	slice := p.sliceFor(acctType)
	if slice == nil || len(*slice) == 0 {
		return nil, ErrNoAuroraAccountAvailable
	}
	idx := auroraTypeIndex(acctType)
	if idx < 0 {
		return nil, ErrNoAuroraAccountAvailable
	}

	entries := *slice
	n := len(entries)
	start := int(p.cursors[idx] % uint64(n))

	for i := 0; i < n; i++ {
		cur := (start + i) % n
		acct := entries[cur]
		acct.mu.Lock()
		if acct.Status == AuroraStatusActive {
			p.cursors[idx] = uint64(cur + 1)
			acct.TotalCalls++
			acct.LastUsed = time.Now()
			acct.mu.Unlock()
			return acct, nil
		}
		acct.mu.Unlock()
	}
	return nil, ErrNoAuroraAccountAvailable
}

func (p *AuroraPool) ReportFailure(acct *AuroraAccount) bool {
	if acct == nil {
		return false
	}
	acct.mu.Lock()
	defer acct.mu.Unlock()
	acct.Status = AuroraStatusExpired
	acct.FailedCalls++
	return true
}

func (p *AuroraPool) ExpiredAccounts() []*AuroraAccount {
	p.mu.Lock()
	defer p.mu.Unlock()
	var out []*AuroraAccount
	for _, list := range [][]*AuroraAccount{p.noauth, p.free, p.puid} {
		for _, a := range list {
			a.mu.RLock()
			if a.Status == AuroraStatusExpired {
				out = append(out, a)
			}
			a.mu.RUnlock()
		}
	}
	return out
}

func (p *AuroraPool) GetOrCreateTempAccount(token, userAgent string, proxyURL string) *AuroraAccount {
	h := TokenHashOf(token)
	p.tempMu.RLock()
	if existing, ok := p.temporary[h]; ok {
		p.tempMu.RUnlock()
		existing.mu.Lock()
		existing.LastUsed = time.Now()
		existing.mu.Unlock()
		return existing
	}
	p.tempMu.RUnlock()

	profile := p.randomProfile()
	ua := userAgent
	if ua == "" {
		ua = profile.UserAgent
	}

	fp := AuroraBrowserFingerprint{
		OaiDeviceID:         generateUUID(),
		OaiSessionID:        generateUUID(),
		UserAgent:           ua,
		ScreenWidth:         profile.ScreenWidth,
		ScreenHeight:        profile.ScreenHeight,
		HardwareConcurrency: profile.HardwareConcurrency,
		Platform:            profile.Platform,
		TLSProfileName:      profile.TLSProfileName,
	}

	acct := NewAuroraAccount(generateUUID(), AuroraAccountTypeFree, token)
	acct.ChatGPTAccountID = ExtractChatGPTAccountID(token)
	acct.Fingerprint = fp
	acct.Proxy = proxyURL
	acct.Status = AuroraStatusActive
	acct.LastUsed = time.Now()
	acct.IsTemporary = true

	p.tempMu.Lock()
	if existing, ok := p.temporary[h]; ok {
		p.tempMu.Unlock()
		existing.mu.Lock()
		existing.LastUsed = time.Now()
		existing.mu.Unlock()
		return existing
	}
	p.temporary[h] = acct
	p.tempMu.Unlock()
	return acct
}

func (p *AuroraPool) randomProfile() AuroraFingerprintProfile {
	if len(p.profiles) == 0 {
		return AuroraFingerprintProfile{
			Name: "default", TLSProfileName: "chrome_146",
			UserAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146.0.0.0 Safari/537.36",
			ScreenWidth: 1920, ScreenHeight: 1080, HardwareConcurrency: 8, Platform: "Win32",
		}
	}
	n, _ := rand.Int(rand.Reader, big.NewInt(int64(len(p.profiles))))
	return p.profiles[n.Int64()]
}

func (p *AuroraPool) EvictIdleTempAccounts(idleTimeout time.Duration) int {
	now := time.Now()
	p.tempMu.Lock()
	defer p.tempMu.Unlock()
	evicted := 0
	for hash, acct := range p.temporary {
		acct.mu.RLock()
		last := acct.LastUsed
		acct.mu.RUnlock()
		if now.Sub(last) > idleTimeout {
			delete(p.temporary, hash)
			evicted++
		}
	}
	return evicted
}

func (p *AuroraPool) TotalCount() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.tempMu.RLock()
	defer p.tempMu.RUnlock()
	return len(p.noauth) + len(p.free) + len(p.puid) + len(p.temporary)
}

func TokenHashOf(token string) string {
	h := sha256.Sum256([]byte(token))
	return fmt.Sprintf("%x", h[:16])
}

// TokenRenewer callback for session health checks
type AuroraTokenRenewer func(acct *AuroraAccount) bool

func (p *AuroraPool) RunHealthCheck(renew AuroraTokenRenewer) int {
	expired := p.ExpiredAccounts()
	renewedCount := 0
	for _, acct := range expired {
		acct.mu.Lock()
		if acct.Status == AuroraStatusExpired && renew != nil {
			acct.mu.Unlock()
			if renew(acct) {
				acct.mu.Lock()
				acct.Status = AuroraStatusActive
				acct.LastChecked = time.Now()
				acct.mu.Unlock()
				renewedCount++
			}
		} else {
			acct.mu.Unlock()
		}
	}
	return renewedCount
}

// ── Tool Call Types and Protocols ───────────────────────────────────────────

const (
	ToolCallStartTag = "<tool_call>"
	ToolCallEndTag   = "</tool_call>"
)

type AuroraToolFunction struct {
	Name        string          `json:"name"`
	Description string          `json:"description,omitempty"`
	Parameters  json.RawMessage `json:"parameters,omitempty"`
}

type AuroraTool struct {
	Type     string             `json:"type"`
	Function AuroraToolFunction `json:"function"`
}

type AuroraToolChoice struct {
	Type     string `json:"type,omitempty"`
	Function struct {
		Name string `json:"name,omitempty"`
	} `json:"function,omitempty"`
	Mode string `json:"mode,omitempty"` // "none", "auto", "required"
}

func (tc *AuroraToolChoice) ForcedFunctionName() string {
	if tc != nil && tc.Type == "function" && tc.Function.Name != "" {
		return tc.Function.Name
	}
	return ""
}

func (tc *AuroraToolChoice) IsForcedNone() bool {
	return tc != nil && (tc.Mode == "none" || tc.Type == "none")
}

type AuroraToolCallFunc struct {
	Name      string `json:"name"`
	Arguments string `json:"arguments"`
}

type AuroraToolCall struct {
	Index    int                `json:"index"`
	ID       string             `json:"id"`
	Type     string             `json:"type"`
	Function AuroraToolCallFunc `json:"function"`
}

type AuroraAPIMessage struct {
	Role      string           `json:"role"`
	Content   string           `json:"content"`
	Name      string           `json:"name,omitempty"`
	ToolCalls []AuroraToolCall `json:"tool_calls,omitempty"`
}

// ── Instruction and Prompt Builder ──────────────────────────────────────────

func BuildAuroraToolInstructions(tools []AuroraTool, toolChoice *AuroraToolChoice) string {
	if len(tools) == 0 {
		return ""
	}
	var sb strings.Builder
	sb.WriteString("# TOOLS AVAILABLE\n")
	sb.WriteString("You have access to the following tools. Use the EXACT tool name from the list below — do NOT rename, abbreviate or invent names.\n\n")
	sb.WriteString(compactAuroraToolsPrompt(tools))
	sb.WriteString("\n\n# TOOL CALLING FORMAT (MANDATORY)\n")
	sb.WriteString("To call a tool, output a JSON object wrapped EXACTLY in these tags:\n")
	sb.WriteString("<tool_call>\n")
	sb.WriteString(`{"name": "tool_name", "arguments": {"param_name": "value"}}`)
	sb.WriteString("\n</tool_call>\n\n")
	sb.WriteString("CRITICAL RULES:\n")
	sb.WriteString("0. Use ONLY the EXACT tool names listed under TOOLS AVAILABLE. Never rename or invent names.\n")
	sb.WriteString("1. ONLY use the tags above for tool calling. NEVER output raw JSON without tags.\n")
	sb.WriteString("2. You can call multiple tools by emitting multiple <tool_call> blocks consecutively.\n")
	sb.WriteString("3. Do NOT output any other text after your <tool_call> blocks. Wait for the tool response.\n")
	sb.WriteString("4. The JSON inside the tags MUST be valid and include the 'arguments' field.\n")
	sb.WriteString("5. If you need to use a tool, do it IMMEDIATELY without preamble.\n")
	if forced := toolChoice.ForcedFunctionName(); forced != "" {
		fmt.Fprintf(&sb, "\nCRITICAL: You MUST call the tool %q in this response. Do not call any other tool.\n", forced)
	} else if toolChoice.IsForcedNone() {
		sb.WriteString("\nCRITICAL: The user has DISABLED tool calling in this request. Do not emit any <tool_call> blocks.\n")
	}
	return sb.String()
}

func compactAuroraToolsPrompt(tools []AuroraTool) string {
	var sb strings.Builder
	for _, t := range tools {
		if t.Type != "function" {
			b, _ := json.Marshal(t)
			sb.WriteString("- ")
			sb.Write(b)
			sb.WriteByte('\n')
			continue
		}
		fmt.Fprintf(&sb, "- %s: %s\n", t.Function.Name, t.Function.Description)
		var schema struct {
			Type       string                    `json:"type"`
			Properties map[string]map[string]any `json:"properties"`
			Required   []string                  `json:"required"`
		}
		if len(t.Function.Parameters) == 0 {
			continue
		}
		if err := json.Unmarshal(t.Function.Parameters, &schema); err != nil || schema.Type != "object" || len(schema.Properties) == 0 {
			continue
		}
		sb.WriteString("  Params:\n")
		keys := make([]string, 0, len(schema.Properties))
		for k := range schema.Properties {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, key := range keys {
			prop := schema.Properties[key]
			isReq := "optional"
			for _, r := range schema.Required {
				if r == key {
					isReq = "required"
					break
				}
			}
			desc, _ := prop["description"].(string)
			typeStr, _ := prop["type"].(string)
			if typeStr == "" {
				typeStr = "string"
			}
			if desc != "" {
				fmt.Fprintf(&sb, "    * %s (%s, %s): %s\n", key, typeStr, isReq, desc)
			} else {
				fmt.Fprintf(&sb, "    * %s (%s, %s)\n", key, typeStr, isReq)
			}
		}
	}
	return sb.String()
}

func BuildAuroraFinalNudge(tools []AuroraTool, messages []AuroraAPIMessage) string {
	if len(tools) == 0 || len(messages) == 0 {
		return ""
	}
	last := messages[len(messages)-1]
	switch last.Role {
	case "tool", "function":
		return "\n[SYSTEM INSTRUCTION: The 'Tool (...)' block above is the REAL output produced by running your tool call on the user's actual machine. Treat it as ground truth. Continue the task based strictly on it: call another tool using <tool_call>{...}</tool_call> or produce your final answer.]"
	case "user":
		return "\n[SYSTEM INSTRUCTION: You are an autonomous coding agent. In THIS session you have NO Python sandbox. The ONLY way to inspect or modify files is to emit a <tool_call>. Begin your response immediately with '<tool_call>'.]"
	}
	return ""
}

// ── Stream Parser & JSON Sanitizer ──────────────────────────────────────────

type AuroraToolCallParser struct {
	buffer       string
	inside       bool
	emittedCount int
	emittedText  bool
}

func NewAuroraToolCallParser() *AuroraToolCallParser {
	return &AuroraToolCallParser{}
}

func (p *AuroraToolCallParser) Feed(chunk string) (textDelta string, toolCalls []AuroraToolCall) {
	p.buffer = normalizeAuroraTags(p.buffer + chunk)
	var text strings.Builder

	for len(p.buffer) > 0 {
		if !p.inside {
			startIdx := strings.Index(p.buffer, ToolCallStartTag)
			if startIdx >= 0 {
				pre := p.buffer[:startIdx]
				if pre != "" {
					text.WriteString(pre)
					p.emittedText = true
				}
				p.inside = true
				p.buffer = p.buffer[startIdx+len(ToolCallStartTag):]
				continue
			}

			flushIndex := len(p.buffer)
			for i := 1; i < len(ToolCallStartTag); i++ {
				if strings.HasSuffix(p.buffer, ToolCallStartTag[:i]) {
					flushIndex = len(p.buffer) - i
					break
				}
			}
			pre := p.buffer[:flushIndex]
			if pre != "" {
				text.WriteString(pre)
				p.emittedText = true
			}
			p.buffer = p.buffer[flushIndex:]
			break
		}

		endIdx := strings.Index(p.buffer, ToolCallEndTag)
		if endIdx < 0 {
			break
		}
		raw := strings.TrimSpace(p.buffer[:endIdx])
		if tc := buildAuroraToolCall(raw, p.emittedCount); tc != nil {
			toolCalls = append(toolCalls, *tc)
			p.emittedCount++
		}
		p.inside = false
		p.buffer = p.buffer[endIdx+len(ToolCallEndTag):]
	}
	return text.String(), toolCalls
}

func (p *AuroraToolCallParser) Flush() (textDelta string, toolCalls []AuroraToolCall) {
	remaining := p.buffer
	p.buffer = ""
	if remaining == "" {
		return "", nil
	}
	if p.inside {
		if tc := buildAuroraToolCall(remaining, p.emittedCount); tc != nil {
			toolCalls = append(toolCalls, *tc)
			p.emittedCount++
			return "", toolCalls
		}
		if p.emittedCount == 0 {
			return ToolCallStartTag + remaining, nil
		}
		return "", nil
	}
	if p.emittedCount == 0 {
		if tc := buildAuroraToolCall(remaining, p.emittedCount); tc != nil {
			toolCalls = append(toolCalls, *tc)
			p.emittedCount++
			return "", toolCalls
		}
		if !p.emittedText {
			return remaining, nil
		}
	}
	return "", nil
}

var (
	auroraToolCallsOpenRe    = regexp.MustCompile(`(?i)<tool_calls>`)
	auroraToolCallsCloseRe   = regexp.MustCompile(`(?i)</tool_calls>`)
	auroraToolCallAltOpenRe  = regexp.MustCompile(`(?i)<tool[_\s]call>`)
	auroraToolCallAltCloseRe = regexp.MustCompile(`(?i)</tool[_\s]call>`)
	auroraFenceOpenRe        = regexp.MustCompile(`^` + "```" + `[a-zA-Z]*\s*`)
	auroraFenceCloseRe       = regexp.MustCompile("```$")
)

func normalizeAuroraTags(s string) string {
	s = auroraToolCallsOpenRe.ReplaceAllString(s, ToolCallStartTag)
	s = auroraToolCallsCloseRe.ReplaceAllString(s, ToolCallEndTag)
	s = auroraToolCallAltOpenRe.ReplaceAllString(s, ToolCallStartTag)
	s = auroraToolCallAltCloseRe.ReplaceAllString(s, ToolCallEndTag)
	return s
}

func buildAuroraToolCall(raw string, index int) *AuroraToolCall {
	s := strings.TrimSpace(raw)
	if s == "" {
		return nil
	}
	s = auroraFenceOpenRe.ReplaceAllString(s, "")
	s = auroraFenceCloseRe.ReplaceAllString(strings.TrimSpace(s), "")
	s = strings.TrimSpace(s)

	idx := strings.Index(s, "{")
	if idx < 0 {
		return nil
	}
	s = s[idx:]
	obj, ok := RobustAuroraJSON(s)
	if !ok {
		return nil
	}
	name := pickStringKey(obj, "name", "tool", "tool_name", "function")
	if name == "" {
		return nil
	}
	args := extractAuroraArguments(obj)
	return &AuroraToolCall{
		Index: index,
		ID:    generateAuroraCallID(),
		Type:  "function",
		Function: AuroraToolCallFunc{
			Name:      name,
			Arguments: marshalAuroraArguments(args),
		},
	}
}

func generateAuroraCallID() string {
	var b [12]byte
	_, _ = rand.Read(b[:])
	return "call_" + hex.EncodeToString(b[:])
}

func pickStringKey(obj map[string]any, keys ...string) string {
	for _, k := range keys {
		if v, ok := obj[k]; ok {
			if s, ok := v.(string); ok {
				return s
			}
		}
	}
	return ""
}

func extractAuroraArguments(obj map[string]any) any {
	for _, k := range []string{"arguments", "parameters", "args"} {
		if v, ok := obj[k]; ok {
			return v
		}
	}
	remaining := make(map[string]any, len(obj))
	for k, v := range obj {
		if k == "name" || k == "tool" || k == "tool_name" || k == "function" {
			continue
		}
		remaining[k] = v
	}
	return remaining
}

func marshalAuroraArguments(v any) string {
	switch t := v.(type) {
	case nil:
		return "{}"
	case string:
		s := strings.TrimSpace(t)
		if strings.HasPrefix(s, "{") {
			if _, ok := RobustAuroraJSON(s); ok {
				return s
			}
		}
		b, _ := json.Marshal(map[string]string{"command": s})
		return string(b)
	case map[string]any:
		b, _ := json.Marshal(t)
		return string(b)
	default:
		b, _ := json.Marshal(t)
		return string(b)
	}
}

func FixAuroraBackslashes(s string) string {
	var out strings.Builder
	out.Grow(len(s) + 8)
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c != '\\' {
			out.WriteByte(c)
			continue
		}
		nxt := byte(0)
		if i+1 < len(s) {
			nxt = s[i+1]
		}
		if nxt != 0 && strings.IndexByte(`"\/bfnrtu`, nxt) >= 0 {
			out.WriteByte('\\')
			out.WriteByte(nxt)
			i++
			continue
		}
		out.WriteByte('\\')
		out.WriteByte('\\')
	}
	return out.String()
}

func RobustAuroraJSON(s string) (map[string]any, bool) {
	if s == "" {
		return nil, false
	}
	repaired := FixAuroraBackslashes(s)
	var v map[string]any
	if err := json.Unmarshal([]byte(repaired), &v); err == nil {
		return v, true
	}
	// Fallback to balanced brackets
	if end := firstBalancedBrackets(repaired); end > 0 {
		if err := json.Unmarshal([]byte(repaired[:end+1]), &v); err == nil {
			return v, true
		}
	}
	return nil, false
}

func firstBalancedBrackets(s string) int {
	depth := 0
	inStr := false
	esc := false
	for i := 0; i < len(s); i++ {
		c := s[i]
		if esc {
			esc = false
			continue
		}
		if c == '\\' {
			esc = true
			continue
		}
		if c == '"' {
			inStr = !inStr
			continue
		}
		if inStr {
			continue
		}
		switch c {
		case '{':
			depth++
		case '}':
			depth--
			if depth == 0 {
				return i
			}
		}
	}
	return -1
}

// ── Recover From Plain Text ─────────────────────────────────────────────────

func RecoverAuroraToolCallsFromText(text string, shellToolName string, shellParamName string) []AuroraToolCall {
	if !strings.Contains(text, "{") {
		return nil
	}
	if shellToolName == "" {
		shellToolName = "bash"
	}
	if shellParamName == "" {
		shellParamName = "command"
	}

	seen := make(map[string]bool)
	var out []AuroraToolCall

	// Scan balanced objects
	depth := 0
	inStr := false
	esc := false
	start := -1

	for i := 0; i < len(text); i++ {
		c := text[i]
		if esc {
			esc = false
			continue
		}
		if c == '\\' {
			esc = true
			continue
		}
		if c == '"' {
			inStr = !inStr
			continue
		}
		if inStr {
			continue
		}
		switch c {
		case '{':
			if depth == 0 {
				start = i
			}
			depth++
		case '}':
			depth--
			if depth == 0 && start >= 0 {
				blob := text[start : i+1]
				if obj, ok := RobustAuroraJSON(blob); ok {
					var tc *AuroraToolCall
					if name := pickStringKey(obj, "name", "tool", "tool_name", "function"); name != "" {
						tc = buildAuroraToolCall(blob, len(out))
					} else if cmd, ok := obj["cmd"]; ok {
						cmdStr := auroraCmdToString(cmd)
						if cmdStr != "" {
							raw, _ := json.Marshal(map[string]string{shellParamName: cmdStr})
							tc = &AuroraToolCall{
								Index: len(out),
								ID:    generateAuroraCallID(),
								Type:  "function",
								Function: AuroraToolCallFunc{
									Name:      shellToolName,
									Arguments: string(raw),
								},
							}
						}
					}
					if tc != nil {
						key := tc.Function.Name + ":" + tc.Function.Arguments
						if !seen[key] {
							seen[key] = true
							out = append(out, *tc)
						}
					}
				}
				start = -1
			}
		}
	}
	return out
}

func auroraCmdToString(v any) string {
	switch t := v.(type) {
	case string:
		return strings.TrimSpace(t)
	case []any:
		parts := make([]string, len(t))
		for i, p := range t {
			parts[i] = fmt.Sprint(p)
		}
		return strings.Join(parts, " ")
	case []string:
		return strings.Join(t, " ")
	default:
		return ""
	}
}

// ── Historical Serialization ────────────────────────────────────────────────

func SerializeAuroraToolCallsForHistory(calls []AuroraToolCall) string {
	var sb strings.Builder
	for _, c := range calls {
		sb.WriteString("\n")
		sb.WriteString(ToolCallStartTag)
		sb.WriteString(`{"name": "`)
		sb.WriteString(c.Function.Name)
		sb.WriteString(`", "arguments": `)
		if strings.HasPrefix(c.Function.Arguments, "{") {
			sb.WriteString(c.Function.Arguments)
		} else {
			b, _ := json.Marshal(c.Function.Arguments)
			sb.Write(b)
		}
		sb.WriteString(`}`)
		sb.WriteString(ToolCallEndTag)
	}
	return sb.String()
}
