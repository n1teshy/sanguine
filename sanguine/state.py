import json
import os

from sanguine.utils import app_dir

counter_file = os.path.join(app_dir, "state.json")

COUNTER = "counter"
HNSW_STALE_ENCOUNTERS = "hnsw_stale_encounters"
HNSW_TOTAL_ENCOUNTERS = "hnsw_total_encounters"

state = {COUNTER: 0, HNSW_STALE_ENCOUNTERS: 0, HNSW_TOTAL_ENCOUNTERS: 0}

if not os.path.isfile(counter_file):
    with open(counter_file, "w") as f:
        json.dump(state, f)
else:
    with open(counter_file) as f:
        state = json.load(f)


def save():
    with open(counter_file, "w") as f:
        json.dump(state, f)


def update_counter():
    state[COUNTER] += 1
    save()


def get_counter() -> int:
    return state[COUNTER]


def update_staleness(total: int, stale: int):
    state[HNSW_TOTAL_ENCOUNTERS] += total
    state[HNSW_STALE_ENCOUNTERS] += stale
    save()


def reset_staleness_metrics():
    state[HNSW_TOTAL_ENCOUNTERS] = 0
    state[HNSW_STALE_ENCOUNTERS] = 0
    save()


def get_staleness() -> float:
    return state[HNSW_STALE_ENCOUNTERS] / state[HNSW_TOTAL_ENCOUNTERS]
