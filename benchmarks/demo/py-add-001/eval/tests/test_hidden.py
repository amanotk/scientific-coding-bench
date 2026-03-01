from src.add import add


def test_add_more_cases():
    assert add(-1, 1) == 0
    assert add(10, 0) == 10


def test_add_float_tolerance():
    # Avoid exact float equality.
    assert abs(add(0.1, 0.2) - 0.3) < 1e-12
