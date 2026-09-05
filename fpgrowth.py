"""
FP-Growth, written by hand.

WHY BY HAND?
------------
There is a library (mlxtend) that does this in one line. We implement it
ourselves for two reasons:
  1. Building the algorithm rather than calling it is the point of the
     exercise; a one-line import demonstrates nothing about the method.
  2. test_fpgrowth.py proves our version gives byte-identical answers to a
     brute-force search and to mlxtend. That test file is your evidence.

VOCABULARY (in our project)
---------------------------
  transaction / basket = one research paper
  item                 = one topic on that paper
  support of a set      = fraction of papers containing ALL topics in the set
  frequent itemset      = a topic combination whose support >= min_support
"""
from __future__ import annotations

from collections import defaultdict
from math import ceil


class FPNode:
    """One node of the FP-tree. Holds an item and how many baskets pass through."""

    __slots__ = ("item", "count", "parent", "children", "link")

    def __init__(self, item, count, parent):
        self.item = item
        self.count = count
        self.parent = parent
        self.children = {}
        self.link = None      # next node holding the SAME item, elsewhere in tree


def _build_tree(weighted_tx, min_count):
    """
    Build an FP-tree from (items, weight) pairs.

    Pass 1: count every item, throw away the rare ones.
    Pass 2: insert each basket, most-frequent item first, sharing prefixes.
    Sharing prefixes is what makes the tree small -- that is the whole trick.
    """
    counts = defaultdict(int)
    for items, w in weighted_tx:
        for it in items:
            counts[it] += w

    freq = {i: c for i, c in counts.items() if c >= min_count}
    if not freq:
        return None, None

    # descending count, then alphabetical, so results are reproducible
    order = sorted(freq, key=lambda i: (-freq[i], i))
    rank = {it: k for k, it in enumerate(order)}

    root = FPNode(None, 0, None)
    header = {it: [freq[it], None] for it in order}

    for items, w in weighted_tx:
        selected = sorted((it for it in items if it in freq), key=lambda it: rank[it])
        node = root
        for it in selected:
            child = node.children.get(it)
            if child is None:
                child = FPNode(it, 0, node)
                node.children[it] = child
                child.link = header[it][1]   # push onto this item's linked list
                header[it][1] = child
            child.count += w
            node = child

    return root, header

def _mine(header, prefix, min_count, out, max_len):
    """
    Grow patterns from the tree, rarest item first.

    For each item we collect its "conditional pattern base": every path from
    that item up to the root, weighted by how many baskets used that path.
    That base is itself a smaller transaction set, so we recurse on it.
    """
    for item in sorted(header, key=lambda i: (header[i][0], i)):
        support_count, node = header[item][0], header[item][1]
        new_prefix = prefix | {item}
        out[frozenset(new_prefix)] = support_count

        if max_len is not None and len(new_prefix) >= max_len:
            continue

        cond_base = []
        while node is not None:
            path, p = [], node.parent
            while p is not None and p.item is not None:
                path.append(p.item)
                p = p.parent
            if path:
                cond_base.append((path, node.count))
            node = node.link

        if cond_base:
            _, cond_header = _build_tree(cond_base, min_count)
            if cond_header:
                _mine(cond_header, new_prefix, min_count, out, max_len)


def frequent_itemsets(transactions, min_support=0.05, min_count=None, max_len=None):
    """
    MAIN ENTRY POINT.

    transactions : list of lists, e.g. [["Machine Learning", "Genomics"], ...]
    min_support  : 0.05 means "appears in at least 5% of papers"
    max_len      : stop at sets of this size (3 or 4 keeps things readable)

    returns (dict {frozenset: support_count}, number_of_transactions)
    """
    n = len(transactions)
    if n == 0:
        return {}, 0
    if min_count is None:
        min_count = max(1, ceil(min_support * n))

    weighted = [(list(set(t)), 1) for t in transactions if t]
    _, header = _build_tree(weighted, min_count)
    out: dict = {}
    if header:
        _mine(header, frozenset(), min_count, out, max_len)
    return out, n


def association_rules(itemsets, n_tx, min_confidence=0.5):
    """
    Turn frequent sets into IF -> THEN rules.

    confidence = P(consequent | antecedent)
    lift       = confidence / P(consequent)
                 lift > 1 means the two really do attract each other;
                 lift ~ 1 means they only co-occur because both are common.
    """
    rules = []
    for items, count in itemsets.items():
        if len(items) < 2:
            continue
        support = count / n_tx
        for item in items:
            antecedent = items - {item}
            a_count = itemsets.get(antecedent)
            c_count = itemsets.get(frozenset({item}))
            if not a_count or not c_count:
                continue
            confidence = count / a_count
            if confidence < min_confidence:
                continue
            lift = confidence / (c_count / n_tx)
            rules.append({
                "antecedent": " | ".join(sorted(antecedent)),
                "consequent": item,
                "support": support,
                "confidence": confidence,
                "lift": lift,
            })
    return sorted(rules, key=lambda r: -r["lift"])

