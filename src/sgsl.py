import os
from config import toml_handler
import process.process_handler as process_handler
import ui.widgets as ui
import server.detect as detect
import server.name as name
import game.cs2.maps
from pathlib import Path
import time
import ui.terminal as terminal
from version import VERSION

g_main_frame = None
g_process_handler = None
g_terminal_window = None
g_terminal_is_open = False
g_terminal_open_close = None
g_start_stop_server = None
g_config_default = None
g_config = None

def get_server_binary_path(dir: str) -> str:
    return str(game.cs2.runner.get(dir))

def is_terminal_open() -> bool:
    global g_terminal_is_open
    return g_terminal_is_open

def print_to_terminal(line: str):
    g_terminal_window.add_line(f"{line}")

def on_install_game_server(name: str):
    print_to_terminal(f"Installing game server for {name}...")

def handle_stdout_output(line: str):
    prefix = "[OUT]"
    print_to_terminal(f"{prefix} {line}")

def handle_stderr_output(line: str):
    prefix = "[ERR]"
    print_to_terminal(f"{prefix} {line}")

def handle_done(pid: int, returncode: int):
    print_to_terminal(f"Process tree {pid} finished with exit code {returncode}")

def on_start_stop_game_server(dir :str, name: str):
    global g_start_stop_server
    global g_process_handler
    exe = get_server_binary_path(dir)
    running_servers = g_process_handler.list_pids()
    if len(running_servers) == 0:
        args=["-dedicated", "-usercon", "+game_type", "0", "+game_mode", "1", "+map", "de_inferno"]
        print_to_terminal(f"Starting game server {name} with executable \"{exe}\" and arguments \"{args}\"...")
        started_pid = g_process_handler.start(
            args,
            no_window=True, 
            stdout_callback=handle_stdout_output, 
            stderr_callback=handle_stderr_output, 
            on_exit=handle_done
        )
        print_to_terminal(f"Started process with PID {started_pid}")
        g_start_stop_server.set_name(name="Stop")
        g_start_stop_server.set_tooltip(tooltip="Stop server")
    else:
        print_to_terminal(f"Found {len(running_servers)} running server(s) {running_servers} for {name} with executable {get_server_binary_path(dir)}")
        print_to_terminal(f"Stopping game server {name} with executable {exe}...")
        g_process_handler.kill_pids(running_servers, timeout=10.0, force=True)
        g_start_stop_server.set_name(name="Start")
        g_start_stop_server.set_tooltip(tooltip="Start server")

def on_toggle_terminal_window():
    global g_terminal_is_open
    g_terminal_is_open = not g_terminal_is_open
    g_terminal_window.toggle()

def setup_install_game(dir:str):
    global g_main_frame
    game_frame = ui.EditGroupFrame(master=g_main_frame, name="No game server detected")
    game_frame.pack()

    selected_game = ui.StringCombobox(master=game_frame, name="Select a game server to install", values=name.get_all_long_names(), selected=name.get_all_long_names()[0], tooltip="Select a game server to install")
    selected_game.pack()

    install_server = ui.ExpandingButton(game_frame, name="Install game server", tooltip="Install selected game server", command=lambda: on_install_game_server(selected_game.combobox.get()))
    install_server.pack()

    spacer_at_end = ui.Spacer(master=g_main_frame)
    spacer_at_end.pack()

def setup_detected_game_server(dir:str, name: str):

    global g_process_handler
    g_process_handler = process_handler.ProcessHandler(get_server_binary_path(dir))

    global g_main_frame

    game_frame = ui.EditGroupFrame(master=g_main_frame, name=name)
    game_frame.pack()

    edit_configuration = ui.Button(master=game_frame, name="Config", tooltip="Edit configuration")
    edit_configuration.pack()

    running_servers = g_process_handler.list_pids()
    print_to_terminal(f"Found {len(running_servers)} running server(s) {running_servers} for {name} with executable {get_server_binary_path(dir)}")
    global g_start_stop_server
    if len(running_servers) > 0:
        g_start_stop_server = ui.Button(master=game_frame, name="Stop", tooltip="Stop server", command=lambda: on_start_stop_game_server(dir, name))
    else:
        g_start_stop_server = ui.Button(master=game_frame, name="Start", tooltip="Start server", command=lambda: on_start_stop_game_server(dir, name))
    g_start_stop_server.pack()

    global g_terminal_open_close
    g_terminal_open_close = ui.CheckButton(master=game_frame, name="Terminal", tooltip="Toggle terminal window", command=lambda: on_toggle_terminal_window())
    g_terminal_open_close.pack()

    # -- spacer

    spacer_between_game_and_shortcut_frame = ui.Spacer(master=g_main_frame)
    spacer_between_game_and_shortcut_frame.pack()

    # -- shortcut frame

    shortcut_frame = ui.EditGroupFrame(master=g_main_frame, name="Shortcuts")
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

    spacer_at_end = ui.Spacer(master=g_main_frame)
    spacer_at_end.pack()

def on_close_terminal_window():
    global g_terminal_is_open
    g_terminal_is_open = False
    g_terminal_open_close.off()

# main

g_config_default = {
    "app": {"terminal": False},
#    "server": {"host": "0.0.0.0", "port": 8080},
}    

root = ui.Window(title="Simple Game Server Launcher" + " " + VERSION)

g_terminal_window = terminal.TerminalWindow(root, on_close_terminal_window, title="Log Output")

g_main_frame = ui.MainFrame(master=root)
g_main_frame.pack()

current_dir = os.getcwd()
test_dir = Path(current_dir) / "test-data" / "cs2" / "server"
if test_dir.exists():
    current_dir = test_dir
detected_game = detect.detect(current_dir)

g_config = toml_handler.TomlHandler(Path(current_dir) / "sgsl.toml", defaults=g_config_default)

if detected_game == "":
    setup_install_game(current_dir)
elif name.is_valid_short_name(detected_game):
    setup_detected_game_server(current_dir, name.long_name(detected_game))
else:
    # TODO: Show dialog box here
    exit(1)

g_config.write()

root.mainloop()
