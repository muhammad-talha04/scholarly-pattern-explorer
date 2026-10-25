from ml.cs_topics import cs_topics, is_cs


def test_cs_filter_uses_openalex_field():
    assert len(cs_topics()) > 200
    assert is_cs("Topic Modeling")
    assert not is_cs("Black Holes and Theoretical Physics")
    assert not is_cs("Educational Leadership and Innovation")


def test_not_cs_topics_are_excluded():
    from ml.cs_topics import NOT_CS
    assert not is_cs("Thoreau and American Literature")
    assert not is_cs("Psychiatry, Mental Health, Neuroscience")
    assert is_cs("Machine Learning and Algorithms")
    assert len(NOT_CS) < 60
