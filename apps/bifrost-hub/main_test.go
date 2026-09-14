package main

import (
	"testing"
	"time"
)

func validEnvelope(now time.Time) Envelope {
	return Envelope{
		SchemaVersion: "bifrost/1",
		ID:            "evt_test_1",
		Type:          "task.dispatch",
		Lane:          "P1_ACTIONABLE",
		OccurredAt:    now,
		ExpiresAt:     now.Add(2 * time.Minute),
		Routing: Routing{
			TenantID:       "tenant_test",
			WorkspaceID:    "workspace_test",
			MissionID:      "mission_test",
			Target:         "node.workload",
			CorrelationID:  "corr_test",
			IdempotencyKey: "sha256:test-idempotency",
		},
		PayloadHash: "sha256:payload",
		Integrity: Integrity{
			Signer:    "node_test",
			Signature: "ed25519:placeholder",
		},
	}
}

func TestValidateEnvelopeStructure(t *testing.T) {
	now := time.Now().UTC()
	if err := validateEnvelope(validEnvelope(now), now); err != nil {
		t.Fatalf("expected valid envelope structure, got %v", err)
	}
}

func TestRejectExpiredEnvelope(t *testing.T) {
	now := time.Now().UTC()
	envelope := validEnvelope(now.Add(-5 * time.Minute))
	envelope.ExpiresAt = now.Add(-time.Minute)
	if err := validateEnvelope(envelope, now); err == nil {
		t.Fatal("expected expired envelope to be rejected")
	}
}

func TestReplayWindowRejectsDuplicate(t *testing.T) {
	window := NewReplayWindow()
	now := time.Now().UTC()
	if !window.Claim("same-key", now.Add(time.Minute), now) {
		t.Fatal("expected first claim to pass")
	}
	if window.Claim("same-key", now.Add(time.Minute), now) {
		t.Fatal("expected duplicate claim to fail")
	}
	if !window.Claim("same-key", now.Add(2*time.Minute), now.Add(90*time.Second)) {
		t.Fatal("expected expired claim to be reusable")
	}
}

func TestTelemetryMayOmitIdempotencyKey(t *testing.T) {
	now := time.Now().UTC()
	envelope := validEnvelope(now)
	envelope.Lane = "P3_TELEMETRY"
	envelope.Routing.IdempotencyKey = ""
	if err := validateEnvelope(envelope, now); err != nil {
		t.Fatalf("telemetry should allow an empty idempotency key: %v", err)
	}
}
