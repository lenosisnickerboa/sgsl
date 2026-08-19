<img src="assets/icon.png" width="96" alt="Counter-Strike 2 icon">

# Counter-Strike 2 [Publisher docs](https://store.steampowered.com/app/730/CounterStrike_2/)

## Some general observations first

There are a lot of notes about restarting the server or the client to see if that solves the problem. It seems to be quite common that when things stop working, a restart fixes things. Hmmm...

Installation takes time and terminal output is not continous (it is buffered) so you will just have to be patient. For me an install takes about 30 minutes.

There are a gazillion config items in cs2 (cvars) and the documentation is really hard to understand. I have selected the ones I think are relevant and some others which sound like they could be useful as well. Some config items are only valid for certain game modes, and ignored in other. I have tried to set sane defaults but not sure I succeeded everywhere. Either create an issue and suggest improvements or fix it by adding custom pre/post commands or adding "_append" config files.

If you think something seems fishy, make sure both the server and client is properly updated. Again, it may be necessary to restart server and/or client to make it realize it needs an update. Again hmmm...

## Installation [Publisher docs](https://developer.valvesoftware.com/wiki/Counter-Strike_2/Dedicated_Servers)

Depending on how you want to run your server, here comes some scenarios.

### Simplest possible, LAN only, no workshop maps, just want to play locally with friends

1. Get your original CS2 client working. Start it up and make sure you can run multiplayer.
1. Drop sgsl.exe into an empty folder where you want your CS2 game server installed and click sgsl.exe. 
1. When sgsl.exe launches, select cs2 and click the install button.
1. ENJOY!

Your friends can now connect to you using the console command "connect \<your-ip\>" or by connecting via the local server browser steam://open/servers. You can create a Windows shortcut with target "steam://open/servers" and name "CS2 local servers" or simply run it with WIN+R, enter steam://open/servers and press ENTER.

### I want workshop maps

I'm not sure what the exact requirements are after googling, AI:ing, ... Some suggest you need a GSLT, some an API auth key. I didn't have to configure any of them but here's a description on how to configure both should you not get workshop maps working without them.

1. Get your original CS2 client working. Start it up and make sure you can run multiplayer.
1. Register some stuff with Valve, like [GSLT](https://developer.valvesoftware.com/wiki/Counter-Strike_2/Dedicated_Servers#Registering_Game_Server_Login_Token) which can be done [here](http://steamcommunity.com/dev/managegameservers) and and [API auth key](https://steamcommunity.com/dev/apikey). Use 730 for the appId.
1. Drop sgsl.exe into an empty folder where you want your CS2 game server installed and click sgsl.exe. 
1. When sgsl.exe launches, select cs2 and click the install button.
1. After the sgsl restart, enter the GSLT, API auth key in the "Steam" game config tab.
1. ENJOY!

### My friends are scattered over the Internet

If you want to have friends connect from outside your LAN the easy way is to just use [tailscale](https://tailscale.com/) or some other VPN solution. It's free and you can invite all your external friends to your game server. Once they are connected it again works just like they're all on your LAN. This is how I run things.

If you don't like this approach proceed to the next scenario.

### I want my server publically available

If you want your server publically available in the Valve server browser, and have friends connect to it from outside your LAN, this is what you need to do:

1. Get your original CS2 client working. Start it up and make sure you can run multiplayer.
1. Register some stuff with Valve, like [GSLT](https://developer.valvesoftware.com/wiki/Counter-Strike_2/Dedicated_Servers#Registering_Game_Server_Login_Token) which can be done [here](http://steamcommunity.com/dev/managegameservers) and and [API auth key](https://steamcommunity.com/dev/apikey)
1. Drop sgsl.exe into an empty folder where you want your CS2 game server installed and click sgsl.exe. 
1. When sgsl.exe launches, select cs2 and click the install button.
1. After the sgsl restart, enter the GSLT, API auth key in the "Steam" game config tab.
1. Open up ports for CS2 in your router and firewall, e.g. look [here](https://portforward.com/counter-strike-2/)
1. ENJOY!

## Required files on standalone game servers

### steamcmd

If you have problems with cs2 not installing correctly,  it may be due to not having "Microsoft Visual C++ 2010 Redistributable Package (x86)" installed. It gets installed with e.g Steam, but if you are running a standalone game server without Steam installed you may have to install this package yourself. It is required by the steamcmd which is used for installing the game server.

Download it from here: https://www.microsoft.com/en-us/download/details.aspx?id=26999

Click Download and select both vcredist_x86.exe and vcredist_x64.exe. After the download finishes, simply run both installers. Now retry installing cs2.

### Other dependencies

According to my understanding a pure Windows 11 without the full cs2 game client (or just Steam?) installed doesn't contain all required libs and hence you must install the cs2 game client (or just Steam?) in order for the dedicated server to work.

Reference: https://steamcommunity.com/app/730/discussions/0/3881596897254177321/
Reference: https://steamcommunity.com/app/730/discussions/0/4335356354422173537/

Or you can just try and see if it works for you. This seems to be a moving target and your mileage may vary.

## Custom user config

Before starting a game server, sgsl writes all of its own cvars into `sgsl_overrides.cfg` (in `<install-path>\server\game\csgo\cfg`), and makes sure every `gamemode_<gamemode>.cfg` shipped by the game has a sibling `gamemode_<gamemode>_server.cfg` that simply execs `sgsl_overrides.cfg` -- this is what actually applies sgsl's settings, regardless of which gamemode ends up running. The "Generate sgsl_overrides.cfg" option on the General tab (on by default) controls this: turn it off to leave `sgsl_overrides.cfg` empty and let the game's own gamemode cfg files fully control server behavior instead.

If there is some special tweak you want to add, not supported by sgsl.exe, first of all you can of course request it by opening an issue. It can also be accomplished by adding your own config file in <install-path>\server\game\csgo\cfg and naming it sgsl_overrides_append.cfg. All config from this file will be copied into `sgsl_overrides.cfg`, last, prior to starting the game, allowing you to add or override whatever you like. Same format is used as in the original config file. This only happens while "Generate sgsl_overrides.cfg" is enabled -- it's ignored (like the rest of `sgsl_overrides.cfg`) when that option is off.

## Quirks

### Workshop maps not working

Most of the time workshop map just works, but if you run into problems, the reason could be that the workshop map is simply too old.
The workshop contains cs2 and csgo maps without a good possibility to distinguish between them. It has e.g. been left to the map author to properly tag the map. sgsl tries to determine if the map is a cs2 map or not and will display a dialog box with its findings but eventually it is up to you if you determine this is a cs2 or csgo map. If it isn't a proper cs2 map it will not work when you try to use it (cs2 will fallback to de_dust2). It is recommended to keep the "predownload map" option enabled to somewhat improve the probability of everything working out for you. If you don't predownload the map, it will be downloaded when you start the server, but it is hard to determine when the download has finished and the clients can start connecting.

If you restart sgsl and see a map named something like "legacy_<something>" that indicates this was an old map and it should simply be removed.

### Low FPS

Sometimes, for no reason, I get very low fps. Restarting the cs2 client GUI helps. Don't know why.

## LAN only play

Valve seems to (according to what I read online) have stopped supporting "sv_lan 1", i.e. a server which runs completely locally. Or rather, the server runs locally but the client will not be able to connect to a server setting "sv_lan 1". Therefore, as suggested, again online, I have set "sv_lan 0" unconditionally and use the "+sv_setsteamaccount" only when user select a public game. Most users will not notice this since it seems the sv_lan option is still there, just thought I'd mention it if someone happens to see that sv_lan is always set to 0.

## Notes

When you start the server an extra terminal window will appear. I haven't found a way to make it disappear, just minimize it if it bothers you.