"""
Proof that our hand-written FP-Growth is correct.

Run it with:   python test_fpgrowth.py

Test 1: the textbook example, checked against numbers you can count by hand.
Test 2: 300 random baskets, compared against brute force (try EVERY subset).
Test 3: same data compared against the mlxtend library, if installed.

When a professor asks "how do you know your miner works?", you show this file.
"""
from __future__ import annotations

import random
from itertools import combinations

from fpgrowth import frequent_itemsets, association_rules

TEXTBOOK = [
    ["bread", "milk"],
    ["bread", "diaper", "beer", "eggs"],
    ["milk", "diaper", "beer", "cola"],
    ["bread", "milk", "diaper", "beer"],
    ["bread", "milk", "diaper", "cola"],
]


def brute_force(transactions, min_count):
    """The slow, obviously-correct way: test every possible combination."""
    items = sorted({i for t in transactions for i in t})
    sets_as = [set(t) for t in transactions]
    found = {}
    for k in range(1, len(items) + 1):
        for combo in combinations(items, k):
            c = sum(1 for t in sets_as if set(combo) <= t)
            if c >= min_count:
                found[frozenset(combo)] = c
    return found


def test_textbook():
    got, n = frequent_itemsets(TEXTBOOK, min_count=3)
    assert n == 5
    assert got[frozenset({"bread"})] == 4
    assert got[frozenset({"milk"})] == 4
    assert got[frozenset({"diaper"})] == 4
    assert got[frozenset({"beer"})] == 3
    assert got[frozenset({"diaper", "beer"})] == 3
    assert frozenset({"eggs"}) not in got          # appears once, must be dropped
    print("PASS test_textbook            ", len(got), "itemsets")


def test_against_brute_force():
    random.seed(7)
    pool = [f"topic{i}" for i in range(12)]
    tx = [random.sample(pool, random.randint(2, 6)) for _ in range(300)]
    for min_count in (5, 15, 40):
        mine, _ = frequent_itemsets(tx, min_count=min_count)
        ref = brute_force(tx, min_count)
        assert mine == ref, f"mismatch at min_count={min_count}"
        print(f"PASS brute force min_count={min_count:<3}", len(ref), "itemsets identical")
    return tx


def test_against_mlxtend(tx):
    try:
        import pandas as pd
        from mlxtend.frequent_patterns import fpgrowth as mlx_fp
        from mlxtend.preprocessing import TransactionEncoder
    except ModuleNotFoundError:
        print("SKIP mlxtend not installed (pip install mlxtend to run this one)")
        return
    enc = TransactionEncoder()
    df = pd.DataFrame(enc.fit(tx).transform(tx), columns=enc.columns_)
    theirs = mlx_fp(df, min_support=15 / len(tx), use_colnames=True)
    theirs_d = {frozenset(r.itemsets): round(r.support * len(tx)) for r in theirs.itertuples()}
    ours, _ = frequent_itemsets(tx, min_count=15)
    assert ours == theirs_d, "our miner disagrees with mlxtend"
    print("PASS mlxtend agreement        ", len(ours), "itemsets identical")


def test_rules():
    itemsets, n = frequent_itemsets(TEXTBOOK, min_count=3)
    rules = association_rules(itemsets, n, min_confidence=0.6)
    got = {(r["antecedent"], r["consequent"]): r for r in rules}
    r = got[("beer", "diaper")]
    assert abs(r["confidence"] - 1.0) < 1e-9      # all 3 beer baskets have diapers
    assert abs(r["lift"] - 1.25) < 1e-9           # 1.0 / (4/5)
    print("PASS test_rules               ", len(rules), "rules")


if __name__ == "__main__":
    test_textbook()
    tx = test_against_brute_force()
    test_against_mlxtend(tx)
    test_rules()
    print("\nAll tests passed.")
