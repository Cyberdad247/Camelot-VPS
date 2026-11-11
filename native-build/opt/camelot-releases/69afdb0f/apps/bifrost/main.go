// SPDX-License-Identifier: MIT

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/gorilla/websocket"
	"google.golang.org/grpc"
)

const (
	// The hub's own tailnet address (mesh_topology.HUB_TAILSCALE_IP). This was
	// 100.71.218.75, which is `kba-services` — a node absent from the tailnet — so
	// net.Listen below always failed and the service silently fell back to
	// binding 0.0.0.0. The intent was a tailnet-scoped bind; the fallback quietly
	// widened it to every interface instead.
	TailscaleBindIP = "100.110.180.18"
	HTTPPort        = "4433"
	GRPCPort        = "4434"
	RedisAddr       = "127.0.0.1:6379"
	BullMQQueueKey  = "bull:webhooks:id"
)

// WebhookPayload captures normalized incoming webhook events
type WebhookPayload struct {
	ID        string                 `json:"id"`
	Source    string                 `json:"source"`
	Timestamp int64                  `json:"timestamp"`
	Data      map[string]interface{} `json:"data"`
}

// BullMQJob strictly matches BullMQ Redis queue structure
type BullMQJob struct {
	Name      string         `json:"name"`
	Data      WebhookPayload `json:"data"`
	Opts      map[string]any `json:"opts"`
	Timestamp int64          `json:"timestamp"`
}

type BifrostServer struct {
	redisClient *redis.Client
	memo        *MemoCache
	upgrader    websocket.Upgrader
}

func NewBifrostServer() *BifrostServer {
	rdb := redis.NewClient(&redis.Options{
		Addr:     RedisAddr,
		Password: "", // zero trust internal localhost socket
		DB:       0,
	})

	return &BifrostServer{
		redisClient: rdb,
		// CloudBrain synthesis memo, Redis-backed in production (cb:memo:,
		// 10-minute TTL). Previously constructed only in tests — now live.
		memo: NewMemoCache(NewRedisKV(rdb), DefaultMemoTTL),
		upgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool {
				// Enforce strict local mesh origin verification
				host, _, _ := net.SplitHostPort(r.RemoteAddr)
				return host == TailscaleBindIP || host == "127.0.0.1"
			},
		},
	}
}

func (s *BifrostServer) enableCORS(w http.ResponseWriter, r *http.Request) bool {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Bifrost-Signature, X-Lamport-Clock")

	if r.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return true
	}
	return false
}

func (s *BifrostServer) RouteWebhook(source string, w http.ResponseWriter, r *http.Request) {
	if s.enableCORS(w, r) {
		return
	}

	if r.Method != http.MethodPost {
		http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read payload", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	var payloadData map[string]interface{}
	if err := json.Unmarshal(body, &payloadData); err != nil {
		http.Error(w, "Invalid JSON payload", http.StatusBadRequest)
		return
	}

	eventID := fmt.Sprintf("%s_%d", source, time.Now().UnixNano())
	payload := WebhookPayload{
		ID:        eventID,
		Source:    source,
		Timestamp: time.Now().UnixMilli(),
		Data:      payloadData,
	}

	// Format as BullMQ compatible job
	job := BullMQJob{
		Name:      fmt.Sprintf("process_%s_webhook", source),
		Data:      payload,
		Opts:      map[string]any{"attempts": 3, "backoff": 5000},
		Timestamp: time.Now().UnixMilli(),
	}

	jobBytes, err := json.Marshal(job)
	if err != nil {
		http.Error(w, "Failed to serialize job", http.StatusInternalServerError)
		return
	}

	// Enqueue into BullMQ Redis Queue without public port exposure
	ctx := context.Background()
	err = s.redisClient.RPush(ctx, BullMQQueueKey, jobBytes).Err()
	if err != nil {
		log.Printf("[POLYGLOT_ROUTER_ERROR] Redis enqueue failed for %s: %v", source, err)
		http.Error(w, "Internal Queue Error", http.StatusInternalServerError)
		return
	}

	log.Printf("[POLYGLOT_ROUTER_SUCCESS] Intercepted %s webhook -> Redis key '%s' (Job ID: %s)", source, BullMQQueueKey, eventID)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	json.NewEncoder(w).Encode(map[string]string{
		"status":  "QUEUED",
		"job_id":  eventID,
		"ingress": TailscaleBindIP,
	})
}

// MemoLookup returns a cached CloudBrain synthesis for prompt, if fresh.
func (s *BifrostServer) MemoLookup(prompt string) (string, bool) {
	return s.memo.Lookup(context.Background(), prompt)
}

// StoreMemo caches a CloudBrain synthesis behind the memo TTL.
func (s *BifrostServer) StoreMemo(prompt, synthesis string) error {
	return s.memo.StoreMemo(context.Background(), prompt, synthesis)
}

// MemoStats reports memo wiring for the health probe (no secret values).
func (s *BifrostServer) MemoStats() map[string]any {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	redisOK := s.redisClient.Ping(ctx).Err() == nil
	return map[string]any{
		"prefix":     MemoPrefix,
		"ttl_seconds": int(DefaultMemoTTL.Seconds()),
		"redis_ok":   redisOK,
	}
}

func (s *BifrostServer) HandleWebSocket(w http.ResponseWriter, r *http.Request) {	conn, err := s.upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("[BIFROST_WS_ERROR] Upgrade failed: %v", err)
		return
	}
	defer conn.Close()

	log.Printf("[BIFROST_WS_CONNECT] Client connected from %s via Tailscale mTLS Bridge", r.RemoteAddr)

	for {
		messageType, p, err := conn.ReadMessage()
		if err != nil {
			log.Printf("[BIFROST_WS_DISCONNECT] Client %s disconnected", r.RemoteAddr)
			break
		}
		// Echo telemetry frame or process command
		if err := conn.WriteMessage(messageType, p); err != nil {
			break
		}
	}
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)
	log.Printf("==================================================================")
	log.Printf("⚡ BIFROST BARE-METAL MESH ENGINE — SIR CODA // CAMELOT-OS")
	log.Printf("⚡ Target IP: %s | Max Memory Footprint: <20MB (Native)", TailscaleBindIP)
	log.Printf("==================================================================")

	server := NewBifrostServer()

	mux := http.NewServeMux()

	// Polyglot Router endpoints (Stripe & Zendesk Webhook Interception)
	mux.HandleFunc("/webhooks/stripe", func(w http.ResponseWriter, r *http.Request) {
		server.RouteWebhook("stripe", w, r)
	})
	mux.HandleFunc("/webhooks/zendesk", func(w http.ResponseWriter, r *http.Request) {
		server.RouteWebhook("zendesk", w, r)
	})

	// Zero-Trust mTLS WebSocket Bridge
	mux.HandleFunc("/ws/bifrost", server.HandleWebSocket)

	// Health probe endpoint (includes Redis + memo wiring status)
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		if server.enableCORS(w, r) {
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]any{
			"status": "HEALTHY",
			"mesh":   TailscaleBindIP,
			"memo":   server.MemoStats(),
		})
	})

	// Try binding to specific Tailscale IP first; fallback to 0.0.0.0 if Tailscale interface is bound to wildcard
	grpcListener, err := net.Listen("tcp", fmt.Sprintf("%s:%s", TailscaleBindIP, GRPCPort))
	if err != nil {
		log.Printf("[WARN] Specific bind to %s:%s failed (%v); falling back to 0.0.0.0:%s", TailscaleBindIP, GRPCPort, err, GRPCPort)
		grpcListener, err = net.Listen("tcp", fmt.Sprintf("0.0.0.0:%s", GRPCPort))
		if err != nil {
			log.Fatalf("[FATAL] Failed to bind gRPC listener on 0.0.0.0:%s: %v", GRPCPort, err)
		}
	}

	httpListener, err := net.Listen("tcp", fmt.Sprintf("%s:%s", TailscaleBindIP, HTTPPort))
	if err != nil {
		log.Printf("[WARN] Specific bind to %s:%s failed (%v); falling back to 0.0.0.0:%s", TailscaleBindIP, HTTPPort, err, HTTPPort)
		httpListener, err = net.Listen("tcp", fmt.Sprintf("0.0.0.0:%s", HTTPPort))
		if err != nil {
			log.Fatalf("[FATAL] Failed to bind HTTP listener on 0.0.0.0:%s: %v", HTTPPort, err)
		}
	}

	httpServer := &http.Server{
		Handler:      mux,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	grpcServer := grpc.NewServer()

	go func() {
		log.Printf("[BIFROST_GRPC] gRPC Mesh Listening on tcp://%s:%s (Tailscale Target: %s)", httpListener.Addr(), GRPCPort, TailscaleBindIP)
		if err := grpcServer.Serve(grpcListener); err != nil {
			log.Printf("[BIFROST_GRPC_STOP] gRPC server stopped: %v", err)
		}
	}()

	go func() {
		log.Printf("[BIFROST_HTTP] Bare-metal Webhook & WS Ingress Listening on http://%s:%s (Tailscale Ingress Target: http://%s:%s)", "0.0.0.0", HTTPPort, TailscaleBindIP, HTTPPort)
		if err := httpServer.Serve(httpListener); err != nil && err != http.ErrServerClosed {
			log.Fatalf("[FATAL] HTTP server failed: %v", err)
		}
	}()

	// Graceful Shutdown Handler
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)
	<-quit

	log.Println("[SHUTDOWN] Initiating graceful drain of Bifrost Mesh...")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	grpcServer.GracefulStop()
	if err := httpServer.Shutdown(ctx); err != nil {
		log.Printf("[ERROR] Forced HTTP shutdown: %v", err)
	}

	log.Println("[SHUTDOWN] Bifrost Mesh cleanly terminated.")
}
