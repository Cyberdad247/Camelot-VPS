package main

import (
	"encoding/json"
	"log"
	"net/http"
)

type HermesAdmission struct {
	Source   string `json:"source"`
	TenantID string `json:"tenant_id"`
}

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/hermes/sync", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"status":  "syncing",
			"message": "Constrained Hermes syncing initiated. Read-only limits applied.",
		})
	})

	log.Println("Hermes Adapter starting on 127.0.0.1:3012")
	if err := http.ListenAndServe("127.0.0.1:3012", mux); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
