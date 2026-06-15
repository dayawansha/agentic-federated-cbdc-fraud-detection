#!/usr/bin/env python3
import argparse
import base64
import json
import urllib.request
from pathlib import Path


def _read_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")

def _post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))

def _print_summary(report: dict) -> None:
    if "results" not in report:
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    print(json.dumps(report, indent=2, sort_keys=True))
    print("\nprivacy_sweep_summary:")
    best_privacy = min(report["results"], key=lambda item: item.get("leakage_proxy_score", 1.0))
    best_utility = max(report["results"], key=lambda item: item.get("tensor_cosine_similarity", 0.0))
    print(
        json.dumps(
            {
                "lowest_leakage_proxy_noise_multiplier": best_privacy.get("noise_multiplier"),
                "lowest_leakage_proxy_score": best_privacy.get("leakage_proxy_score"),
                "lowest_leakage_risk_level": best_privacy.get("leakage_risk_level"),
                "highest_cosine_similarity_noise_multiplier": best_utility.get("noise_multiplier"),
                "highest_cosine_similarity": best_utility.get("tensor_cosine_similarity"),
            },
            indent=2,
            sort_keys=True,
        )
    )

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a privacy evaluation report from raw/protected/encrypted model payloads.")
    parser.add_argument("--privacy-url", default="http://localhost:9003", help="Base URL for the privacy-layer service")
    parser.add_argument("--raw", required=True, help="Path to raw model weights file")
    parser.add_argument("--protected", help="Path to privacy-protected model weights file")
    parser.add_argument("--encrypted", help="Path to encrypted model payload file")
    parser.add_argument("--noise-multiplier", type=float, default=0.01, help="Noise multiplier used during privacy processing")
    parser.add_argument("--noise-sweep", help="Comma-separated list of noise multipliers for comparative privacy experiments")
    parser.add_argument("--no-encrypt", action="store_true", help="Skip encryption during privacy sweep experiments")
    args = parser.parse_args()

    raw_weights = _read_base64(Path(args.raw))
    if args.noise_sweep:
        noise_multipliers = [float(item.strip()) for item in args.noise_sweep.split(",") if item.strip()]
        report = _post_json(
            f"{args.privacy_url.rstrip('/')}/privacy/evaluate/sweep",
            {
                "raw_weights": raw_weights,
                "noise_multipliers": noise_multipliers,
                "encrypt_payloads": not args.no_encrypt,
            },
        )
        _print_summary(report)
        return 0

    if not args.protected:
        raise SystemExit("--protected is required when --noise-sweep is not used")

    report = _post_json(
        f"{args.privacy_url.rstrip('/')}/privacy/evaluate",
        {
            "raw_weights": raw_weights,
            "protected_weights": _read_base64(Path(args.protected)),
            "encrypted_data": _read_base64(Path(args.encrypted)) if args.encrypted else "",
            "noise_multiplier": float(args.noise_multiplier),
        },
    )
    _print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
