import pytest
from .models import Company

pytestmark = pytest.mark.asyncio


async def test_225_large_binary(bind):
    c = await Company.create(logo=b'SVG LOGO')
    assert c.logo == b'SVG LOGO'
