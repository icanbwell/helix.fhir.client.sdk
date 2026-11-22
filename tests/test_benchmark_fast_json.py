"""
Benchmarks for fast_json against the standard library on synthetic Bundles (no PHI).

Run on Python 3.12 (CI and the floor) inside the dev container:
    docker compose run --rm dev pytest tests/test_benchmark_fast_json.py --benchmark-only --benchmark-group-by=param:entries
"""

import json
from typing import Any

import pytest
from compressedfhir.utilities.fhir_json_encoder import FhirJSONEncoder

from helix_fhir_client_sdk.utilities.fast_json import dumps_str, loads


def _bundle(entries: int) -> dict[str, Any]:
    # Object-heavy (short keys and values), which is the low end of the speed-up: dumps about 4x, loads about 1.5x.
    # String- and number-heavy bundles (narrative text, float arrays) reach 6 to 9x for dumps.
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": f"obs-{i}",
                    "status": "final",
                    "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}]},
                    "subject": {"reference": f"Patient/{i}"},
                    "valueQuantity": {"value": 60 + (i % 40), "unit": "/min", "system": "http://unitsofmeasure.org"},
                    "note": [{"text": "Synthetic note with non-ASCII Zoë 日本語"}],
                }
            }
            for i in range(entries)
        ],
    }


@pytest.mark.parametrize("entries", [100, 1000, 10000])
@pytest.mark.parametrize("backend", ["stdlib", "fast_json"])
def test_benchmark_dumps(benchmark: Any, entries: int, backend: str) -> None:
    bundle = _bundle(entries)
    fn = (lambda: json.dumps(bundle, cls=FhirJSONEncoder)) if backend == "stdlib" else (lambda: dumps_str(bundle))

    result = benchmark.pedantic(fn, rounds=5, iterations=1, warmup_rounds=1)

    assert json.loads(result)["resourceType"] == "Bundle"


@pytest.mark.parametrize("entries", [100, 1000, 10000])
@pytest.mark.parametrize("backend", ["stdlib", "fast_json"])
def test_benchmark_loads(benchmark: Any, entries: int, backend: str) -> None:
    text = json.dumps(_bundle(entries))
    fn = (lambda: json.loads(text)) if backend == "stdlib" else (lambda: loads(text))

    result = benchmark.pedantic(fn, rounds=5, iterations=1, warmup_rounds=1)

    assert len(result["entry"]) == entries
