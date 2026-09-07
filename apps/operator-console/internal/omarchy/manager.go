package omarchy

import (
	"fmt"
	"math/rand"
	"os/exec"
	"strings"
	"time"
)

type SliceHealth struct {
	Name      string `json:"name"`
	MemoryUse string `json:"memory_use"`
	Tasks     string `json:"tasks"`
	Status    string `json:"status"`
}

// GetHealth returns the hardware health metrics and cgroup slice statuses.
// It attempts to run systemctl, but falls back to simulated metrics if run outside 
// a native systemd Linux environment (e.g. in the preview sandbox).
func GetHealth() []SliceHealth {
	slices := []string{
		"camelot-critical.slice",
		"camelot-control.slice",
		"camelot-data.slice",
		"camelot-workers.slice",
	}

	var results []SliceHealth

	for _, s := range slices {
		// Attempt to get actual MemoryCurrent via systemctl
		cmd := exec.Command("systemctl", "show", s, "-p", "MemoryCurrent")
		out, err := cmd.Output()
		
		var mem string
		var tasks string
		var status string
		
		if err != nil || len(out) == 0 || strings.Contains(string(out), "[not set]") {
			// Mock data for preview environment where systemctl isn't present
			r := rand.New(rand.NewSource(time.Now().UnixNano()))
			memVal := r.Intn(400) + 100 // 100MB - 500MB
			mem = fmt.Sprintf("%d MB", memVal)
			tasks = fmt.Sprintf("%d", r.Intn(50)+5)
			status = "HEALTHY (Mock)"
			if memVal > 450 {
				status = "WARNING: GC PRESSURE"
			}
		} else {
			// Parse systemctl output
			raw := strings.TrimSpace(strings.TrimPrefix(string(out), "MemoryCurrent="))
			mem = fmt.Sprintf("%s bytes", raw)
			
			// Tasks
			tcmd := exec.Command("systemctl", "show", s, "-p", "TasksCurrent")
			tout, _ := tcmd.Output()
			tasks = strings.TrimSpace(strings.TrimPrefix(string(tout), "TasksCurrent="))
			status = "ACTIVE"
		}

		results = append(results, SliceHealth{
			Name:      s,
			MemoryUse: mem,
			Tasks:     tasks,
			Status:    status,
		})
	}

	return results
}
