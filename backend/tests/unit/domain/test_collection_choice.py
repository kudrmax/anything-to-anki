import pytest
from backend.domain.value_objects.collection_choice import CollectionChoice


@pytest.mark.unit
class TestCollectionChoice:
    def test_no_collection_is_neither(self) -> None:
        choice = CollectionChoice()
        assert choice.existing_id is None
        assert choice.new_name is None

    def test_choice_cannot_be_both(self) -> None:
        with pytest.raises(ValueError):
            CollectionChoice(existing_id=1, new_name="Dune")

    def test_blank_new_name_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            CollectionChoice(new_name="  ")
