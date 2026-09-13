package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"
)

const maxRequestBytes = 32 * 1024

var stateURL = strings.TrimRight(envOr("CAMELOT_STATE_URL", "http://127.0.0.1:3012"), "/")

type ProposalRequest struct {
	TenantID    string `json:"tenantId"`
	WorkspaceID string `json:"workspaceId"`
	MissionID   string `json:"missionId"`
	TaskID      string `json:"taskId"`
	CartridgeID string `json:"cartridgeId"`
	TraceID     string `json:"traceId"`
	Objective   string `json:"objective"`
}

type workspaceEventRequest struct {
	Type           string         `json:"type"`
	TenantID       string         `json:"tenantId"`
	WorkspaceID    string         `json:"workspaceId"`
	CartridgeID    string         `json:"cartridgeId"`
	MissionID      string         `json:"missionId"`
	TraceID        string         `json:"traceId"`
	Classification string         `json:"classification"`
	Visibility     string         `json:"visibility"`
	Payload        map[string]any `json:"payload"`
	Provenance     map[string]any `json:"provenance"`
}

func envOr(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}

func validScope(value string) bool {
	value = strings.TrimSpace(value)
	return value != "" && len(value) <= 160
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func propose(client *http.Client, proposal ProposalRequest) (map[string]any, error) {
	for name, value := range map[string]string{
		"tenantId": proposal.TenantID,
		"workspaceId": proposal.WorkspaceID,
		"missionId": proposal.MissionID,
		"taskId": proposal.TaskID,
		"cartridgeId": proposal.CartridgeID,
		"traceId": proposal.TraceID,
	} {
		if !validScope(value) {
			return nil, fmt.Errorf("invalid %s", name)
		}
	}
	if strings.TrimSpace(proposal.Objective) == "" || len(proposal.Objective) > 4096 {
		return nil, errors.New("objective must contain 1..4096 characters")
	}

	requestBody := workspaceEventRequest{
		Type:           "task.state.changed",
		TenantID:       proposal.TenantID,
		WorkspaceID:    proposal.WorkspaceID,
		CartridgeID:    proposal.CartridgeID,
		MissionID:      proposal.MissionID,
		TraceID:        proposal.TraceID,
		Classification: "internal",
		Visibility:     "operator",
		Payload: map[string]any{
			"taskId": proposal.TaskID,
			"state": "PROPOSED",
			"authorityEpoch": authorityEpoch(),
			"reason": "mission proposal accepted for policy evaluation",
			"objective": proposal.Objective,
		},
		Provenance: map[string]any{
			"source": "merlin-task-scheduler",
		},
	}
	encoded, err := json.Marshal(requestBody)
	if err != nil {
		return nil, fmt.Errorf("encode workspace proposal: %w", err)
	}
	request, err := http.NewRequest(http.MethodPost, stateURL+"/v1/events", bytes.NewReader(encoded))
	if err != nil {
		return nil, fmt.Errorf("create state request: %w", err)
	}
	request.Header.Set("Content-Type", "application/json")
	response, err := client.Do(request)
	if err != nil {
		return nil, fmt.Errorf("authoritative state service unavailable: %w", err)
	}
	defer response.Body.Close()
	body, err := io.ReadAll(io.LimitReader(response.Body, 128*1024))
	if err != nil {
		return nil, fmt.Errorf("read state response: %w", err)
	}
	if response.StatusCode != http.StatusCreated {
		return nil, fmt.Errorf("state service rejected proposal (%d): %s", response.StatusCode, strings.TrimSpace(string(body)))
	}
	var event map[string]any
	if err := json.Unmarshal(body, &event); err != nil {
		return nil, fmt.Errorf("decode state response: %w", err)
	}
	return event, nil
}

func authorityEpoch() uint64 {
	var value uint64 = 1
	if raw := strings.TrimSpace(os.Getenv("CAMELOT_AUTHORITY_EPOCH")); raw != "" {
		_, _ = fmt.Sscan(raw, &value)
	}
	if value == 0 {
		return 1
	}
	return value
}

func main() {
	client := &http.Client{Timeout: 5 * time.Second}
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{
			"status": "ready",
			"service": "merlin-task-scheduler",
			"role": "proposal-ingress",
			"effectAuthority": false,
			"stateService": stateURL,
		})
	})

	mux.HandleFunc("/schedule/proposal", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, maxRequestBytes)
		decoder := json.NewDecoder(r.Body)
		decoder.DisallowUnknownFields()
		var proposal ProposalRequest
		if err := decoder.Decode(&proposal); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid proposal: " + err.Error()})
			return
		}
		event, err := propose(client, proposal)
		if err != nil {
			writeJSON(w, http.StatusConflict, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusAccepted, map[string]any{
			"status": "proposed",
			"nextGate": "sentinel",
			"effectAuthority": false,
			"event": event,
		})
	})

	mux.HandleFunc("/schedule/dag", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusGone, map[string]any{
			"error": "mock DAG admission endpoint removed",
			"replacement": "/schedule/proposal",
			"reason": "a scheduler cannot claim admission before Sentinel and downstream gates produce evidence",
		})
	})

	server := &http.Server{
		Addr:              "127.0.0.1:3005",
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       60 * time.Second,
	}
	log.Printf("Merlin proposal ingress starting on %s -> %s", server.Addr, stateURL)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("scheduler failed: %v", err)
	}
}
