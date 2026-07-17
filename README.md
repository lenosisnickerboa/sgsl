# sgsl

Simple Game Server Launcher

# Preconditions

## Network

I am currently only running local servers and invite external players via the free [tailscale](https://tailscale.com/). Hence I will not describe the things required to setup gaming for external players. HOWEVER, there is nothing stopping you from doing this. I have provided the necessary options and you can of course configure your router to portforward traffic according each games recommendations and in that way get your public game server up and running. I have a limited amount of people connecting to my servers and hence I find tailscale a simple and practical solution for this. It solves all problems for all kinds of game servers, not just the ones controlled by sgsl.exe.

## OS
Only works on Windows 11 for now. It could work on previous Windows versions but I haven't tested it.

If a linux version is in high demand I will consider porting it to linux.

## cs2 only

According to my understanding a pure Windows 11 without the full cs2 game client (or just Steam?) installed doesn't contain all required libs and hence you must install the cs2 game client (or just Steam?) in order for the dedicated server to work.

Reference: https://steamcommunity.com/app/730/discussions/0/3881596897254177321/
Reference: https://steamcommunity.com/app/730/discussions/0/4335356354422173537/

Or you can just try and see if it works for you. This seems to be a moving target and your mileage may vary.

# Troubleshooting

As a a first hint, if something doesn't work, have a look in the terminal log to see more details of what failed.

## steamcmd dependencies

If you have problems with cs2 not installing it may be due to not having "Microsoft Visual C++ 2010 Redistributable Package (x86)" installed. It gets installed
with e.g Steam, but if you are running a standalone game server without Steam installed you may have to install this package yourself. It is required by the steamcmd which is used for installing the game server.

Download it from here: https://www.microsoft.com/en-us/download/details.aspx?id=26999

Click Download and select both vcredist_x86.exe and vcredist_x64.exe. After the download finishes, simply run both installers. Now retry installing cs2.