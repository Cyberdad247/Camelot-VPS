package main

import (
	"crypto/ed25519"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

const (
	serviceVersion   = "2.0.0"
	maxEnvelopeBytes = 8 * 1024
	maxFutureSkew    = 30 * time.Second
)

var laneCapacityBytes = map[string]int{
	"P0_CRITICAL":   4 * 1024 * 1024,
	"P1_ACTIONABLE": 4 * 1024 * 1024,
	"P2_DIGEST":     3 * 1024 * 1024,
	"P3_TELEMETRY":  2 * 1024 * 1024,
	"P4_RETRY":      2 * 1024 * 1024,
	"RESERVE":       1 * 1024 * 1024,
}

type Routing struct {
	TenantID       string `json:"tenant_id"`
	WorkspaceID    string `json:"workspace_id"`
	MissionID      string `json:"mission_id"`
	Target         string `json:"target"`
	CorrelationID  string `json:"correlation_id"`
	IdempotencyKey string `json:"idempotency_key"`
}

type Integrity struct {
	Signer    string `json:"signer"`
	Signature string `json:"signature"`
}

type Envelope struct {
	SchemaVersion string    `json:"schema_version"`
	ID            string    `json:"id"`
	Type          string    `json:"type"`
	Lane          string    `json:"lane"`
	OccurredAt    time.Time `json:"occurred_at"`
	ExpiresAt     time.Time `json:"expires_at"`
	Routing       Routing   `json:"routing"`
	PayloadRef    string    `json:"payload_ref,omitempty"`
	PayloadHash   string    `json:"payload_hash"`
	Integrity     Integrity `json:"integrity"`
}

type signingEnvelope struct {
	SchemaVersion string    `json:"schema_version"`
	ID            string    `json:"id"`
	Type          string    `json:"type"`
	Lane          string    `json:"lane"`
	OccurredAt    time.Time `json:"occurred_at"`
	ExpiresAt     time.Time `json:"expires_at"`
	Routing       Routing   `json:"routing"`
	PayloadRef    string    `json:"payload_ref,omitempty"`
	PayloadHash   string    `json:"payload_hash"`
	Signer        string    `json:"signer"`
}

type Gateway struct {
	trustRoots map[string]ed25519.PublicKey
	replay     *ReplayWindow
}

type ReplayWindow struct {
	mu      sync.Mutex
	entries map[string]time.Time
}

func NewReplayWindow() *ReplayWindow {
	return &ReplayWindow{entries: make(map[string]time.Time)}
}

func (r *ReplayWindow) Claim(key string, expiresAt time.Time, now time.Time) bool {
	if key == "" {
		return false
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	for existing, expiry := range r.entries {
		if !expiry.After(now) {
			delete(r.entries, existing)
		}
	}
	if expiry, exists := r.entries[key]; exists && expiry.After(now) {
		return false
	}
	r.entries[key] = expiresAt
	return true
}

func signingBytes(envelope Envelope) ([]byte, error) {
	return json.Marshal(signingEnvelope{
		SchemaVersion: envelope.SchemaVersion,
		ID:            envelope.ID,
		Type:          envelope.Type,
		Lane:          envelope.Lane,
		OccurredAt:    envelope.OccurredAt,
		ExpiresAt:     envelope.ExpiresAt,
		Routing:       envelope.Routing,
		PayloadRef:    envelope.PayloadRef,
		PayloadHash:   envelope.PayloadHash,
		Signer:        envelope.Integrity.Signer,
	})
}

func decodeSignature(value string) ([]byte, error) {
	value = strings.TrimSpace(value)
	value = strings.TrimPrefix(value, "ed25519:")
	decoded, err := hex.DecodeString(value)
	if err != nil {
		return nil, fmt.Errorf("signature is not valid hex: %w", err)
	}
	if len(decoded) != ed25519.SignatureSize {
		return nil, fmt.Errorf("signature must be %d bytes", ed25519.SignatureSize)
	}
	return decoded, nil
}

func validateEnvelope(envelope Envelope, now time.Time) error {
	if envelope.SchemaVersion != "bifrost/1" {
		return errors.New("unsupported schema_version")
	}
	if envelope.ID == "" || envelope.Type == "" {
		return errors.New("id and type are required")
	}
	if _, ok := laneCapacityBytes[envelope.Lane]; !ok {
		return errors.New("unknown Bifrost lane")
	}
	if envelope.OccurredAt.IsZero() || envelope.ExpiresAt.IsZero() {
		return errors.New("occurred_at and expires_at are required")
	}
	if envelope.OccurredAt.After(now.Add(maxFutureSkew)) {
		return errors.New("envelope occurred_at is too far in the future")
	}
	if !envelope.ExpiresAt.After(now) {
		return errors.New("envelope expired")
	}
	if !envelope.ExpiresAt.After(envelope.OccurredAt) {
		return errors.New("expires_at must be after occurred_at")
	}
	if envelope.Routing.TenantID == "" || envelope.Routing.WorkspaceID == "" || envelope.Routing.MissionID == "" {
		return errors.New("tenant, workspace, and mission routing scope are required")
	}
	if envelope.Routing.Target == "" || envelope.Routing.CorrelationID == "" {
		return errors.New("target and correlation_id are required")
	}
	if envelope.Lane != "P3_TELEMETRY" && envelope.Routing.IdempotencyKey == "" {
		return errors.New("idempotency_key is required for non-telemetry envelopes")
	}
	if !strings.HasPrefix(envelope.PayloadHash, "sha256:") || len(envelope.PayloadHash) <= len("sha256:") {
		return errors.New("payload_hash must be a sha256 reference")
	}
	if envelope.Integrity.Signer == "" || envelope.Integrity.Signature == "" {
		return errors.New("signed integrity block is required")
	}
	return nil
}

func (g *Gateway) verifyEnvelope(envelope Envelope, now time.Time) error {
	if err := validateEnvelope(envelope, now); err != nil {
		return err
	}
	publicKey, ok := g.trustRoots[envelope.Integrity.Signer]
	if !ok {
		return errors.New("signer is not trusted by this Hub")
	}
	signature, err := decodeSignature(envelope.Integrity.Signature)
	if err != nil {
		return err
	}
	canonical, err := signingBytes(envelope)
	if err != nil {
		return fmt.Errorf("canonicalize envelope: %w", err)
	}
	if !ed25519.Verify(publicKey, canonical, signature) {
		return errors.New("invalid Ed25519 envelope signature")
	}
	return nil
}

func parseTrustRoots(raw string) (map[string]ed25519.PublicKey, error) {
	roots := map[string]string{}
	if strings.TrimSpace(raw) == "" {
		return map[string]ed25519.PublicKey{}, nil
	}
	if err := json.Unmarshal([]byte(raw), &roots); err != nil {
		return nil, fmt.Errorf("CAMELOT_BIFROST_TRUST_ROOTS_JSON must be a JSON object: %w", err)
	}
	parsed := make(map[string]ed25519.PublicKey, len(roots))
	for signer, encoded := range roots {
		bytes, err := hex.DecodeString(strings.TrimPrefix(encoded, "ed25519:"))
		if err != nil || len(bytes) != ed25519.PublicKeySize {
			return nil, fmt.Errorf("trust root %q must be a %d-byte Ed25519 public key", signer, ed25519.PublicKeySize)
		}
		parsed[signer] = ed25519.PublicKey(bytes)
	}
	return parsed, nil
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func health(gateway *Gateway, ready bool) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		status := http.StatusOK
		state := "ok"
		if ready && len(gateway.trustRoots) == 0 {
			status = http.StatusServiceUnavailable
			state = "not_ready"
		}
		writeJSON(w, status, map[string]any{
			"status":          state,
			"service":         "camelot-bifrost-hub",
			"version":         serviceVersion,
			"authorityGrant":  false,
			"trustRootCount":  len(gateway.trustRoots),
			"maxEnvelopeBytes": maxEnvelopeBytes,
		})
	}
}

func (g *Gateway) admit(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, maxEnvelopeBytes)
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	var envelope Envelope
	if err := decoder.Decode(&envelope); err != nil {
		if errors.Is(err, io.EOF) {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "empty envelope"})
			return
		}
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid envelope: " + err.Error()})
		return
	}
	now := time.Now().UTC()
	if err := g.verifyEnvelope(envelope, now); err != nil {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": err.Error()})
		return
	}

	replayKey := envelope.Routing.IdempotencyKey
	if replayKey == "" {
		replayKey = envelope.ID
	}
	if !g.replay.Claim(replayKey, envelope.ExpiresAt, now) {
		writeJSON(w, http.StatusConflict, map[string]string{"error": "replay or duplicate envelope rejected"})
		return
	}

	writeJSON(w, http.StatusAccepted, map[string]any{
		"admitted":       true,
		"eventId":        envelope.ID,
		"lane":           envelope.Lane,
		"target":         envelope.Routing.Target,
		"correlationId":  envelope.Routing.CorrelationID,
		"transportOnly":  true,
		"authorityGrant": false,
		"nextGate":       "sentinel",
	})
}

func sameHostToken(actual, expected string) bool {
	if expected == "" || len(actual) != len(expected) {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(actual), []byte(expected)) == 1
}

func main() {
	trustRoots, err := parseTrustRoots(os.Getenv("CAMELOT_BIFROST_TRUST_ROOTS_JSON"))
	if err != nil {
		log.Fatal(err)
	}
	gateway := &Gateway{trustRoots: trustRoots, replay: NewReplayWindow()}

	host := strings.TrimSpace(os.Getenv("CAMELOT_BIFROST_HOST"))
	if host == "" {
		host = "127.0.0.1"
	}
	port := strings.TrimSpace(os.Getenv("CAMELOT_BIFROST_PORT"))
	if port == "" {
		port = "3000"
	}
	if ip := net.ParseIP(host); ip == nil || !ip.IsLoopback() {
		log.Fatalf("Bifrost Hub must bind to loopback behind the explicit HTTPS/mesh ingress layer; got %q", host)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", health(gateway, true))
	mux.HandleFunc("/health/live", health(gateway, false))
	mux.HandleFunc("/health/ready", health(gateway, true))
	mux.HandleFunc("/v1/bifrost/admit", gateway.admit)
	mux.HandleFunc("/v1/bifrost/config", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{
			"schemaVersion":    "bifrost/1",
			"transportOnly":    true,
			"authorityGrant":   false,
			"maxEnvelopeBytes": maxEnvelopeBytes,
			"lanes":            laneCapacityBytes,
			"trustRootCount":   len(gateway.trustRoots),
		})
	})
	mux.HandleFunc("/", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusForbidden, map[string]string{
			"error": "Bifrost is a narrow trust/transport boundary. Present a signed bifrost/1 envelope to the admitted route.",
		})
	})

	address := net.JoinHostPort(host, port)
	server := &http.Server{
		Addr:              address,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	log.Printf("Camelot Bifrost Hub %s listening on http://%s (transport authority=false, trust roots=%d)", serviceVersion, address, len(trustRoots))
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("Bifrost server failed: %v", err)
	}
}
