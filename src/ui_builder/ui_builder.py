from typing import Callable, Optional, Union

from config.config_item import ConfigItem, ConfigType, SchemaField, describe_default_value
from config.tab_spec import TabSpec
from config.toml_config import Config, IndexT, reset_to_defaults
import ui.widgets as ui
from support.dialog import choice_dialog, default_dialog_master

# Fallback bounds for an INTEGER/FLOAT item that declares no range, so
# IntegerSpinbox/FloatSpinbox always has something usable to pass as from_/to.
_INT_MIN = -2_147_483_648
_INT_MAX = 2_147_483_647
_FLOAT_MIN = -1e9
_FLOAT_MAX = 1e9

# A tab with more items than this gets a scrollbar instead of growing
# past this many rows.
MAX_VISIBLE_CONFIG_ITEMS_PER_TAB = 24


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
        # Registered separately from _widgets: a DefaultResetRow wraps
        # a built widget rather than replacing it in the registry
        # config_changed() uses to refresh values/read_only/allowed_values
        # (see build_configuration_window()), but still needs its own
        # "am I default right now?" refresh on every change -- see
        # _register_reset_row().
        self._reset_rows: dict[IndexT, list[object]] = {}

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
        defaults_factory: Optional[Callable[[], Config[IndexT]]] = None,
    ) -> ui.TabbedWindow:
        """Build a tabbed window titled `title` with one tab per TabSpec
        in `tabs`, each populated with a widget per index in that
        spec's `items` — same widget building and change wiring as
        build_shortcuts(). A "Masked" tab is appended next, containing
        every MASKED_STRING item in `config` (passwords/keys), if any
        -- skipped entirely if `config` has none. A final "All" tab is
        always appended, containing every config item in `config`
        sorted alphabetically by visible name, regardless of how the
        game grouped its other tabs (an item that's also on a custom
        tab, or the "Masked" one, appears on both — same as any other
        duplicate between a custom tab and "All").

        The window is created hidden; use
        its show()/hide()/toggle() to control visibility, which joins/
        leaves the shared snap chain automatically (see SnapWindow).
        `on_close` is called when the window is closed via its own
        close button (see TabbedWindow).

        `defaults_factory`, if given, adds a "Set defaults..." button
        to the bottom right of every tab (including the "All" one),
        offering the same All/All excluding masked/Cancel choice as an
        application-wide reset button would, but scoped to just that
        tab's own items -- see _add_tab_defaults_button(). Called fresh
        each time the button is clicked (rather than once up front), so
        it reflects whatever a defaults computation (e.g. a detected
        maps list) would produce right now, the same as an
        application-wide reset does."""
        window = ui.TabbedWindow(master=master, on_close=on_close, title=title)
        alphabetical_items = sorted(
            config.keys(), key=lambda index: config[index].visible_name.lower()
        )
        masked_items = [
            index
            for index in alphabetical_items
            if config[index].type is ConfigType.MASKED_STRING
        ]
        all_tabs = [
            *tabs,
            *([TabSpec(title="Masked", items=masked_items)] if masked_items else []),
            TabSpec(title="All", items=alphabetical_items),
        ]
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
                if config_item.type is ConfigType.STATIC_TEXT:
                    # Purely informational text, not a real config
                    # value (ConfigItem.__post_init__ requires it be
                    # read_only) -- nothing sensible to "reset", so
                    # leave it unwrapped. Every other read_only item
                    # still gets wrapped below: read_only for those is
                    # a runtime flag, not a permanent trait (e.g. a
                    # Game may flip RCON_PASSWORD or SELECTED_MAP
                    # between read_only and editable depending on
                    # another item's value -- see
                    # Game._sync_rcon_password_state()) -- so whether
                    # it's currently read_only at the moment this
                    # window is built says nothing about whether it
                    # can ever differ from its default.
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
                    continue

                def on_reset(index=index, config_item=config_item):
                    # `widget` is deliberately NOT a default arg here:
                    # it doesn't exist yet at this point in the loop
                    # (built below, against `row` as its master, right
                    # after row itself) -- resolved from the enclosing
                    # scope once this actually runs, by which time it's
                    # long since been assigned. Same forward-reference
                    # pattern _build_widget()'s own on_widget_changed
                    # relies on for its own `widget`.
                    self._apply_edit(
                        index,
                        config_item,
                        config,
                        config_item.default_value,
                        widget,
                        config_changed_callback,
                    )

                row = ui.DefaultResetRow(
                    master=tab,
                    on_reset=on_reset,
                    tooltip=f"Reset to default value ({describe_default_value(config_item)})",
                )
                # Built with `row` (not `tab`) as its master, so it's a
                # genuine Tk child of the row -- see
                # DefaultResetRow.set_child()'s docstring for why that
                # matters.
                widget = self._build_widget(
                    row,
                    index,
                    config_item,
                    config,
                    config_changed_callback,
                    compact=False,
                )
                row.set_child(widget)
                self._register(index, widget)
                tab_widgets.append(widget)
                row.set_has_default(config_item.is_default())
                row.pack(side=ui.TOP)
                self._register_reset_row(index, row)
            self._align_hint_widths(tab_widgets)
            if overflowing:
                self._clip_tab_to_visible_items(tab, len(tab_spec.items))
            if defaults_factory is not None:
                self._add_tab_defaults_button(
                    tab,
                    window,
                    tab_spec.items,
                    config,
                    config_changed_callback,
                    defaults_factory,
                )
        return window

    def _add_tab_defaults_button(
        self,
        tab,
        window: "ui.TabbedWindow",
        indexes: list[IndexT],
        config: Config[IndexT],
        config_changed_callback: Optional[
            Callable[[ConfigItem, Config[IndexT]], list[IndexT]]
        ],
        defaults_factory: Callable[[], Config[IndexT]],
    ) -> None:
        """Pack a "Set defaults..." button at the bottom right of `tab`,
        offering the same All/All excluding masked/Cancel choice as an
        application-wide reset button, but scoped to just `indexes` --
        this tab's own items -- so resetting one tab doesn't touch
        config items shown on another tab. The confirmation dialog
        centers itself on `window` (the configuration window this tab
        belongs to) rather than the application's main window, since
        that's what the user is actually looking at when they click it."""

        def on_tab_set_defaults():
            choice = choice_dialog(
                "Set config back to default values?",
                title="Set defaults",
                master=window,
                choices=[
                    ("All", "All config items including masked", "all"),
                    (
                        "All excluding masked",
                        "All config items but keep masked config items, i.e. all "
                        "passwords and keys",
                        "all_excluding_masked",
                    ),
                    ("Cancel", "Don't touch my config, I want it as it is", "cancel"),
                ],
                cancel_value="cancel",
            )
            if choice == "cancel":
                return

            keep_masked = choice == "all_excluding_masked"
            defaults = defaults_factory()
            changed = reset_to_defaults(config, defaults, keep_masked, indexes=indexes)
            affected = set(changed)
            if config_changed_callback is not None:
                for index in changed:
                    affected.update(config_changed_callback(config[index], config))
            self.config_changed(list(affected), config)

        button_row = ui.Frame(master=tab)
        button_row.pack(side=ui.BOTTOM, fill=ui.X)
        button = ui.Button(
            master=button_row,
            name="Set defaults...",
            tooltip="Reset this tab's config items to their default values",
            command=on_tab_set_defaults,
        )
        button.pack(side=ui.RIGHT)

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
        Likewise, for a STRUCT_MAP item with key_allowed_values_from
        set (e.g. MAP_GAME_MODES, keyed by SELECTED_MAP's known maps),
        refreshes MapGroupEditor's fixed key list from that other
        item's current allowed_values via set_keys() -- so e.g. adding
        or removing a workshop map updates MAP_GAME_MODES' key list
        too, as long as a Game lists it as affected whenever it lists
        the item key_allowed_values_from points at (see
        CS2Game.config_item_changed()'s WORKSHOP_MAPS handling).
        Also re-applies read_only, so a Game can dynamically
        enable/disable an item's widget (e.g. in response to another
        item's edit) by toggling ConfigItem.read_only and listing the
        item as affected, the same way it would change allowed_values.
        Also toggles any DefaultResetRow wrapping one of those widgets
        (see build_configuration_window()) to show/hide its "reset to
        default" button, since a change made anywhere -- a shortcut
        widget, another tab's copy of the same item, a reset itself,
        or a Game.config_item_changed() side effect -- can just as
        easily move an item back to its default as away from it.

        Indexes with no built widget are skipped."""
        for index in changed:
            item = config[index]
            for widget in self._widgets.get(index, []):
                if item.allowed_values is not None and hasattr(widget, "set_values"):
                    widget.set_values(item.allowed_values)
                key_source = item.key_allowed_values_from
                if (
                    key_source is not None
                    and key_source.allowed_values is not None
                    and hasattr(widget, "set_keys")
                ):
                    widget.set_keys(list(key_source.allowed_values))
                widget.update(item.value)
                widget.set_read_only(item.read_only)
            for row in self._reset_rows.get(index, []):
                row.set_has_default(item.is_default())

    def _register(self, index: IndexT, widget: object) -> None:
        self._widgets.setdefault(index, []).append(widget)

    def _register_reset_row(self, index: IndexT, row: object) -> None:
        self._reset_rows.setdefault(index, []).append(row)

    def _apply_edit(
        self,
        index: IndexT,
        item: ConfigItem,
        config: Config[IndexT],
        new_value,
        widget,
        config_changed_callback: Optional[
            Callable[[ConfigItem, Config[IndexT]], list[IndexT]]
        ],
    ) -> None:
        """Validate and apply `new_value` to `item`, then refresh every
        registered widget/reset-row for its index -- shared by a
        widget's own on-change handler (see _build_widget()) and a
        DefaultResetRow's reset button (see build_configuration_window()),
        so a reset behaves exactly like any other edit: widget value
        refresh, sibling-widget refresh, config_changed_callback side
        effects, and reset-button visibility, all included."""
        previous = item.value
        # Covers both item.set() (whose transform, e.g.
        # confirm_workshop_item() via WORKSHOP_MAPS/WORKSHOP_MAPGROUPS,
        # may pop up a dialog of its own) and config_changed_callback()
        # below (e.g. Game.config_item_changed() reacting to the new
        # value, which can do the same -- see CS2Game's workshop map
        # pre-download flow) -- both are several calls removed from any
        # window reference, so this lets whatever dialog either of them
        # shows still center on whichever window `widget` actually
        # lives in (a configuration window, or the main window for a
        # shortcut) instead of always the main window.
        with default_dialog_master(widget.winfo_toplevel()):
            try:
                item.set(new_value)
            except (TypeError, ValueError):
                # Reject the edit and snap the widget back to the last
                # valid value rather than leaving item/widget out of sync.
                widget.update(previous)
                return
            # A single refresh, after config_changed_callback (if any)
            # has had a chance to react -- e.g. CS2Game's workshop map
            # pre-download flow, which may still change `item`'s own
            # value again (drop a cancelled entry, dedupe a re-added
            # id) before it's actually final. Refreshing only once,
            # here, means every widget for `index` (this one, plus any
            # sibling, e.g. a shortcut and its counterpart in the
            # config tabs) always shows that final, settled value --
            # never an intermediate one the callback is about to
            # revise.
            affected = {index}
            if config_changed_callback is not None:
                # The game may have reacted by mutating other config
                # items too (e.g. narrowing another item's
                # allowed_values) -- refresh their widgets as well.
                affected.update(config_changed_callback(item, config))
            self.config_changed(list(affected), config)

    def _build_widget(
        self,
        master,
        index: IndexT,
        item: ConfigItem,
        config: Config[IndexT],
        config_changed_callback: Optional[
            Callable[[ConfigItem, Config[IndexT]], list[IndexT]]
        ],
        compact: bool,
    ):
        tooltip = item.tooltip if item.tooltip else item.visible_name

        def on_widget_changed(new_value):
            self._apply_edit(
                index, item, config, new_value, widget, config_changed_callback
            )

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
        elif item.type is ConfigType.STATIC_TEXT:
            widget = ui.StaticText(
                master=master,
                text=item.value,
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
                fixed_length=item.array_length is not None,
                listbox_height=item.display_rows or item.array_length or 5,
            )
        elif item.type is ConfigType.STRUCT:
            widget = ui.StructEditor(
                master=master,
                name=item.visible_name,
                schema=self._python_schema(item.schema),
                field_choices=self._field_choices(item.schema),
                initial_value=item.value,
                tooltip=tooltip,
                command=on_widget_changed,
                compact=compact,
            )
        elif item.type is ConfigType.STRUCT_LIST:
            widget = ui.StructListEditor(
                master=master,
                name=item.visible_name,
                schema=self._python_schema(item.schema),
                field_choices=self._field_choices(item.schema),
                initial_value=item.value,
                tooltip=tooltip,
                command=on_widget_changed,
                compact=compact,
            )
        elif item.type is ConfigType.STRUCT_MAP:
            field_choices = self._field_choices(item.schema)
            single_field = next(iter(item.schema)) if len(item.schema) == 1 else None
            if (
                item.value_type is ConfigType.STRUCT_LIST
                and single_field is not None
                and field_choices.get(single_field)
            ):
                # A map-group-shaped STRUCT_MAP (one field, a closed
                # set of choices, a list of them per key) -- e.g.
                # CS2/CS:GO's ordinary_mapgroups -- gets the
                # group-picker + toggle-checklist editor instead of
                # StructMapEditor's generic table/tree.
                all_keys = None
                if (
                    item.key_allowed_values_from is not None
                    and item.key_allowed_values_from.allowed_values is not None
                ):
                    # The item's own keys are externally managed (e.g.
                    # MAP_GAME_MODES' keys are exactly SELECTED_MAP's
                    # known maps, workshop included) -- show that fixed
                    # list instead of just whatever keys the item's
                    # current value happens to contain, and hide the
                    # add/remove-key controls entirely (there's nothing
                    # for the user to type; the key set comes from
                    # elsewhere).
                    all_keys = list(item.key_allowed_values_from.allowed_values)
                widget = ui.MapGroupEditor(
                    master=master,
                    name=item.visible_name,
                    key_type=self._python_type(item.item_type),
                    key_name=item.key_name,
                    field_name=single_field,
                    all_values=field_choices[single_field],
                    values_label=self._field_values_label(item.schema) or "Maps",
                    all_keys=all_keys,
                    initial_value=item.value,
                    tooltip=tooltip,
                    command=on_widget_changed,
                    compact=compact,
                )
            else:
                widget = ui.StructMapEditor(
                    master=master,
                    name=item.visible_name,
                    key_type=self._python_type(item.item_type),
                    key_name=item.key_name,
                    schema=self._python_schema(item.schema),
                    field_choices=field_choices,
                    initial_value=item.value,
                    tooltip=tooltip,
                    command=on_widget_changed,
                    compact=compact,
                    value_is_list=item.value_type is ConfigType.STRUCT_LIST,
                )
        else:
            raise ValueError(
                f"{item.name}: builder does not support ConfigType.{item.type.name} yet"
            )

        if item.read_only:
            widget.set_read_only(True)

        return widget

    def _python_type(self, config_type: ConfigType):
        # STRING_LIST/MASKED_STRING are distinct ConfigType members
        # from STRING (see config_item.py) purely so they don't alias
        # it as an Enum member — their actual Python value type is str
        # either way.
        if config_type in (ConfigType.STRING_LIST, ConfigType.MASKED_STRING):
            return str
        return config_type.value

    def _python_schema(
        self, schema: dict[str, Union[ConfigType, SchemaField]]
    ) -> dict[str, type]:
        """Convert a ConfigItem's STRUCT/STRUCT_LIST/STRUCT_MAP schema
        (field name -> ConfigType, or SchemaField wrapping one) to the
        field name -> plain Python type shape the Struct*Editor widgets
        expect — same reasoning as _python_type(): widgets.py stays
        config-agnostic."""
        return {
            field_name: self._python_type(self._field_type(field))
            for field_name, field in schema.items()
        }

    def _field_type(self, field: Union[ConfigType, SchemaField]) -> ConfigType:
        return field.type if isinstance(field, SchemaField) else field

    def _field_choices(
        self, schema: dict[str, Union[ConfigType, SchemaField]]
    ) -> dict[str, list]:
        """For each schema field associated with another ConfigItem
        (via SchemaField.allowed_values_from) that currently has
        allowed_values populated, snapshot those choices — passed to
        a Struct*Editor so it renders that field as a dropdown instead
        of free text. Fields with no association, or whose associated
        item's allowed_values isn't populated (yet), are omitted, so
        the widget falls back to its normal free-text field for them."""
        choices = {}
        for field_name, field in schema.items():
            if not isinstance(field, SchemaField) or field.allowed_values_from is None:
                continue
            candidates = field.allowed_values_from.allowed_values
            if candidates is not None:
                choices[field_name] = list(candidates)
        return choices

    def _field_values_label(
        self, schema: dict[str, Union[ConfigType, SchemaField]]
    ) -> Optional[str]:
        """The cosmetic values_label of whichever schema field carries
        one (see SchemaField.values_label) -- passed to MapGroupEditor
        as what to call its checklist's choices as a group (e.g. "Game
        modes"). None if no field sets one, letting the caller fall
        back to a generic default."""
        for field in schema.values():
            if isinstance(field, SchemaField) and field.values_label is not None:
                return field.values_label
        return None

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
