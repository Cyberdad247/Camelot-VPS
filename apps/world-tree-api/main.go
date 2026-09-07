package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"
)

func main() {
	mux := http.NewServeMux()

	// 1. Accessible Node/Edge Lists (JSON for HTMX rendering)
	mux.HandleFunc("/api/graph/nodes", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		// Mocks Neo4j Node Retrieval
		w.Write([]byte(`
			<div class="space-y-2">
				<div class="p-2 bg-white/5 border border-white/10 rounded flex justify-between">
					<span class="text-emerald-400 font-mono text-xs">[ENTITY] Project Alpha</span>
					<span class="text-slate-500 text-[10px]">Hash: a1b2c</span>
				</div>
				<div class="p-2 bg-white/5 border border-white/10 rounded flex justify-between">
					<span class="text-luxora font-mono text-xs">[FACT] Budget Approved</span>
					<span class="text-slate-500 text-[10px]">Hash: 9f8d7</span>
				</div>
			</div>
		`))
	})

	// 2. SSE Event Projection
	mux.HandleFunc("/api/graph/stream", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")

		flusher, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "Streaming unsupported", http.StatusInternalServerError)
			return
		}

		for i := 0; i < 5; i++ {
			time.Sleep(2 * time.Second)
			msg := fmt.Sprintf(`{"event": "graph_update", "node_id": "N-%d", "type": "memory.promoted"}`, i)
			fmt.Fprintf(w, "data: %s\n\n", msg)
			flusher.Flush()
		}
	})

	log.Println("World Tree API starting on 127.0.0.1:3006")
	if err := http.ListenAndServe("127.0.0.1:3006", mux); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
