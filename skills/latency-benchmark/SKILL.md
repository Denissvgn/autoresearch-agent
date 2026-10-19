# Latency Minimization Benchmark

You are a **measured latency minimization agent**. Your goal is to improve a
loopback query service's latency through a real implementation change and have
the improvement qualified by measured evidence — never by synthetic scores.

## The frozen workload

The workload is fixed before any comparison and packaged in the skill
directory's `workload.json`: a dataset of key/value pairs and a frozen request
mix (a seeded key sequence). The protocol is likewise frozen: warmup count,
repeat count, request count per repeat, the target percentile (p95), the
resource envelope, guardrails (error rate, throughput floor), the uncertainty
bound, and the minimum improvement. **Do not change the workload or the
protocol between the baseline and candidate runs** — their digests must match,
or the samples are incomparable and cannot win.

## How a measurement run works

1. The service under test is an agent-owned loopback HTTP server implementing
   `GET /query?key=...` over the skill's dataset.
2. Run the measurement procedure with the frozen protocol. The real
   implementation answers every request; there is no `sleep`-based scoring
   anywhere — a score inflated by synthetic delay is invalid evidence.
3. Record the measurement to the store. The record carries the immutable
   evaluation-context identity (protocol digest + workload digest + mode) and
   the **environment limits**: all results are machine- and load-specific.

## Qualification rules (lower is better)

A candidate becomes the minimization winner only when all of the following
pass: identical evaluation context, all repeats complete, uncertainty within
the bound (noisy samples never win), no resource contention detected during
the run, guardrails satisfied (zero errors, throughput floor), and the median
p95 improvement above the minimum. Anything else is a non-result with a
reason — never a production winner.

## Simulated scores are a separate mode

Sleep-based or simulated scoring is a **separately labeled mode**. Simulated
results are never comparable with measured results and can never promote a
winner through the measured pipeline.
