# sgsl

Simple Game Server Launcher

# Troubleshooting

As a a first hint, if something doesn't work, have a look in the terminal log to see more details of what failed.

## steamcmd dependencies

If you have problems with cs2 not installing it may be due to not having "Microsoft Visual C++ 2010 Redistributable Package (x86)" installed. It gets installed
with e.g Steam, but if you are running a standalone game server without Steam installed you may have to install this package yourself. It is required by the steamcmd which is used for installing the game server.

Download it from here: https://www.microsoft.com/en-us/download/details.aspx?id=26999

Click Download and select both vcredist_x86.exe and vcredist_x64.exe. After the download finishes, simply run both installers. Now retry installing cs2.