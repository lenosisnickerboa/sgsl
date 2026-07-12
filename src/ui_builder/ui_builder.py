from typing import Callable, Optional

from config.config_item import ConfigItem, ConfigType
from config.tab_spec import TabSpec
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
    a later config_changed() call can find the right widget(s) and ask
    them to refresh without the caller needing to keep its own
    mapping. The same index can end up with more than one widget (e.g.
    it appears both in the shortcuts row and in a configuration tab),
    so each index maps to a list."""

    def __init__(self):
        self._widgets: dict[IndexT, list[object]] = {}

    def build_shortcuts(
        self,
        master,
        shortcuts: list[IndexT],
        config: Config[IndexT],
        config_changed_callback: Optional[Callable[[ConfigItem, Config[IndexT]], None]] = None,
    ) -> dict[IndexT, object]:
        """Build one widget per index in `shortcuts` into `master`, each
        reflecting the current value of the matching ConfigItem in
        `config`. When the user edits a widget, its ConfigItem is
        updated in place and, if valid, `config_changed_callback` is
        invoked with (config_item, config) so the caller can react
        (e.g. forward it to Game.config_item_changed)."""
        built: dict[IndexT, object] = {}
        for shortcut in shortcuts:
            config_item = config[shortcut]
            widget = self._build_widget(master, shortcut, config_item, config, config_changed_callback, compact=True)
            widget.pack()
            self._register(shortcut, widget)
            built[shortcut] = widget
        return built

    def build_configuration_window(
        self,
        master,
        on_close: Callable[[], None],
        title: str,
        tabs: list[TabSpec],
        config: Config[IndexT],
        config_changed_callback: Optional[Callable[[ConfigItem, Config[IndexT]], None]] = None,
    ) -> ui.TabbedWindow:
        """Build a tabbed window titled `title` with one tab per TabSpec
        in `tabs`, each populated with a widget per index in that
        spec's `items` — same widget building and change wiring as
        build_shortcuts(). A final "All" tab is always appended,
        containing every config item in `config`, regardless of how the
        game grouped its other tabs. The window is created hidden; use
        its show()/hide()/toggle() to control visibility. `on_close` is
        called when the window is closed via its own close button (see
        TabbedWindow)."""
        window = ui.TabbedWindow(master=master, on_close=on_close, title=title)
        all_tabs = [*tabs, TabSpec(title="All", items=list(config.keys()))]
        for tab_spec in all_tabs:
            tab = ui.Tab(master=window.notebook, title=tab_spec.title)
            window.add_tab(tab)
            for index in tab_spec.items:
                config_item = config[index]
                widget = self._build_widget(tab, index, config_item, config, config_changed_callback, compact=False)
                widget.pack(side=ui.TOP)
                self._register(index, widget)
        return window

    def config_changed(self, changed: list[IndexT], config: Config[IndexT]) -> None:
        """Refresh the widget(s) for `changed` indexes to reflect their
        current value in `config`. Indexes with no built widget are
        skipped."""
        for index in changed:
            for widget in self._widgets.get(index, []):
                widget.update(config[index].value)

    def _register(self, index: IndexT, widget: object) -> None:
        self._widgets.setdefault(index, []).append(widget)

    def _build_widget(
        self,
        master,
        index: IndexT,
        item: ConfigItem,
        config: Config[IndexT],
        config_changed_callback: Optional[Callable[[ConfigItem, Config[IndexT]], None]],
        compact: bool,
    ):
        tooltip = item.tooltip if item.tooltip else item.visible_name

        def on_widget_changed(new_value):
            previous = item.value
            try:
                item.set(new_value)
            except (TypeError, ValueError):
                # Reject the edit and snap the widget back to the last
                # valid value rather than leaving item/widget out of sync.
                widget.update(previous)
                return
            # Other widgets built for this same index (e.g. a shortcut
            # and its counterpart in the config tabs) need to pick up
            # the new value too.
            self.config_changed([index], config)
            if config_changed_callback is not None:
                config_changed_callback(item, config)

        if item.type is ConfigType.BOOLEAN:
            widget = ui.CheckButton(
                master=master,
                name=item.visible_name,
                tooltip=tooltip,
                initial_value=item.value,
                command=on_widget_changed,
                compact=compact,
            )
        elif item.type is ConfigType.INTEGER:
            widget = ui.IntegerSpinbox(
                master=master,
                name=item.visible_name,
                range=self._integer_range(item),
                initial_value=item.value,
                tooltip=tooltip,
                command=on_widget_changed,
                compact=compact,
            )
        elif item.type is ConfigType.STRING:
            widget = ui.StringEntry(
                master=master,
                name=item.visible_name,
                initial_value=item.value,
                tooltip=tooltip,
                command=on_widget_changed,
                compact=compact,
            )
        elif item.type is ConfigType.STRING_LIST:
            # A closed set of allowed_values becomes a read-only dropdown;
            # an unconstrained STRING_LIST falls back to a free-typing
            # combobox seeded with its current value.
            values = item.allowed_values if item.allowed_values else [item.value]
            widget = ui.StringCombobox(
                master=master,
                name=item.visible_name,
                values=values,
                selected=item.value,
                tooltip=tooltip,
                readonly=item.allowed_values is not None,
                command=on_widget_changed,
                compact=compact,
            )
        else:
            raise ValueError(f"{item.name}: builder does not support ConfigType.{item.type.name} yet")

        return widget

    def _integer_range(self, item: ConfigItem) -> list[int]:
        lo, hi = _INT_MIN, _INT_MAX
        if item.range is not None:
            if item.range.min_value is not None:
                lo = item.range.min_value
            if item.range.max_value is not None:
                hi = item.range.max_value
        return [lo, hi]
