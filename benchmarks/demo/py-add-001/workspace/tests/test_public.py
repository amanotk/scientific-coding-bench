from src.add import add


def test_add_integers():
    assert add(2, 3) == 5


def test_add_floats():
    assert abs(add(0.1, 0.2) - 0.3) < 1e-12
