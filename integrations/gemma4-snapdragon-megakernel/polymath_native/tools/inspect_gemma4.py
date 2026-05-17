#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(spec: dict[str, Any]) -> dict[str, Any]:
    config = spec.get("hf_config_summary", {})
    text = config.get("text_config", {})
    repos = spec.get("repos", {})
    return {
        "model_name": spec.get("model_name"),
        "base_repo": repos.get("base", {}).get("id"),
        "license": spec.get("license", {}).get("spdx") or repos.get("base", {}).get("license"),
        "architecture": config.get("architectures"),
        "text": {
            "hidden_size": text.get("hidden_size"),
            "intermediate_size": text.get("intermediate_size"),
            "num_hidden_layers": text.get("num_hidden_layers"),
            "num_attention_heads": text.get("num_attention_heads"),
            "num_key_value_heads": text.get("num_key_value_heads"),
            "max_position_embeddings": text.get("max_position_embeddings"),
            "sliding_window": text.get("sliding_window"),
            "activation": text.get("hidden_activation"),
            "rms_norm_eps": text.get("rms_norm_eps"),
            "vocab_size": text.get("vocab_size"),
        },
        "trainability": spec.get("trainability", {}),
        "blockers": spec.get("blockers", []),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize a Gemma 4 model spec.")
    parser.add_argument("spec", type=Path, help="Path to model_spec JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(json.dumps(summarize(load_json(args.spec)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
