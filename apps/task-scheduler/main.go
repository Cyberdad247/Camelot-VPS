package main

import (
	"encoding/json"
	"log"
	"net/http"
)

type DagAdmissionRequest struct {
	MissionID string `json:"mission_id"`
	TenantID  string `json:"tenant_id"`
}

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/schedule/dag", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		// In reality, this communicates with Sentinel for admission and Gideon for verification
		json.NewEncoder(w).Encode(map[string]string{
			"status": "admitted",
			"dag_id": "DAG-MOCK-8F92A",
			"message": "Task DAG scheduled and placed in Merlin execution queue.",
		})
	})

	log.Println("Merlin Task Scheduler starting on 127.0.0.1:3005")
	if err := http.ListenAndServe("127.0.0.1:3005", mux); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
