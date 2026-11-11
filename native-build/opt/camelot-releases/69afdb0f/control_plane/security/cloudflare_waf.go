package security

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/cloudflare/cloudflare-go"
)

// CloudflareEdgeAegis provides programmatic edge WAF rules and IP blocking
// governed by Sir Sentinel and the Bifrost Bridge.
type CloudflareEdgeAegis struct {
	client *cloudflare.API
	zoneID string
}

// NewCloudflareEdgeAegis initializes the Cloudflare SDK using environment variables
// following Camelot-OS Zero Secrets law (no hardcoded keys).
func NewCloudflareEdgeAegis() (*CloudflareEdgeAegis, error) {
	apiToken := os.Getenv("CLOUDFLARE_API_TOKEN")
	apiKey := os.Getenv("CLOUDFLARE_API_KEY")
	apiEmail := os.Getenv("CLOUDFLARE_API_EMAIL")
	zoneID := os.Getenv("CLOUDFLARE_ZONE_ID")

	var client *cloudflare.API
	var err error

	if apiToken != "" {
		client, err = cloudflare.NewWithAPIToken(apiToken)
	} else if apiKey != "" && apiEmail != "" {
		client, err = cloudflare.New(apiKey, apiEmail)
	} else {
		// Mock/Dry-Run Mode when tokens are unmounted locally
		log.Println("[CLOUDFLARE-AEGIS] No Cloudflare API credentials detected in environment. Operating in DRY-RUN mode.")
		return &CloudflareEdgeAegis{client: nil, zoneID: zoneID}, nil
	}

	if err != nil {
		return nil, fmt.Errorf("failed to initialize Cloudflare client: %w", err)
	}

	log.Println("🛡️ [CLOUDFLARE-AEGIS] Edge Aegis Shield active and authenticated.")
	return &CloudflareEdgeAegis{client: client, zoneID: zoneID}, nil
}

// BlockMaliciousIP creates a dynamic WAF access rule blocking an attacking IP address
// immediately at Cloudflare's global Anycast edge.
func (a *CloudflareEdgeAegis) BlockMaliciousIP(ipAddress string, reason string) error {
	if a.client == nil {
		log.Printf("[CLOUDFLARE-AEGIS:DRY-RUN] Would block malicious IP %s: %s", ipAddress, reason)
		return nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	rule := cloudflare.AccessRule{
		Mode: "block",
		Configuration: cloudflare.AccessRuleConfiguration{
			Target: "ip",
			Value:  ipAddress,
		},
		Notes: fmt.Sprintf("Camelot-OS Sir Sentinel Automated Block: %s (%s)", reason, time.Now().UTC().Format(time.RFC3339)),
	}

	res, err := a.client.CreateAccountAccessRule(ctx, a.zoneID, rule)
	if err != nil {
		return fmt.Errorf("failed to block IP %s at Cloudflare edge: %w", ipAddress, err)
	}

	log.Printf("⚡ [CLOUDFLARE-AEGIS] IP %s blocked globally at edge (Rule ID: %s)", ipAddress, res.Result.ID)
	return nil
}
