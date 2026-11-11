// SPDX-License-Identifier: MIT

package main

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestAuroraAccountPoolAndRotation(t *testing.T) {
	a1 := NewAuroraAccount("acct-1", AuroraAccountTypeFree, "token-1")
	a1.Status = AuroraStatusActive
	a2 := NewAuroraAccount("acct-2", AuroraAccountTypeFree, "token-2")
	a2.Status = AuroraStatusActive

	pool := NewAuroraPool([]*AuroraAccount{a1, a2})

	acct1, err := pool.Acquire(AuroraAccountTypeFree)
	if err != nil || acct1.ID != "acct-1" {
		t.Fatalf("expected acct-1, got %v (err: %v)", acct1, err)
	}

	acct2, err := pool.Acquire(AuroraAccountTypeFree)
	if err != nil || acct2.ID != "acct-2" {
		t.Fatalf("expected acct-2, got %v (err: %v)", acct2, err)
	}

	// Wraps around
	acct3, err := pool.Acquire(AuroraAccountTypeFree)
	if err != nil || acct3.ID != "acct-1" {
		t.Fatalf("expected acct-1 wrap, got %v (err: %v)", acct3, err)
	}
}

func TestAuroraSessionHealthCheckAndAutoRenew(t *testing.T) {
	a1 := NewAuroraAccount("acct-1", AuroraAccountTypeFree, "token-1")
	a1.Status = AuroraStatusActive

	pool := NewAuroraPool([]*AuroraAccount{a1})
	pool.ReportFailure(a1)

	if a1.Status != AuroraStatusExpired {
		t.Fatalf("expected status expired after report failure, got %v", a1.Status)
	}

	// Health check with renewer
	renewed := pool.RunHealthCheck(func(acct *AuroraAccount) bool {
		return acct.ID == "acct-1"
	})

	if renewed != 1 {
		t.Fatalf("expected 1 account renewed, got %d", renewed)
	}
	if a1.Status != AuroraStatusActive {
		t.Fatalf("expected status active after renewal, got %v", a1.Status)
	}
}

func TestAuroraToolCallInstructionAndPromptBuilder(t *testing.T) {
	tools := []AuroraTool{
		{
			Type: "function",
			Function: AuroraToolFunction{
				Name:        "execute_command",
				Description: "Run shell command",
				Parameters:  json.RawMessage(`{"type":"object","properties":{"command":{"type":"string","description":"Command to run"}},"required":["command"]}`),
			},
		},
	}
	choice := &AuroraToolChoice{
		Type: "function",
	}
	choice.Function.Name = "execute_command"

	instructions := BuildAuroraToolInstructions(tools, choice)
	if !strings.Contains(instructions, "# TOOLS AVAILABLE") {
		t.Fatalf("missing TOOLS AVAILABLE in instructions")
	}
	if !strings.Contains(instructions, "execute_command") {
		t.Fatalf("missing tool name in instructions")
	}
	if !strings.Contains(instructions, "<tool_call>") {
		t.Fatalf("missing <tool_call> in instructions")
	}
}

func TestAuroraStreamParser(t *testing.T) {
	parser := NewAuroraToolCallParser()
	chunk1 := "Thinking about next action...\n<tool_call>\n{\"name\": \"execute_command\", \"arguments\": {\"command\": \"dir\"}}"
	text1, calls1 := parser.Feed(chunk1)
	if !strings.Contains(text1, "Thinking about next action...") {
		t.Fatalf("expected text output in chunk1, got %q", text1)
	}
	if len(calls1) != 0 {
		t.Fatalf("expected 0 tool calls before closing tag, got %d", len(calls1))
	}

	chunk2 := "\n</tool_call>\nFinishing up."
	text2, calls2 := parser.Feed(chunk2)
	if len(calls2) != 1 {
		t.Fatalf("expected 1 tool call after closing tag, got %d", len(calls2))
	}
	if calls2[0].Function.Name != "execute_command" {
		t.Fatalf("expected function name execute_command, got %s", calls2[0].Function.Name)
	}
	if !strings.Contains(text2, "Finishing up.") {
		t.Fatalf("expected trailing text, got %q", text2)
	}
}

func TestAuroraRecoverFromText(t *testing.T) {
	rawText := `I will execute this: {"name": "read_file", "arguments": {"path": "C:\\test\\file.txt"}}`
	recovered := RecoverAuroraToolCallsFromText(rawText, "read_file", "path")
	if len(recovered) != 1 {
		t.Fatalf("expected 1 recovered tool call, got %d", len(recovered))
	}
	if recovered[0].Function.Name != "read_file" {
		t.Fatalf("expected read_file, got %s", recovered[0].Function.Name)
	}
}
