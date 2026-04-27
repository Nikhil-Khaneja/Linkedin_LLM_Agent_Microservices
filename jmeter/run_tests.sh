#!/bin/bash
set -e

API_HOST=${API_HOST:-analytics-api}
API_PORT=${API_PORT:-8000}
SCENARIO=${SCENARIO:-both}   # "A", "B", or "both"
RESULTS_DIR=/jmeter/results

mkdir -p $RESULTS_DIR

# Wait for the analytics API to be ready
echo "Waiting for analytics-api at $API_HOST:$API_PORT..."
until curl -sf "http://$API_HOST:$API_PORT/health" > /dev/null; do
  sleep 2
done
echo "Analytics API is up."

run_scenario() {
  local name=$1
  local jmx=$2
  local csv="$RESULTS_DIR/results_scenario_${name}.csv"
  local report="$RESULTS_DIR/report_scenario_${name}"

  echo ""
  echo "============================================"
  echo " Running Scenario $name: $jmx"
  echo "============================================"

  rm -rf "$report"

  jmeter -n \
    -t "/jmeter/plans/$jmx" \
    -l "$csv" \
    -e -o "$report" \
    -JHOST="$API_HOST" \
    -JPORT="$API_PORT" \
    2>&1 | grep -E "summary|Err:|error" || true

  echo "Scenario $name complete. Results: $csv"
}

if [[ "$SCENARIO" == "A" || "$SCENARIO" == "both" ]]; then
  run_scenario "A" "scenario_a_ingest.jmx"
fi

if [[ "$SCENARIO" == "B" || "$SCENARIO" == "both" ]]; then
  run_scenario "B" "scenario_b_queries.jmx"
fi

echo ""
echo "All scenarios complete. Results in $RESULTS_DIR"

# POST summary to benchmarks endpoint
if [[ "$SCENARIO" == "A" || "$SCENARIO" == "both" ]]; then
  curl -sf -X POST "http://$API_HOST:$API_PORT/benchmarks/report" \
    -H "Content-Type: application/json" \
    -d '{
      "scenario":"A","owner_id":"owner7","service_name":"analytics-service",
      "results":{"source":"jmeter-docker","status":"completed"},
      "metadata":{"report_path":"/jmeter/results/report_scenario_A"}
    }' && echo "Scenario A benchmark stored." || true
fi

if [[ "$SCENARIO" == "B" || "$SCENARIO" == "both" ]]; then
  curl -sf -X POST "http://$API_HOST:$API_PORT/benchmarks/report" \
    -H "Content-Type: application/json" \
    -d '{
      "scenario":"B","owner_id":"owner7","service_name":"analytics-service",
      "results":{"source":"jmeter-docker","status":"completed"},
      "metadata":{"report_path":"/jmeter/results/report_scenario_B"}
    }' && echo "Scenario B benchmark stored." || true
fi
