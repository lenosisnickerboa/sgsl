from typing import Callable, Optional

from config.config_item import ConfigItem, ConfigType
from config.tab_spec import TabSpec
from config.toml_config import Config, IndexT
import ui.widgets as ui

# Fallback bounds for an INTEGER/FLOAT item that declares no range, so
# IntegerSpinbox/FloatSpinbox always has something usable to pass as from_/to.
_INT_MIN = -2_147_483_648
_INT_MAX = 2_147_483_647
_FLOAT_MIN = -1e9
_FLOAT_MAX = 1e9

# A tab with more items than this gets a scrollbar instead of growing
# past this many rows.
MAX_VISIBLE_CONFIG_ITEMS_PER_TAB = 8


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
        config_changed_callback: Optional[
            Callable[[ConfigItem, Config[IndexT]], list[IndexT]]
        ] = None,
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
            widget = self._build_widget(
                master,
                shortcut,
                config_item,
                config,
                config_changed_callback,
                compact=True,
            )
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
        config_changed_callback: Optional[
            Callable[[ConfigItem, Config[IndexT]], list[IndexT]]
        ] = None,
    ) -> ui.TabbedWindow:
        """Build a tabbed window titled `title` with one tab per TabSpec
        in `tabs`, each populated with a widget per index in that
        spec's `items` — same widget building and change wiring as
        build_shortcuts(). A final "All" tab is always appended,
        containing every config item in `config` sorted alphabetically
        by visible name, regardless of how the game grouped its other
        tabs. The window is created hidden; use
        its show()/hide()/toggle() to control visibility. `on_close` is
        called when the window is closed via its own close button (see
        TabbedWindow)."""
        window = ui.TabbedWindow(master=master, on_close=on_close, title=title)
        alphabetical_items = sorted(
            config.keys(), key=lambda index: config[index].visible_name.lower()
        )
        all_tabs = [*tabs, TabSpec(title="All", items=alphabetical_items)]
        for tab_spec in all_tabs:
            overflowing = len(tab_spec.items) > MAX_VISIBLE_CONFIG_ITEMS_PER_TAB
            if overflowing:
                tab = ui.ScrollableTab(master=window.notebook, title=tab_spec.title)
            else:
                tab = ui.Tab(master=window.notebook, title=tab_spec.title)
            window.add_tab(tab)
            tab_widgets = []
            for index in tab_spec.items:
                config_item = config[index]
                widget = self._build_widget(
                    tab,
                    index,
                    config_item,
                    config,
                    config_changed_callback,
                    compact=False,
                )
                widget.pack(side=ui.TOP)
                self._register(index, widget)
                tab_widgets.append(widget)
            self._align_hint_widths(tab_widgets)
            if overflowing:
                self._clip_tab_to_visible_items(tab, len(tab_spec.items))
        return window

    def _align_hint_widths(self, widgets: list) -> None:
        """Give every widget's hint label in this tab the same fixed
        pixel width (the widest one's natural width), so their core
        controls (entry/spinbox/combobox/checkbutton) all start at the
        same x position — a straight vertical line down the tab. Only
        non-compact widgets (see HintedWidget) have a hint label.

        Sized in real pixels (winfo_reqwidth()), not characters:
        ttk.Label's own `width` option counts in units of the "0"
        glyph's pixel width, which can badly underestimate the space
        real text needs and clip it."""
        alignable = [widget for widget in widgets if hasattr(widget, "set_hint_width")]
        if not alignable:
            return
        for widget in alignable:
            widget.hint_frame.update_idletasks()
        max_width = max(widget.hint_frame.winfo_reqwidth() for widget in alignable)
        for widget in alignable:
            widget.set_hint_width(max_width)

    def _clip_tab_to_visible_items(
        self, tab: "ui.ScrollableTab", item_count: int
    ) -> None:
        """Size a ScrollableTab's viewport so only
        MAX_VISIBLE_CONFIG_ITEMS_PER_TAB of its widgets are visible at
        once, based on the height they actually took (widgets differ
        in height, so this isn't a fixed per-row constant), leaving the
        rest reachable by scrolling. Width is left at its natural
        (unclipped) size so nothing is cut off horizontally."""
        tab.update_idletasks()
        content_width = tab.winfo_reqwidth()
        content_height = tab.winfo_reqheight()
        per_item_height = content_height / item_count
        visible_height = round(per_item_height * MAX_VISIBLE_CONFIG_ITEMS_PER_TAB)
        tab.container.configure(width=content_width)
        tab.set_visible_height(visible_height)

    def config_changed(self, changed: list[IndexT], config: Config[IndexT]) -> None:
        """Refresh the widget(s) for `changed` indexes to reflect their
        current value in `config` — and, for widgets that support it
        (e.g. StringCombobox.set_values()), their current
        allowed_values too, e.g. when one item's edit narrows or
        widens another item's choices (see Game.config_item_changed).
        Indexes with no built widget are skipped."""
        for index in changed:
            item = config[index]
            for widget in self._widgets.get(index, []):
                if item.allowed_values is not None and hasattr(widget, "set_values"):
                    widget.set_values(item.allowed_values)
                widget.update(item.value)

    def _register(self, index: IndexT, widget: object) -> None:
        self._widgets.setdefault(index, []).append(widget)

    def _build_widget(
        self,
        master,
        index: IndexT,
        item: ConfigItem,
        config: Config[IndexT],
        config_changed_callback: Optional[Callable[[ConfigItem, Config[IndexT]], list[IndexT]]],
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
                # The game may have reacted by mutating other config
                # items (e.g. narrowing another item's allowed_values)
                # — refresh their widgets too.
                affected = config_changed_callback(item, config)
                if affected:
                    self.config_changed(affected, config)

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
        elif item.type is ConfigType.FLOAT:
            widget = ui.FloatSpinbox(
                master=master,
                name=item.visible_name,
                range=self._float_range(item),
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
        elif item.type is ConfigType.MASKED_STRING:
            widget = ui.MaskedStringEntry(
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
        elif item.type is ConfigType.ARRAY:
            widget = ui.ArrayEditor(
                master=master,
                name=item.visible_name,
                initial_value=item.value,
                tooltip=tooltip,
                item_type=self._python_type(item.item_type),
                command=on_widget_changed,
                compact=compact,
            )
        else:
            raise ValueError(
                f"{item.name}: builder does not support ConfigType.{item.type.name} yet"
            )

        return widget

    def _python_type(self, config_type: ConfigType):
        # STRING_LIST/MASKED_STRING are distinct ConfigType members
        # from STRING (see config_item.py) purely so they don't alias
        # it as an Enum member — their actual Python value type is str
        # either way.
        if config_type in (ConfigType.STRING_LIST, ConfigType.MASKED_STRING):
            return str
        return config_type.value

    def _integer_range(self, item: ConfigItem) -> list[int]:
        lo, hi = _INT_MIN, _INT_MAX
        if item.range is not None:
            if item.range.min_value is not None:
                lo = item.range.min_value
            if item.range.max_value is not None:
                hi = item.range.max_value
        return [lo, hi]

    def _float_range(self, item: ConfigItem) -> list[float]:
        lo, hi = _FLOAT_MIN, _FLOAT_MAX
        if item.range is not None:
            if item.range.min_value is not None:
                lo = item.range.min_value
            if item.range.max_value is not None:
                hi = item.range.max_value
        return [lo, hi]
