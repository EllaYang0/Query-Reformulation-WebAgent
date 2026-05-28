"""
hotpotqa.py - HotpotQA loader.
"""

import random
from datasets import load_dataset


def load_hotpotqa(num_samples=None, seed=42, level="hard", q_type=None):
    print("📥 Loading HotpotQA dataset...")
    dataset = load_dataset("hotpot_qa", "fullwiki", split="validation", trust_remote_code=True)
    print(f"📄 Loaded {len(dataset)} questions")

    items = []
    for item in dataset:
        if level and item["level"] != level:
            continue
        if q_type and item["type"] != q_type:
            continue
        items.append({
            "question": item["question"],
            "answer": item["answer"],
            "type": item["type"],
            "level": item["level"],
        })

    print(f"🔍 Filtered to {len(items)} questions (level={level}, type={q_type or 'all'})")

    if num_samples and num_samples < len(items):
        rng = random.Random(seed)
        items = rng.sample(items, num_samples)
        print(f"🎲 Sampled {num_samples} questions (seed={seed})")

    return items
