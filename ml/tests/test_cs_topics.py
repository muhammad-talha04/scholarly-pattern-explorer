from ml.cs_topics import cs_topics, is_cs


def test_cs_filter_uses_openalex_field():
    assert len(cs_topics()) > 200
    assert is_cs("Topic Modeling")
    assert not is_cs("Black Holes and Theoretical Physics")
    assert not is_cs("Educational Leadership and Innovation")
