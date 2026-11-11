// SPDX-License-Identifier: MIT
// Camelot-OS Kernel Micro-Benchmark: Go Runtime Performance
// Evaluates:
// 1. Bitwise LCG XOR throughput (acc += uint64(i) ^ 0x5DEECE66D)
// 2. Vector Dot Product on Float32 slices (SIMD vs SSA compilation)

package benchmark

import (
	"fmt"
	"testing"
	"time"
)

var sink uint64
var floatSink float32

// Task 1: Bitwise LCG XOR Loop (Exact User Specification)
func BenchmarkThroughput(b *testing.B) {
	b.ReportAllocs()
	b.ResetTimer()

	var acc uint64
	for i := 0; i < b.N; i++ {
		acc += uint64(i) ^ 0x5DEECE66D
	}
	sink = acc
}

// Task 2: Vector Dot Product (1,000,000 elements)
func BenchmarkVectorDotProduct(b *testing.B) {
	const n = 1_000_000
	vecA := make([]float32, n)
	vecB := make([]float32, n)
	for i := 0; i < n; i++ {
		vecA[i] = float32(i) * 0.001
		vecB[i] = float32(i%100) * 0.01
	}

	b.ReportAllocs()
	b.ResetTimer()

	for iter := 0; iter < b.N; iter++ {
		var dot float32
		for i := 0; i < n; i++ {
			dot += vecA[i] * vecB[i]
		}
		floatSink = dot
	}
}

// Standalone runner for deterministic comparative metrics
func TestRunComparativeKernelBenchmarks(t *testing.T) {
	const xorIterations = 100_000_000
	t.Log("=== GO KERNEL BENCHMARK (go1.23.4 windows/amd64) ===")

	// 1. XOR Throughput
	start := time.Now()
	var acc uint64
	for i := 0; i < xorIterations; i++ {
		acc += uint64(i) ^ 0x5DEECE66D
	}
	elapsedXor := time.Since(start)
	sink = acc
	nsPerOpXor := float64(elapsedXor.Nanoseconds()) / float64(xorIterations)
	mopsXor := float64(xorIterations) / elapsedXor.Seconds() / 1_000_000

	fmt.Printf("[GO] Task 1 (XOR 100M ops): %v | %.3f ns/op | %.2f MOps/sec | sink=%d\n",
		elapsedXor, nsPerOpXor, mopsXor, sink)

	// 2. Vector Dot Product (10M ops)
	const vecSize = 10_000_000
	vecA := make([]float32, vecSize)
	vecB := make([]float32, vecSize)
	for i := 0; i < vecSize; i++ {
		vecA[i] = float32(i) * 0.0001
		vecB[i] = float32(i%100) * 0.01
	}

	startVec := time.Now()
	var dot float32
	for i := 0; i < vecSize; i++ {
		dot += vecA[i] * vecB[i]
	}
	elapsedVec := time.Since(startVec)
	floatSink = dot
	nsPerElem := float64(elapsedVec.Nanoseconds()) / float64(vecSize)
	mopsVec := float64(vecSize) / elapsedVec.Seconds() / 1_000_000

	fmt.Printf("[GO] Task 2 (Dot Product 10M f32): %v | %.3f ns/elem | %.2f MElem/sec | dot=%f\n",
		elapsedVec, nsPerElem, mopsVec, floatSink)
}
