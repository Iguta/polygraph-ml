# Benchmark results

`latest.json` is captured from the deterministic fixture release gate:

```bash
uv run polygraphml-benchmarks --output benchmark-results/latest.json
```

The campaign case is a declared multi-mechanism synthetic failure. The UCI COVID-19 Surveillance case is a public CC BY 4.0 clean control paired with a generated safe model and notebook. Fixture runs make no OpenAI request, so token and cost fields are explicitly zero; live-agent measurements are a separate release artifact.

`queue-timing.json` is derived from the captured per-case durations:

```bash
make calibrate-queue
```

It proves the configured timeout and heartbeat cover the fixture measurement, but deliberately reports `production_calibrated: false`. The separate `queue-timing-live.json` records the completed 20-run deployed-live calibration (P95 32.666 seconds; configured 300-second visibility and 60-second heartbeat exceed the 161-second recommendation).

After `OPENAI_API_KEY` is configured, the metadata-only live evidence command is:

```bash
make live-smoke
```

The resulting `live-trace.json` excludes event payloads, prompts, raw data, reasoning text, and chain-of-thought. The public-path evidence files `deployed-smoke.json`, `cold-start-smoke.json`, and `resilience-drill.json` are likewise metadata-only. Commit them only after manual inspection.
