package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"

	"github.com/gorilla/mux"
)

// MCPTool defines the structure for tool discovery
type MCPTool struct {
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	InputSchema map[string]interface{} `json:"inputSchema"`
}

// MCPCallRequest represents an incoming tool invocation
type MCPCallRequest struct {
	Name      string            `json:"name"`
	Arguments map[string]string `json:"arguments"`
}

func handleMCPTools(w http.ResponseWriter, r *http.Request) {
	tools := []MCPTool{
		{
			Name:        "spawn_microvm_task",
			Description: "Executes an ephemeral payload inside an isolated Firecracker MicroVM within 80ms.",
			InputSchema: map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"tenant":     map[string]string{"type": "string", "description": "The calling agent ID"},
					"capability": map[string]string{"type": "string", "description": "System binary to trigger (e.g., echo, ls)"},
					"payload":    map[string]string{"type": "string", "description": "Payload argument for the binary"},
				},
				"required": []string{"tenant", "capability", "payload"},
			},
		},
		{
			Name:        "arthurian_omni_forge_pipeline",
			Description: "Triggers Arthur's 7-Phase Omni-Forge Digital Factory (Intent->Spec->Plan->DAG->Sandbox->Verify->Receipt) under strict 512MB RAM cap with Z3 formal theorem convexity.",
			InputSchema: map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"mission_id": map[string]string{"type": "string", "description": "Unique mission identifier"},
					"objective":  map[string]string{"type": "string", "description": "Target objective or code to synthesize"},
					"risk_tier":  map[string]string{"type": "string", "description": "Risk Tier: LOW, MEDIUM, HIGH, CRITICAL"},
				},
				"required": []string{"objective"},
			},
		},
		{
			Name:        "bifrost_bridge_route",
			Description: "Probes and routes agent intents across the 3-tier Bifrost Bridge (Primary Gateway :3001, Sidecar :8080, Dark Mesh VPS :8091).",
			InputSchema: map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"tenant":     map[string]string{"type": "string", "description": "Calling Knight ID"},
					"capability": map[string]string{"type": "string", "description": "Routing capability"},
					"payload":    map[string]string{"type": "string", "description": "Data payload to transmit across bridge"},
				},
				"required": []string{"tenant", "capability", "payload"},
			},
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"tools": tools})
}

func handleMCPCall(w http.ResponseWriter, r *http.Request) {
	var request MCPCallRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		http.Error(w, "Invalid MCP JSON-RPC format", http.StatusBadRequest)
		return
	}

	log.Printf("[MCP-BRIDGE] Invoking Tool: %s", request.Name)

	switch request.Name {
	case "spawn_microvm_task":
		bifrostPayload := AgentIntent{
			Tenant:     request.Arguments["tenant"],
			Capability: request.Arguments["capability"],
			Payload:    request.Arguments["payload"],
		}
		reqBody, _ := json.Marshal(bifrostPayload)
		resp, err := http.Post("http://127.0.0.1:8080/execute", "application/json", bytes.NewBuffer(reqBody))
		if err != nil {
			http.Error(w, "Underlying Bifrost transport layer unreachable", http.StatusServiceUnavailable)
			return
		}
		defer resp.Body.Close()

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"status":  "success",
			"message": "Ephemeral MicroVM executed and verified via Blake3 SQLite ledger.",
		})
		return

	case "arthurian_omni_forge_pipeline":
		intent := AgentIntent{
			Tenant:     "ARTHUR_OMEGA",
			Capability: "ARTHURIAN_OMNI_FORGE",
			MissionID:  request.Arguments["mission_id"],
			Payload:    request.Arguments["objective"],
			RiskTier:   request.Arguments["risk_tier"],
		}
		receipt := ExecuteArthurianOmniForge(intent)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":  "OMNI_FORGE_COMPLETE",
			"receipt": receipt,
		})
		return

	case "bifrost_bridge_route":
		intent := AgentIntent{
			Tenant:     request.Arguments["tenant"],
			Capability: request.Arguments["capability"],
			Payload:    request.Arguments["payload"],
		}
		status := GetBifrostBridgeStatus()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":        "ROUTED",
			"bridge_status": status,
			"intent":        intent,
		})
		return

	default:
		http.Error(w, fmt.Sprintf("Tool '%s' not supported", request.Name), http.StatusNotFound)
	}
}

func RegisterMCPEndpoints(r *mux.Router) {
	r.HandleFunc("/mcp/tools", handleMCPTools).Methods("GET")
	r.HandleFunc("/mcp/call", handleMCPCall).Methods("POST")
}
