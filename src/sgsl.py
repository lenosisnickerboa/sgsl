import os
import ui.widgets as ui
import server.detect as detect
import server.name as name
import game.cs2.maps
from pathlib import Path
import process.process_handle as process_handle
import time
import ui.terminal as terminal

server_process_handle = None
terminal_window = None
terminal_is_open = False
terminal_open_close = None

def is_server_running() -> bool:
    global server_process_handle
    if server_process_handle is None:
        return False
    return server_process_handle.is_running()

def is_terminal_open() -> bool:
    global terminal_is_open
    return terminal_is_open

def print_to_terminal(line: str):
    terminal_window.add_line(f"{line}")

def on_install_game_server(name: str):
    print_to_terminal(f"Installing game server for {name}...")

def handle_output(line, stream):
    prefix = "[ERR]" if stream == "stderr" else "[OUT]"
    print_to_terminal(f"{prefix} {line}")

def handle_done(returncode):
    print_to_terminal(f"Process tree finished with exit code {returncode}")

def on_start_game_server(dir :str, name: str):
    exe = game.cs2.runner.get(dir)
    print_to_terminal(f"Starting game server for {name} with {exe}...")

    global server_process_handle
    server_process_handle = process_handle.run_command_interactive(
        f"{exe} -dedicated -headless -usercon +game_type 0 +game_mode 1 +map de_inferno",
        shell=True,
        on_output=handle_output,
        on_done=handle_done,
    )
    global start_stop_server
    start_stop_server.config(command=lambda: on_stop_game_server(dir, name), name="Stop", tooltip="Stop server")

def on_stop_game_server(dir :str, name: str):
    exe = game.cs2.runner.get(dir)
    print(f"Stopping game server for {name} with {exe}...")

    global server_process_handle
    server_process_handle = process_handle.kill(timeout=5.0)
    global start_stop_server
    start_stop_server.config(command=lambda: on_start_game_server(dir, name), name="Start", tooltip="Start server")

def on_toggle_terminal_window():
    global terminal_is_open
    terminal_is_open = not terminal_is_open
    terminal_window.toggle()

def setup_install_game(dir:str):
    game_frame = ui.EditGroupFrame(master=main_frame, name="No game server detected")
    game_frame.pack()

    selected_game = ui.StringCombobox(master=game_frame, name="Select a game server to install", values=name.get_all_long_names(), selected=name.get_all_long_names()[0], tooltip="Select a game server to install")
    selected_game.pack()

    install_server = ui.ExpandingButton(game_frame, name="Install game server", tooltip="Install selected game server", command=lambda: on_install_game_server(selected_game.combobox.get()))
    install_server.pack()

    spacer_at_end = ui.Spacer(master=main_frame)
    spacer_at_end.pack()

def setup_detected_game_server(dir:str, name: str):
    game_frame = ui.EditGroupFrame(master=main_frame, name=name)
    game_frame.pack()

    edit_configuration = ui.Button(master=game_frame, name="Config", tooltip="Edit configuration")
    edit_configuration.pack()

    if is_server_running():
        start_stop_server = ui.Button(master=game_frame, name="Stop", tooltip="Stop server", command=lambda: on_stop_game_server(dir, name))
    else:
        start_stop_server = ui.Button(master=game_frame, name="Start", tooltip="Start server", command=lambda: on_start_game_server(dir, name))
    start_stop_server.pack()

    global terminal_open_close
    terminal_open_close = ui.CheckButton(master=game_frame, name="Terminal", tooltip="Toggle terminal window", command=lambda: on_toggle_terminal_window())
    terminal_open_close.pack()

    # -- spacer

    spacer_between_game_and_shortcut_frame = ui.Spacer(master=main_frame)
    spacer_between_game_and_shortcut_frame.pack()

    # -- shortcut frame

    shortcut_frame = ui.EditGroupFrame(master=main_frame, name="Shortcuts")
    shortcut_frame.pack()

    game_mode = ui.StringCombobox(master=shortcut_frame, name="Game mode", values=(r"Deathmatch", r"Gungame", r"Casual"), selected=2, tooltip="Selected game mode")
    game_mode.pack()

#    map_group = ui.StringCombobox(master=shortcut_frame, name="Map group", values=(r"Mapgroup-1", r"Mapgroup-2", r"Mapgroup-3"), selected=1, tooltip="Selected map group")
#    map_group.pack()

    maps = game.cs2.maps.get(dir)
    map = ui.StringCombobox(master=shortcut_frame, name="Map", values=maps, selected=maps[0], tooltip="Selected map within selected game mode")
    map.pack()

    player_count = ui.IntegerSpinbox(master=shortcut_frame, name="Player count", range=(1,64), initial_value=5, tooltip="Number of players on server")
    player_count.pack()

    spacer_at_end = ui.Spacer(master=main_frame)
    spacer_at_end.pack()

def on_close_terminal_window():
    global terminal_is_open
    terminal_is_open = False
    terminal_open_close.off()

# main

root = ui.Window(title="sgsl 0.1")

terminal_window = terminal.TerminalWindow(root, on_close_terminal_window, title="Log Output")

main_frame = ui.MainFrame(master=root)
main_frame.pack()

current_dir = os.getcwd()
test_dir = Path(current_dir) / "test-data" / "cs2" / "server"
if test_dir.exists():
    current_dir = test_dir
detected_game = detect.detect(current_dir)

if detected_game == "":
    setup_install_game(current_dir)
elif name.is_valid_short_name(detected_game):
    setup_detected_game_server(current_dir, name.long_name(detected_game))
else:
    exit(1)

for i in range(256):
    print_to_terminal(f"Test line {i+1}")

root.mainloop()
