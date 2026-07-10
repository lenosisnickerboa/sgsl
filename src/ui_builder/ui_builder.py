from config.config_item import ConfigItem, ConfigType
from config.toml_config import Config, IndexT
import ui.widgets as ui

# Fallback bounds for an INTEGER item that declares no range, so
# IntegerSpinbox always has something usable to pass as from_/to.
_INT_MIN = -2_147_483_648
_INT_MAX = 2_147_483_647


class UiBuilder:
    """Builds ui widgets from ConfigItems and keeps them in
    sync when the backing config changes elsewhere.

    Tracks every widget it builds in a dict keyed by config index, so
    a later config_changed() call can find the right widget and ask it
    to refresh itself without the caller needing to keep its own
    mapping."""

    def __init__(self):
        self._widgets: dict[IndexT, object] = {}

    def build_shortcuts(self, master, shortcuts: list[IndexT], config: Config[IndexT]) -> dict[IndexT, object]:
        """Build one widget per index in `shortcuts` into `master`, each
        reflecting the current value of the matching ConfigItem in
        `config`."""
        for shortcut in shortcuts:
            config_item = config[shortcut]
            widget = self._build_widget(master, config_item)
            widget.pack()
            self._widgets[shortcut] = widget
        return self._widgets

    def config_changed(self, changed: list[IndexT], config: Config[IndexT]) -> None:
        """Refresh the widgets for `changed` indexes to reflect their
        current value in `config`. Indexes with no built widget are
        skipped."""
        for index in changed:
            widget = self._widgets.get(index)
            if widget is None:
                continue
            widget.update(config[index].value)

    def _build_widget(self, master, item: ConfigItem):
        if item.type is ConfigType.BOOLEAN:
            return ui.CheckButton(
                master=master,
                name=item.visible_name,
                tooltip=item.visible_name,
                initial_value=item.value,
            )

        if item.type is ConfigType.INTEGER:
            return ui.IntegerSpinbox(
                master=master,
                name=item.visible_name,
                range=self._integer_range(item),
                initial_value=item.value,
                tooltip=item.visible_name,
            )

        if item.type is ConfigType.STRING:
            # A closed set of allowed_values becomes a read-only dropdown;
            # an unconstrained string becomes a free-typing combobox seeded
            # with its current value (widgets.py has no plain text entry).
            values = item.allowed_values if item.allowed_values else [item.value]
            return ui.StringCombobox(
                master=master,
                name=item.visible_name,
                values=values,
                selected=item.value,
                tooltip=item.visible_name,
                readonly=item.allowed_values is not None,
            )

        raise ValueError(f"{item.name}: builder does not support ConfigType.{item.type.name} yet")

    def _integer_range(self, item: ConfigItem) -> list[int]:
        lo, hi = _INT_MIN, _INT_MAX
        if item.range is not None:
            if item.range.min_value is not None:
                lo = item.range.min_value
            if item.range.max_value is not None:
                hi = item.range.max_value
        return [lo, hi]
