// SPDX-License-Identifier: MIT

package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

type payload struct {
	Backend   string `json:"backend"`
	KnightID  string `json:"knight_id"`
	EngineCmd string `json:"engine_cmd"`
	ReturnCode int   `json:"returncode"`
	Stdout    string `json:"stdout,omitempty"`
	Stderr    string `json:"stderr,omitempty"`
	Status    string `json:"status,omitempty"`
	Error     string `json:"error,omitempty"`
	Prompt    string `json:"prompt,omitempty"`
}

func resolveCommand(engine string, prompt string) ([]string, error) {
	if strings.HasSuffix(strings.ToLower(engine), ".cmd") {
		return []string{"cmd.exe", "/c", engine, "--print", prompt}, nil
	}

	resolved, err := exec.LookPath(engine)
	if err != nil {
		return nil, err
	}
	return []string{resolved, prompt}, nil
}

func main() {
	engine := flag.String("engine", "", "harness engine command")
	prompt := flag.String("prompt", "", "prompt for harness")
	cwd := flag.String("cwd", ".", "working directory")
	timeoutSec := flag.Int("timeout-sec", 120, "timeout in seconds")
	knightID := flag.String("knight-id", "", "worker identifier")
	flag.Parse()

	out := payload{
		Backend:   "go-native-harness",
		KnightID:  *knightID,
		EngineCmd: *engine,
	}

	if strings.TrimSpace(*engine) == "" {
		out.Status = "failed"
		out.Error = "missing --engine"
		out.Prompt = *prompt
		writeJSON(out)
		return
	}

	command, err := resolveCommand(*engine, *prompt)
	if err != nil {
		out.Status = "failed"
		out.Error = err.Error()
		out.Prompt = *prompt
		writeJSON(out)
		return
	}

	absCWD, err := filepath.Abs(*cwd)
	if err != nil {
		absCWD = *cwd
	}

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(*timeoutSec)*time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, command[0], command[1:]...)
	cmd.Dir = absCWD
	cmd.Env = os.Environ()
	var stdoutBuf bytes.Buffer
	var stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	err = cmd.Run()

	if err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			out.ReturnCode = ee.ExitCode()
			out.Stdout = strings.TrimSpace(stdoutBuf.String())
			out.Stderr = strings.TrimSpace(stderrBuf.String())
			writeJSON(out)
			return
		}

		out.Status = "failed"
		out.Error = err.Error()
		out.Prompt = *prompt
		writeJSON(out)
		return
	}

	out.ReturnCode = 0
	out.Stdout = strings.TrimSpace(stdoutBuf.String())
	out.Stderr = strings.TrimSpace(stderrBuf.String())
	writeJSON(out)
}

func writeJSON(p payload) {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(p)
}
