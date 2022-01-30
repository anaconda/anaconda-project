import pytest

@pytest.fixture(params=["packages", "dependencies"])
def packages(request):
    """Ensure equivalence between `dependencies` and `packages`"""
    yield request.param


