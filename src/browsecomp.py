"""
browsecomp.py - BrowseComp dataset loader.
"""

import base64
import hashlib
import random
import pandas as pd

DATASET_URL = "https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv"


def _derive_key(password, length):
    hasher = hashlib.sha256()
    hasher.update(password.encode())
    key = hasher.digest()
    return (key * (length // len(key) + 1))[:length]


def _decrypt(ciphertext_b64, password):
    encrypted = base64.b64decode(ciphertext_b64)
    key = _derive_key(password, len(encrypted))
    return bytes(a ^ b for a, b in zip(encrypted, key)).decode("utf-8")


def load_browsecomp(num_samples=None, seed=42):
    print("📥 Downloading BrowseComp dataset...")
    df = pd.read_csv(DATASET_URL)
    print(f"📄 Loaded {len(df)} encrypted entries")

    decrypted = []
    for _, row in df.iterrows():
        try:
            question = _decrypt(row["problem"], row["canary"])
            answer = _decrypt(row["answer"], row["canary"])
            if question and answer:
                decrypted.append({"question": question, "answer": answer})
        except Exception:
            continue

    print(f"🔓 Decrypted {len(decrypted)} questions")

    if num_samples and num_samples < len(decrypted):
        rng = random.Random(seed)
        decrypted = rng.sample(decrypted, num_samples)
        print(f"🎲 Sampled {num_samples} questions (seed={seed})")

    return decrypted
