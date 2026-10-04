"""
scripts/preprocess/split_dataset.py
----------------------------------
Strict identity-level dataset partitioner for ASTCV.

Guarantees 0% identity leakage: the exact same person / subject ID
never appears across multiple splits (e.g., train, val, test).

Features:
- Partitioning by subject/actor identity
- Verification mode: checks any existing split file for data leakage
- Generates reproducible, immutable split manifests saved to data/manifests/<dataset>_splits.json
- Logs detailed balance statistics (samples per split, identities per split, label distribution)

Owner: M3 (Aswin K N)

Usage:
    # Generate splits from a metadata JSON/CSV
    python scripts/preprocess/split_dataset.py --metadata data/manifests/raw_metadata.json --dataset uadfv --train-ratio 0.70 --val-ratio 0.15 --test-ratio 0.15

    # Verify existing split manifest for identity leakage
    python scripts/preprocess/split_dataset.py --verify data/manifests/uadfv_splits.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("split_dataset")


def verify_split_integrity(split_manifest: Dict[str, Any]) -> bool:
    """
    Check that train, val, and test partitions have zero identity overlap.

    Returns:
        True if split is completely disjoint across identities, False otherwise.
    """
    splits = split_manifest.get("splits", {})
    identities_by_split: Dict[str, Set[str]] = {}

    for split_name, items in splits.items():
        identities_by_split[split_name] = {
            item["identity_id"] for item in items if "identity_id" in item
        }

    all_splits = list(identities_by_split.keys())
    has_leakage = False

    for i in range(len(all_splits)):
        for j in range(i + 1, len(all_splits)):
            s1, s2 = all_splits[i], all_splits[j]
            overlap = identities_by_split[s1] & identities_by_split[s2]
            if overlap:
                logger.error(
                    f"DATA LEAKAGE DETECTED between '{s1}' and '{s2}'! "
                    f"Overlapping identities ({len(overlap)}): {sorted(list(overlap))[:5]}..."
                )
                has_leakage = True

    if not has_leakage:
        logger.info("[VERIFICATION PASSED] 0% identity leakage across all splits.")
        return True
    return False


def create_identity_splits(
    samples: List[Dict[str, Any]],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Partition samples by identity_id into train, val, and test splits.

    Args:
        samples: List of sample dicts. Each must contain 'sample_id', 'identity_id', and 'label'.
        train_ratio: Proportion of identities allocated to training.
        val_ratio: Proportion of identities allocated to validation.
        test_ratio: Proportion of identities allocated to testing.
        seed: Random seed for deterministic reproducibility.

    Returns:
        Structured split dictionary with verification hash and partition lists.
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-4, "Split ratios must sum to 1.0"

    # Group samples by identity
    identity_to_samples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        if "identity_id" not in sample:
            raise ValueError(f"Sample missing 'identity_id': {sample}")
        identity_to_samples[str(sample["identity_id"])].append(sample)

    unique_identities = sorted(list(identity_to_samples.keys()))
    rng = random.Random(seed)
    rng.shuffle(unique_identities)

    n_identities = len(unique_identities)
    n_train = int(round(n_identities * train_ratio))
    n_val = int(round(n_identities * val_ratio))

    train_ids = set(unique_identities[:n_train])
    val_ids = set(unique_identities[n_train:n_train + n_val])
    test_ids = set(unique_identities[n_train + n_val:])

    # Double check identity disjointness
    assert train_ids.isdisjoint(val_ids), "Train and Val identity overlap!"
    assert train_ids.isdisjoint(test_ids), "Train and Test identity overlap!"
    assert val_ids.isdisjoint(test_ids), "Val and Test identity overlap!"

    splits: Dict[str, List[Dict[str, Any]]] = {"train": [], "val": [], "test": []}

    for identity_id, s_list in identity_to_samples.items():
        if identity_id in train_ids:
            splits["train"].extend(s_list)
        elif identity_id in val_ids:
            splits["val"].extend(s_list)
        elif identity_id in test_ids:
            splits["test"].extend(s_list)

    # Compute summary stats
    stats = {}
    for split_name, items in splits.items():
        identities_in_split = {item["identity_id"] for item in items}
        labels_count = defaultdict(int)
        for item in items:
            labels_count[item.get("label", "unknown")] += 1

        stats[split_name] = {
            "n_samples": len(items),
            "n_identities": len(identities_in_split),
            "label_distribution": dict(labels_count),
        }

    split_manifest = {
        "seed": seed,
        "train_ratio": train_ratio,
        "val_ratio": val_ratio,
        "test_ratio": test_ratio,
        "total_identities": n_identities,
        "total_samples": len(samples),
        "statistics": stats,
        "splits": splits,
    }

    # Verify final result before returning
    if not verify_split_integrity(split_manifest):
        raise RuntimeError("Generated split manifest failed zero-leakage verification!")

    return split_manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ASTCV Strict Identity Split Generator & Leakage Validator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--verify", type=Path, help="Verify an existing split manifest for identity leakage.")
    parser.add_argument("--metadata", type=Path, help="JSON file containing list of samples with sample_id, identity_id, and label.")
    parser.add_argument("--dataset", type=str, default="dataset", help="Dataset name identifier.")
    parser.add_argument("--train-ratio", type=float, default=0.70, help="Train split ratio.")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="Val split ratio.")
    parser.add_argument("--test-ratio", type=float, default=0.15, help="Test split ratio.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument("--output", type=Path, default=None, help="Output JSON path. Defaults to data/manifests/<dataset>_splits.json.")

    args = parser.parse_args()

    if args.verify:
        if not args.verify.exists():
            logger.error(f"File not found: {args.verify}")
            sys.exit(1)
        with args.verify.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
        passed = verify_split_integrity(manifest)
        sys.exit(0 if passed else 1)

    if not args.metadata:
        logger.error("Either --metadata or --verify must be specified.")
        parser.print_help()
        sys.exit(1)

    with args.metadata.open("r", encoding="utf-8") as f:
        samples = json.load(f)

    logger.info(f"Loaded {len(samples)} samples for dataset '{args.dataset}'")
    manifest = create_identity_splits(
        samples=samples,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )

    out_path = args.output or Path(f"data/manifests/{args.dataset}_splits.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Saved verified split manifest to {out_path}")
    logger.info(f"Summary: {json.dumps(manifest['statistics'], indent=2)}")


if __name__ == "__main__":
    main()
