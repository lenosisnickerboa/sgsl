# sgsl

Simple Game Server Launcher

# The general idea - "One click install game server"

This is a simple game server launcher suitable for people wanting to quickly setup and host a game server for some friends to join without diving into all the details of setting up and configuring a game server.

Even though the "One click install game server" vision is hard to reach due to how games are developed, this is still as close as you get. Create an empty directory for your server, drop sgsl.exe into it and start it, select game to install. Done.

Currently supported games:
- [Counter-Strike 2](src/game/cs2/README.md)
- [Venice Unleashed](src/game/vu/README.md)

# Preconditions

## OS
Only works on Windows 11 for now. Perhaps it works on previous Windows versions but I haven't tested it.

If a linux version is in high demand I will consider porting it to linux. sgsl is mostly python but there are some linux only things to consider when dealing with the actual game servers. So, I will be collecting requests for a while before starting this journey.

## cs2 only

According to my understanding a pure Windows 11 without the full cs2 game client (or just Steam?) installed doesn't contain all required libs and hence you must install the cs2 game client (or just Steam?) in order for the dedicated server to work.

Reference: https://steamcommunity.com/app/730/discussions/0/3881596897254177321/
Reference: https://steamcommunity.com/app/730/discussions/0/4335356354422173537/

Or you can just try and see if it works for you. This seems to be a moving target and your mileage may vary.

# Troubleshooting

As a a first hint, if something doesn't work, have a look in the terminal log to see more details of what failed. There is also the possibility to create an error report and file an issue. I will do my best to analyze it. As always, the more time you put into the issue text, the less time I need to fix the issue.

## steamcmd dependencies

If you have problems with cs2 not installing it may be due to not having "Microsoft Visual C++ 2010 Redistributable Package (x86)" installed. It gets installed
with e.g Steam, but if you are running a standalone game server without Steam installed you may have to install this package yourself. It is required by the steamcmd which is used for installing the game server.

Download it from here: https://www.microsoft.com/en-us/download/details.aspx?id=26999

Click Download and select both vcredist_x86.exe and vcredist_x64.exe. After the download finishes, simply run both installers. Now retry installing cs2.

## Developer information

If you want to develop sgsl on your own, [here](src/develop/README.md) are some hints.

# Some notes on my setup

I am currently only running local servers and invite external players via the free [tailscale](https://tailscale.com/) but there is nothing stopping you from going public with your server. I have provided the necessary options and briefly described what is required in the game description above. 

I have a limited amount of people connecting to my servers and hence I find tailscale a simple and practical solution for this. It solves all problems for all kinds of game servers, not just the ones controlled by sgsl.exe.
