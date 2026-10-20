from __future__ import annotations

import pytest
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container


@pytest.mark.unit
def test_a_container_method_makes_a_dependency() -> None:
    assert callable(use_case(Container.get_stats_use_case))


@pytest.mark.unit
def test_anything_but_a_container_method_is_refused_when_the_route_is_defined() -> None:
    with pytest.raises(TypeError):
        use_case(lambda container, session: container.get_stats_use_case(session))
