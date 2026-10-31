"""A pattern must never be listed as both emerging and declining."""
import pandas as pd

from analytics import split_change
from export_snapshot import md_table


def test_split_change():
    df = pd.DataFrame({"itemset": ["A | B", "C | D", "E | F"],
                       "change": [0.0019, -0.0032, 0.0]})
    up, down = split_change(df, 10)
    assert up.itemset.tolist() == ["A | B"]
    assert down.itemset.tolist() == ["C | D"]
    assert split_change(df.iloc[:0], 10)[0].empty


def test_md_table_escapes_pipes():
    row = md_table(pd.DataFrame({"itemset": ["A | B"], "k": [2]})).splitlines()[2]
    assert row == "| A \\| B | 2 |"
