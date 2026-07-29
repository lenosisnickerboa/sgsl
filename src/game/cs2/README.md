# Counter-Strike 2 [Read more here](https://store.steampowered.com/app/730/CounterStrike_2/)

## Installation [Read more here](https://developer.valvesoftware.com/wiki/Counter-Strike_2/Dedicated_Servers)

Depending on how you want to run your server, here comes some scenarios.

### Simplest possible, LAN only, no workshop maps, just want to play locally with friends

1. Get your original CS2 working. Start it up and make sure you can run multiplayer.
1. Drop sgsl.exe into an empty folder where you want your CS2 game server installed and click sgsl.exe. 
1. When sgsl.exe launches, select cs2 and click the install button. I recommend first opening the terminal (Toggle to the far right).
1. ENJOY!

Your friends can now connect to you using the console command "connect <your-ip>" or by connecting via the local server browser steam://open/servers. You can create a Windows shortcut with target "steam://open/servers" and name "CS2 local servers" or simply run it with WIN+R, enter steam://open/servers and press ENTER.

### I want workshop maps

I'm not sure what the exact requirements are after googling, AI:ing, ... Some suggest you need a GSLT, some an API auth key. I eventually configured both to get it working. 

1. Get your original CS2 working. Start it up and make sure you can run multiplayer.
1. Register some stuff with Valve, like [GSLT](https://developer.valvesoftware.com/wiki/Counter-Strike_2/Dedicated_Servers#Registering_Game_Server_Login_Token) which can be done [here](http://steamcommunity.com/dev/managegameservers) and and [API auth key](https://steamcommunity.com/dev/apikey). Use 730 for the appId.
1. Drop sgsl.exe into an empty folder where you want your CS2 game server installed and click sgsl.exe. 
1. When sgsl.exe launches, select cs2 and click the install button. I recommend first opening the terminal (Toggle to the far right).
1. Enter the GSLT, API auth key
1. ENJOY!

### My friends are scattered over the Internet

If you want to have friends connect from outside your LAN the easy way is to just use [tailscale](https://tailscale.com/) or some other VPN solution. It's free and you can invite all your external friends to your game server. Once they are connected it again works just like they're all on your LAN. This is how I run things.

If you don't like this approach proceed to the next scenario.

### I want my server publically available

If you want your server publically available in the Valve server browser, and have friends connect to it from outside your LAN, this is what you need to do:

1. Get your original CS2 working. Start it up and make sure you can run multiplayer.
1. Register some stuff with Valve, like [GSLT](https://developer.valvesoftware.com/wiki/Counter-Strike_2/Dedicated_Servers#Registering_Game_Server_Login_Token) which can be done [here](http://steamcommunity.com/dev/managegameservers) and and [API auth key](https://steamcommunity.com/dev/apikey)
1. Drop sgsl.exe into an empty folder where you want your CS2 game server installed and click sgsl.exe. 
1. When sgsl.exe launches, select cs2 and click the install button. I recommend first opening the terminal (Toggle to the far right).
1. Enter the GSLT, API auth key. Also, set some good server name and password.
1. Open up ports for CS2 in your router and firewall, e.g. look [here](https://portforward.com/counter-strike-2/)
1. ENJOY!

## Required files on standalone game servers

### steamcmd

If you have problems with cs2 not installing it may be due to not having "Microsoft Visual C++ 2010 Redistributable Package (x86)" installed. It gets installed
with e.g Steam, but if you are running a standalone game server without Steam installed you may have to install this package yourself. It is required by the steamcmd which is used for installing the game server.

Download it from here: https://www.microsoft.com/en-us/download/details.aspx?id=26999

Click Download and select both vcredist_x86.exe and vcredist_x64.exe. After the download finishes, simply run both installers. Now retry installing cs2.

### Other dependencies

According to my understanding a pure Windows 11 without the full cs2 game client (or just Steam?) installed doesn't contain all required libs and hence you must install the cs2 game client (or just Steam?) in order for the dedicated server to work.

Reference: https://steamcommunity.com/app/730/discussions/0/3881596897254177321/
Reference: https://steamcommunity.com/app/730/discussions/0/4335356354422173537/

Or you can just try and see if it works for you. This seems to be a moving target and your mileage may vary.


## Custom user config

If there is some special tweak you want to add, not supported by sgsl.exe, it can be accomplished by adding your own config file in <install -path>\server\game\csgo\cfg and naming it gamemode_<gamemode>_append.cfg. All config from this file will be added last to the gamemode_<gamemode>.cfg file prior to starting the game allowing you to add or override whatever you like. Same format is used as in the original config file.