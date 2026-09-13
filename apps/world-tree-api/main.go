package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

var stateBaseURL = strings.TrimRight(envOr("CAMELOT_STATE_URL", "http://127.0.0.1:3012"), "/")

func envOr(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func stateTarget(workspaceID, resource string, query url.Values) (string, error) {
	if workspaceID == "" || len(workspaceID) > 160 {
		return "", fmt.Errorf("invalid workspace id")
	}
	if resource != "snapshot" && resource != "events" && resource != "stream" {
		return "", fmt.Errorf("unsupported projection resource")
	}
	if strings.TrimSpace(query.Get("tenantId")) == "" {
		return "", fmt.Errorf("tenantId is required")
	}
	return fmt.Sprintf("%s/v1/workspaces/%s/%s?%s", stateBaseURL, url.PathEscape(workspaceID), resource, query.Encode()), nil
}

func parseWorkspaceProjectionPath(path string) (string, string, error) {
	trimmed := strings.TrimPrefix(path, "/api/workspaces/")
	parts := strings.Split(strings.Trim(trimmed, "/"), "/")
	if len(parts) != 2 {
		return "", "", fmt.Errorf("expected /api/workspaces/{workspaceId}/{snapshot|events|stream}")
	}
	return parts[0], parts[1], nil
}

func proxyJSON(client *http.Client, w http.ResponseWriter, r *http.Request, target string) {
	request, err := http.NewRequestWithContext(r.Context(), http.MethodGet, target, nil)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	response, err := client.Do(request)
	if err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "authoritative state service unavailable"})
		return
	}
	defer response.Body.Close()
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(response.StatusCode)
	_, _ = io.CopyN(w, response.Body, 4*1024*1024)
}

func proxySSE(client *http.Client, w http.ResponseWriter, r *http.Request, target string) {
	request, err := http.NewRequestWithContext(r.Context(), http.MethodGet, target, nil)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	response, err := client.Do(request)
	if err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "authoritative state stream unavailable"})
		return
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		w.WriteHeader(response.StatusCode)
		_, _ = io.CopyN(w, response.Body, 256*1024)
		return
	}
	flusher, ok := w.(http.Flusher)
	if !ok {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "streaming unsupported"})
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache, no-store")
	w.Header().Set("Connection", "keep-alive")
	reader := bufio.NewReaderSize(response.Body, 256*1024)
	for {
		line, readErr := reader.ReadString('\n')
		if len(line) > 0 {
			_, _ = io.WriteString(w, line)
			flusher.Flush()
		}
		if readErr != nil {
			if readErr != io.EOF {
				log.Printf("state stream ended with error: %v", readErr)
			}
			return
		}
	}
}

func main() {
	client := &http.Client{Timeout: 15 * time.Second}
	streamClient := &http.Client{Timeout: 0}
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		proxyJSON(client, w, r, stateBaseURL+"/health/ready")
	})

	mux.HandleFunc("/api/workspaces/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
			return
		}
		workspaceID, resource, err := parseWorkspaceProjectionPath(r.URL.Path)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
			return
		}
		target, err := stateTarget(workspaceID, resource, r.URL.Query())
		if err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
			return
		}
		if resource == "stream" {
			proxySSE(streamClient, w, r, target)
			return
		}
		proxyJSON(client, w, r, target)
	})

	// Old demo routes must never invent graph truth. Clients should migrate to workspace projections.
	mux.HandleFunc("/api/graph/nodes", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusGone, map[string]any{
			"error": "legacy mock graph projection removed",
			"replacement": "/api/workspaces/{workspaceId}/snapshot?tenantId={tenantId}",
			"verifiedOnly": true,
		})
	})
	mux.HandleFunc("/api/graph/stream", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusGone, map[string]any{
			"error": "legacy synthetic event stream removed",
			"replacement": "/api/workspaces/{workspaceId}/stream?tenantId={tenantId}",
			"verifiedOnly": true,
		})
	})

	server := &http.Server{
		Addr:              "127.0.0.1:3006",
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      0,
		IdleTimeout:       60 * time.Second,
	}
	log.Printf("World Tree verified projection gateway starting on %s -> %s", server.Addr, stateBaseURL)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("world tree projection gateway failed: %v", err)
	}
}
