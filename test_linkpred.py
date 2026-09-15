"""Self-check for link prediction logic.
Creates a tiny synthetic graph to verify that heuristics and ML proxies
actually produce scores and can distinguish between a likely link
(shared neighbors) and an unlikely one (random).
"""

import numpy as np
from linkpred import get_heuristics, get_graph_mlp_scores

def test_logic():
    # Synthetic split: 2 clusters {A,B,C} and {D,E,F}
    # A and B are connected; C is connected to A and B.
    # D and E are connected; F is connected to D and E.
    # Link (A, D) is unlikely. Link (A, C) is likely.
    class MockSplit:
        def __init__(self):
            self.adj = {
                'A': {'B', 'C'}, 'B': {'A', 'C'}, 'C': {'A', 'B'},
                'D': {'E', 'F'}, 'E': {'D', 'F'}, 'F': {'D', 'E'}
            }
            self.nodes = ['A', 'B', 'C', 'D', 'E', 'F']
            self.test_pos = [('A', 'C')]
            self.test_neg = [('A', 'D')]
            self.index = {n: i for i, n in enumerate(self.nodes)}

    sp = MockSplit()
    topics = {'A': {1}, 'B': {1}, 'C': {1}, 'D': {2}, 'E': {2}, 'F': {2}}

    print("Testing Heuristics...")
    h = get_heuristics(sp, topics)
    # Pair 0 (A,C) should have higher CN than Pair 1 (A,D)
    assert h['cn'][0] > h['cn'][1], f"CN failed: {h['cn'][0]} vs {h['cn'][1]}"
    assert h['jaccard'][0] > h['jaccard'][1], "Jaccard failed"
    print("  Heuristics OK.")

    print("Testing Graph-ML Proxy...")
    ga = get_graph_mlp_scores(sp, topics)
    assert ga[0] > ga[1], f"ML Proxy failed: {ga[0]} vs {ga[1]}"
    print("  ML Proxy OK.")

    print("\nAll link-prediction self-checks passed!")

if __name__ == "__main__":
    try:
        test_logic()
    except Exception as e:
        print(f"Test failed: {e}")
        exit(1)
