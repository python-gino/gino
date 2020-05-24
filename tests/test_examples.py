import os
from pathlib import Path

import pytest

examples_dir = Path(__file__).parent.parent / "examples"


@pytest.mark.parametrize(
    "example",
    [
        pytest.param(example, id=str(example.name))
        for example in examples_dir.iterdir()
        if example.is_dir()
    ],
)
@pytest.mark.skipif(
    os.getenv("TEST_EXAMPLES", "0").lower() not in {"1", "yes", "true", "t"},
    reason="TEST_EXAMPLES=" + os.getenv("TEST_EXAMPLES", ""),
)
def test_examples(example: Path, virtualenv):
    env = virtualenv.env.copy()
    env["PWD"] = str(example)
    env.update(
        {
            k: v
            for k, v in os.environ.items()
            if k.startswith("DB_")
            or k.startswith("POSTGRESQL_")
            or k.startswith("MYSQL_")
        }
    )

    virtualenv.run("pip install -e ../../../sqlalchemy", cwd=example)
    virtualenv.run("make test", cwd=example, env=env)
