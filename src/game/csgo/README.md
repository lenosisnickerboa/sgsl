<img src="assets/icon.png" width="96" alt="Counter-Strike: Global Offensive icon">

# Counter-Strike: Global Offensive [Publisher docs](https://store.steampowered.com/app/4465480/CounterStrikeGlobal_Offensive/)

## Installation [Publisher docs](https://developer.valvesoftware.com/wiki/Counter-Strike:_Global_Offensive/Dedicated_Servers) and [here](https://steamcommunity.com/sharedfiles/filedetails/?id=3678325098)

Just a general note; installation takes time and terminal output is not continous (it is buffered) so you will just have to be patient. For me an install takes about 15 minutes.

Depending on how you want to run your server, here comes some scenarios.

A note first; csgo is discontinued and my only ambition with getting it to work is to be able to play locally with friends. To do this I had to do some things which might not be necessary, but it worked for me.

1. If running the game server and the game client on the same host, always start the game client **first** or Steam will detect the game already running.
1. Once the game client is running I got a message "Connecting to game servers...", I just ignored this and started the game server instead.
1. To connect to the game server I created a desktop shortcut with "steam://open/servers" as target and named it "Game server".
1. Click on the shortcut and now your server should be visible in the LAN tab. Or add a favourite...
1. Double-click on your server and the game client should start loading the correct map and now you can play.

I tried connecting using the console (connect localhost) and also the in-game server browser but never got that to work.

### Simplest possible, LAN only, no workshop maps, just want to play locally with friends

1. Get your original csgo client working. Since csgo is no longer searchable in Steam you have to perform a little quirk:
   Open this [link](https://store.steampowered.com/app/4465480/CounterStrikeGlobal_Offensive/)
   Add the game to your library, then head into Steam and install it as usual.
   Start it up and make sure you can run multiplayer.
   This info taken from [here](https://store.steampowered.com/app/4465480/CounterStrikeGlobal_Offensive/)
1. Drop sgsl.exe into an empty folder where you want your CSGO game server installed and click sgsl.exe. 
1. When sgsl.exe launches, select csgo and click the install button.
1. ENJOY!

Your friends should now be able to connect to you using the console command "connect <your-ip>" (but it didn't work for me) or by connecting via the local server browser steam://open/servers. You can create a Windows shortcut with target "steam://open/servers" and name "CSGO local servers" or simply run it with WIN+R, enter steam://open/servers and press ENTER.

### I want workshop maps

I'm not sure what the exact requirements are after googling, AI:ing, ... Some suggest you need a GSLT, some an API auth key. I didn't have to configure any of them but here's a description on how to configure both should you not get workshop maps working.

1. Get your original csgo working as described above.
1. Register some stuff with Valve, like [GSLT](https://zap-hosting.com/guides/docs/csgo-gslt/) which can be done [here](http://steamcommunity.com/dev/managegameservers) and [API auth key](https://steamcommunity.com/dev/apikey). Use 4465480 for the appId.
1. Drop sgsl.exe into an empty folder where you want your csgo game server installed and click sgsl.exe. 
1. When sgsl.exe launches select csgo and, click the install button. I recommend first opening the terminal (Toggle to the far right).
1. Enter the GSLT, API auth key
1. ENJOY!

### My friends are scattered over the Internet

If you want to have friends connect from outside your LAN the easy way is to just use [tailscale](https://tailscale.com/) or some other VPN solution. It's free and you can invite all your external friends to your game server. Once they are connected it again works just like they're all on your LAN. This is how I run things.

If you don't like this approach proceed to the next scenario.

### I want my server publically available

If you want your server publically available in the Valve server browser, and have friends connect to it from outside your LAN, this is what you need to do:

1. Get your original csgo working as described above. It is important that the game is installed prior to proceeding, it must exist in Steam before step 2 will be successful.
1. Register some stuff with Valve, like [GSLT](https://developer.valvesoftware.com/wiki/Counter-Strike_2/Dedicated_Servers#Registering_Game_Server_Login_Token) which can be done [here](http://steamcommunity.com/dev/managegameservers) and and [API auth key](https://steamcommunity.com/dev/apikey)
1. Drop sgsl.exe into an empty folder where you want your CSGO game server installed and click sgsl.exe. 
1. When sgsl.exe launches, select csgo and click the install button. I recommend first opening the terminal (Toggle to the far right).
1. Enter the GSLT, API auth key. Also, set some good server name and password.
1. Open up ports for CSGO in your router and firewall, e.g. look [here](https://portforward.com/counter-strike-global-offensive/)
1. ENJOY!

## Required files on standalone game servers

### steamcmd

If you have problems with csgo not installing it may be due to not having "Microsoft Visual C++ 2010 Redistributable Package (x86)" installed. It gets installed
with e.g Steam, but if you are running a standalone game server without Steam installed you may have to install this package yourself. It is required by the steamcmd which is used for installing the game server.

Download it from here: https://www.microsoft.com/en-us/download/details.aspx?id=26999

Click Download and select both vcredist_x86.exe and vcredist_x64.exe. After the download finishes, simply run both installers. Now retry installing CSGO.

### Other dependencies

According to my understanding a pure Windows 11 without the full csgo game client (or just Steam?) installed doesn't contain all required libs and hence you must install the csgo game client (or just Steam?) in order for the dedicated server to work.

Reference: https://steamcommunity.com/app/730/discussions/0/3881596897254177321/
Reference: https://steamcommunity.com/app/730/discussions/0/4335356354422173537/

Or you can just try and see if it works for you. This seems to be a moving target and your mileage may vary.

## Custom user config

If there is some special tweak you want to add, not supported by sgsl.exe, first of all you can of course request it by opening an issue. It can also be accomplished by adding your own config file in <install -path>\server\game\csgo\cfg and naming it gamemode_<gamemode>_append.cfg. All config from this file will be added last to the gamemode_<gamemode>.cfg file prior to starting the game allowing you to add or override whatever you like. Same format is used as in the original config file.

## Finding workshop content

In short; it's a mess, but most of the time you should be fine with using the same workshop items/ids as for [cs2](https://steamcommunity.com/workshop/browse/?appid=730). You can google it or ask your favourite AI companion about more details.

Also, read the [cs2 docs](../cs2/README.md) for more info.

## Quirks

Sometimes, for no reason, I get very low fps. Restarting the csgo client GUI helps. Don't know why.

## LAN only play

Valve seems to (according to what I read online) have stopped supporting "sv_lan 1", i.e. a server which runs completely locally. Or rather, the server runs locally but the client will not be able to connect to a server setting "sv_lan 1". Therefore, as suggested, again online, I have set "sv_lan 0" unconditionally and use the "+sv_setsteamaccount" only when user select a public game. Most users will not notice this since it seems the sv_lan option is still there, just thought I'd mention it if someone happens to see that sv_lan is always set to 0.

## Notes

When you start the server an extra terminal window will appear. I haven't found away to make it disappear, just minimize it if it bothers you.