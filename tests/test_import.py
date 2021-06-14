from pytest import mark


def test_import() -> None:
    """Very simple test mostly to make sure pytest has something to run."""
    import pycheck

    assert pycheck


@mark.slow
def test_slow() -> None:
    """Dummy test to ensure one test exists marked "slow"."""
