import pytest

@pytest.fixture(autouse=True)
def tc_setup():
    print("Set up method")

    yield

    print("Tear down method")