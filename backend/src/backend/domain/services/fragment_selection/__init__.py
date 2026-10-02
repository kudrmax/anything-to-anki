"""Fragment selection pipeline (domain service)."""
from backend.domain.services.fragment_selection.selector import (
    FragmentSelector,
    SelectedFragment,
)
from backend.domain.value_objects.fragment_selection_config import (
    FragmentSelectionConfig,
)

__all__ = ["FragmentSelectionConfig", "FragmentSelector", "SelectedFragment"]
