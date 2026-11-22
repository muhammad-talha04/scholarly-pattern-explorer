

def test_default_threads_respects_cgroup_quota(monkeypatch, tmp_path):
    import builtins
    from ml import embeddings
    real_open = builtins.open
    def fake(quota):
        def _open(path, *a, **k):
            if path == "/sys/fs/cgroup/cpu.max":
                f = tmp_path / "cpu.max"; f.write_text(quota)
                return real_open(f, *a, **k)
            return real_open(path, *a, **k)
        return _open
    monkeypatch.setattr(embeddings.os, "cpu_count", lambda: 64)
    monkeypatch.setattr(builtins, "open", fake("10000 100000\n"))   # 0.1 CPU
    assert embeddings.default_threads() == 1
    monkeypatch.setattr(builtins, "open", fake("400000 100000\n"))  # 4 CPUs
    assert embeddings.default_threads() == 4
    monkeypatch.setattr(builtins, "open", fake("max 100000\n"))
    assert embeddings.default_threads() == 64
