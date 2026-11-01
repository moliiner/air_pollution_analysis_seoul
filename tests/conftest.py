import pandas as pd
import pytest


@pytest.fixture
def tiny_frame():
    return pd.DataFrame({"pm25": [10.0, -1.0, 40.0, None]})
