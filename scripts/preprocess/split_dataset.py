"""
scripts/preprocess/split_dataset.py
----------------------------------
Strict identity-level dataset partitioner for ASTCV.

Guarantees 0% identity leakage: the exact same person / subject ID
never appears across multiple splits (train, val, test).

Features:
- Multi-identity handling via Union-Find (groups connected source & target identities for deepfakes)
- Graph collapse detector (warns if a dataset must use official benchmark split files)
- Strict verification: fails immediately if any sample lacks identity metadata
- Global sample_id uniqueness assertion
- Non-empty split assertions
- Label distribution tracking with skew warnings
- Immutable manifests with embedded SHA-256 verification hash
- Refuses to overwrite existing manifests without --force flag

Owner: M3 (Aswin K N)

Usage:
    # Partition a custom dataset metadata JSON
    python scripts/preprocess/split_dataset.py --metadata data/manifests/raw_metadata.json --dataset custom_v1 --train-ratio 0.70 --val-ratio 0.15 --test-ratio 0.15

    # Verify existing split manifest for identity leakage
    python scripts/preprocess/split_dataset.py --verify data/manifests/custom_v1_splits.json
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
from typing import Any, Dict, List, Set, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("split_dataset")


def group_by_components(samples: List[Dict[str, Any]]) -> Tuple[Dict[str, List[Dict[str, Any]]], bool]:
    """
    Group samples into connected components based on multi-identity relationships
    (e.g., deepfakes linking source actor A and target actor B).

    Uses Union-Find to find disjoint connected components of identities.
    Detects if the identity graph collapses into a single giant component.

    Returns:
        (groups, collapsed): mapping of root_identity -> list of samples, and boolean collapse flag.
    """
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        root_x = find(x)
        root_y = find(y)
        if root_x != root_y:
            parent[root_x] = root_y

    for s in samples:
        # Extract identities strictly
        raw_ids = s.get("identity_ids")
        if raw_ids is None:
            single_id = s.get("identity_id")
            if single_id is None:
                raise ValueError(
                    f"Sample '{s.get('sample_id', 'UNKNOWN')}' has no 'identity_id' or 'identity_ids'. "
                    f"Cannot safely partition without identity metadata."
                )
            raw_ids = [single_id]

        normalized_ids = [str(i).strip() for i in raw_ids if str(i).strip()]
        if not normalized_ids:
            raise ValueError(f"Sample '{s.get('sample_id')}' contains empty identity identifiers.")

        s["_normalized_identities"] = normalized_ids

        # Connect all identities within this sample
        root_id = normalized_ids[0]
        for other_id in normalized_ids[1:]:
            union(root_id, other_id)

    # Group samples by the root component of their first identity
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for s in samples:
        root = find(s["_normalized_identities"][0])
        groups[root].append(s)

    # Graph collapse check: if largest group contains > 60% of all samples
    total_samples = len(samples)
    max_group_size = max(len(grp) for grp in groups.values()) if groups else 0
    collapse_ratio = max_group_size / total_samples if total_samples > 0 else 0.0
    collapsed = collapse_ratio > 0.60 and len(groups) > 1

    if collapsed:
        logger.warning(
            f"[GRAPH COLLAPSE DETECTED] Largest connected component contains {max_group_size}/{total_samples} "
            f"({collapse_ratio:.1%}) of all samples! Splitting this dataset locally will result in severe "
            f"train/test imbalance. For datasets like FF++, Celeb-DF, and DFDC, ALWAYS USE OFFICIAL SPLITS."
        )

    return groups, collapsed


def verify_split_integrity(split_manifest: Dict[str, Any]) -> bool:
    """
    Check that:
    1. Every sample has valid identity metadata.
    2. Train, val, and test partitions have 0% identity overlap (normalized strings).
    3. Sample IDs are globally unique across all partitions.
    4. No partition is empty.

    Returns:
        True if split passes all integrity assertions, False otherwise.
    """
    splits = split_manifest.get("splits", {})
    all_partitions = ["train", "val", "test"]

    for p in all_partitions:
        if p not in splits:
            logger.error(f"Missing expected partition '{p}' in split manifest.")
            return False
        if len(splits[p]) == 0:
            logger.error(f"Partition '{p}' is EMPTY! Every split must contain at least 1 sample.")
            return False

    seen_sample_ids: Set[str] = set()
    identities_by_split: Dict[str, Set[str]] = defaultdict(set)

    for split_name, items in splits.items():
        for item in items:
            # Verify sample_id
            sid = str(item.get("sample_id", "")).strip()
            if not sid:
                logger.error(f"Partition '{split_name}' contains item with missing sample_id.")
                return False
            if sid in seen_sample_ids:
                logger.error(f"DUPLICATE sample_id '{sid}' detected across splits!")
                return False
            seen_sample_ids.add(sid)

            # Verify identity
            raw_ids = item.get("identity_ids") or [item.get("identity_id")]
            valid_ids = [str(i).strip() for i in raw_ids if i is not None and str(i).strip()]
            if not valid_ids:
                logger.error(f"Sample '{sid}' in split '{split_name}' has NO valid identity IDs!")
                return False

            for i in valid_ids:
                identities_by_split[split_name].add(i)

    # Cross-check disjointness
    has_leakage = False
    for i in range(len(all_partitions)):
        for j in range(i + 1, len(all_partitions)):
            s1, s2 = all_partitions[i], all_partitions[j]
            overlap = identities_by_split[s1] & identities_by_split[s2]
            if overlap:
                logger.error(
                    f"DATA LEAKAGE DETECTED between '{s1}' and '{s2}'! "
                    f"Overlapping identities ({len(overlap)}): {sorted(list(overlap))[:5]}..."
                )
                has_leakage = True

    if not has_leakage:
        logger.info(
            f"[VERIFICATION PASSED] 0% identity leakage across all partitions ({len(seen_sample_ids)} unique samples)."
        )
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
    Partition samples by connected identity components into train, val, and test splits.
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-4, "Split ratios must sum to 1.0"
    if not samples:
        raise ValueError("Cannot partition empty samples list.")

    # 1. Group by connected components
    groups, collapsed = group_by_components(samples)
    root_keys = sorted(list(groups.keys()))

    if len(root_keys) < 3:
        raise ValueError(
            f"Only {len(root_keys)} distinct identity group(s) exist. "
            f"At least 3 distinct identity groups are required for train, val, and test splits."
        )

    rng = random.Random(seed)
    rng.shuffle(root_keys)

    n_groups = len(root_keys)
    n_train = max(1, int(round(n_groups * train_ratio)))
    n_val = max(1, int(round(n_groups * val_ratio)))

    # Ensure test gets at least 1 group
    if n_train + n_val >= n_groups:
        n_train = max(1, n_groups - 2)
        n_val = 1

    train_roots = set(root_keys[:n_train])
    val_roots = set(root_keys[n_train:n_train + n_val])
    test_roots = set(root_keys[n_train + n_val:])

    assert test_roots, "Test split has no identity groups! Adjust split ratios."

    splits: Dict[str, List[Dict[str, Any]]] = {"train": [], "val": [], "test": []}

    for root_id, sample_list in groups.items():
        if root_id in train_roots:
            target_split = "train"
        elif root_id in val_roots:
            target_split = "val"
        else:
            target_split = "test"

        for s in sample_list:
            # Store compact reference
            splits[target_split].append({
                "sample_id": str(s["sample_id"]),
                "identity_ids": s["_normalized_identities"],
                "label": s.get("label", "unknown"),
            })

    # Assert all splits are non-empty
    for p in ["train", "val", "test"]:
        if len(splits[p]) == 0:
            raise RuntimeError(f"Generated split partition '{p}' is empty!")

    # Calculate statistics and check for label skew
    stats = {}
    for p in ["train", "val", "test"]:
        labels_count = defaultdict(int)
        identities_in_p = set()
        for item in splits[p]:
            labels_count[item["label"]] += 1
            for ident in item["identity_ids"]:
                identities_in_p.add(ident)

        total_p = len(splits[p])
        stats[p] = {
            "n_samples": total_p,
            "n_identities": len(identities_in_p),
            "label_distribution": dict(labels_count),
        }

        # Check label skew
        for lbl, count in labels_count.items():
            pct = count / total_p
            if pct > 0.90 and total_p > 10:
                logger.warning(
                    f"Label skew in partition '{p}': class '{lbl}' represents {pct:.1%} of samples."
                )

    raw_manifest = {
        "dataset_metadata": {
            "seed": seed,
            "train_ratio": train_ratio,
            "val_ratio": val_ratio,
            "test_ratio": test_ratio,
            "total_samples": len(samples),
            "total_identity_groups": len(root_keys),
            "graph_collapsed": collapsed,
        },
        "statistics": stats,
        "splits": splits,
    }

    # Verify integrity before finalizing
    if not verify_split_integrity(raw_manifest):
        raise RuntimeError("Generated split manifest failed zero-leakage verification!")

    # Compute embedded SHA-256 verification hash over split content
    content_bytes = json.dumps(raw_manifest["splits"], sort_keys=True).encode("utf-8")
    verification_hash = hashlib.sha256(content_bytes).hexdigest()
    raw_manifest["dataset_metadata"]["verification_sha256"] = verification_hash

    return raw_manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ASTCV Strict Identity Split Generator & Leakage Validator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--verify", type=Path, help="Verify an existing split manifest for identity leakage.")
    parser.add_argument("--metadata", type=Path, help="JSON file containing list of samples with sample_id, identity_id/identity_ids, and label.")
    parser.add_argument("--dataset", type=str, default="custom", help="Dataset name identifier.")
    parser.add_argument("--train-ratio", type=float, default=0.70, help="Train split ratio.")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="Val split ratio.")
    parser.add_argument("--test-ratio", type=float, default=0.15, help="Test split ratio.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument("--output", type=Path, default=None, help="Output JSON path. Defaults to data/manifests/<dataset>_splits.json.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing manifest file if present.")

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

    out_path = args.output or Path(f"data/manifests/{args.dataset}_splits.json")
    if out_path.exists() and not args.force:
        logger.error(f"Output manifest already exists: {out_path}. Use --force to overwrite.")
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

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Saved verified split manifest to {out_path}")
    logger.info(f"Embedded SHA-256: {manifest['dataset_metadata']['verification_sha256']}")
    logger.info(f"Summary: {json.dumps(manifest['statistics'], indent=2)}")


if __name__ == "__main__":
    main()
