<img src="src/app/assets/icon.png" width="96" alt="sgsl icon">

# sgsl

Simple Game Server Launcher

[![Latest release](https://img.shields.io/github/v/release/lenosisnickerboa/sgsl.svg)](https://github.com/lenosisnickerboa/sgsl/releases/latest) [![Downloads](https://img.shields.io/github/downloads/lenosisnickerboa/sgsl/total.svg)](https://github.com/lenosisnickerboa/sgsl/releases) — [detailed download stats](https://somsubhra.github.io/github-release-stats/?username=lenosisnickerboa&repository=sgsl)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/lenosisnickerboa)

# The general idea - "One click install game server"

This is a simple game server launcher suitable for people wanting to quickly setup and host a game server for some friends to join without diving into all the details.

The "One click install game server" vision is hard to reach due to how games are developed, but I think this is still as close as you get. Create an empty directory for your server, drop sgsl.exe into it and start it, select game to install. Done. (Note that installing a game may take a while and will not produce continous output during the install. Just sit back and wait and let it finish.)

Currently supported games:
- <img src="src/game/cs2/assets/icon.png" width="24" alt=""> [Counter-Strike 2](src/game/cs2/README.md)
- <img src="src/game/csgo/assets/icon.png" width="24" alt=""> [Counter-Strike: Global Offensive](src/game/csgo/README.md)
- <img src="src/game/vu/assets/icon.png" width="24" alt=""> [Venice Unleashed](src/game/vu/README.md)

# Preconditions

For now requires Windows 11. Perhaps it works on previous Windows versions but I haven't tested it.

If a linux version is in high demand I will consider porting it to linux. sgsl is mostly python but there are some linux only things to consider when dealing with the actual game servers. So, I will be collecting requests for a while before starting this journey. Also, please state the linux distribution.

# Firewalls

The first time you start your server you will get questions from the Windows firewall. Simply accept all questions to allow access to your game server.

# Customization

On top of the already implemented game options, every game support the following levels of customization:

1. In the 'General' config tab of your game, select 'Edit run command' which will let you edit the command before it is used to start the game server. This edit will only apply to this game server start.
1. In the 'General' config tab of your game, there are options 'Custom run command (pre)' and 'Custom run command (post)' where you can add any options you want prepended or appended to the command line every time the server starts.
1. You can write config game specific config files named as the particular games config files, but with '_append' in the end of the config filename. The contents of this file will be appended to the game specific config file. Read more in the game specific README.md.

# Known limitations

[No game mode <-> map relation](https://github.com/lenosisnickerboa/sgsl/issues/1)

# Troubleshooting

As a a first hint, if something doesn't work, have a look in the terminal log to see more details of what failed. There is also the possibility to create an error report and file an [issue](https://github.com/lenosisnickerboa/sgsl/issues). I will do my best to analyze it. As always, the more time you put into the issue text, the less time I need to fix the issue.

**I have done my best to mask all sensitive data in the error report, but please inspect the complete report before submitting it to ensure nothing sensitive is leaked.**

## Developer information

If you want to develop sgsl on your own, [here](src/develop/README.md) are some hints.

# Some notes on my setup

I am currently only running local game servers and invite external players via the free [tailscale](https://tailscale.com/) but there is nothing stopping you from going public with your server. I have provided the necessary options and briefly described what is required in the game descriptions. 

I have a limited amount of people connecting to my servers and hence I find tailscale a simple and practical solution for this. It solves all problems for all kinds of game servers, not just the ones controlled by sgsl.exe, i.e. tailscale makes my game server host available to all invited as if they where directly connected to my LAN.

# A few words about the application, myself and AI

This application is mostly written in python, a language I have used from time to time but far from master. I have written this application as a hobby project since I wanted to play with python and occasionaly host game servers for connecting friends. I just want an easy way to host game servers and to offer others the same level of hosting I am content with. This is the game server launcher for dummies, but it offers quite a bit of simplified configuration should you want it. If you're an expert tinkerer this is probably not the application for you.

Also, a few words on AI, as it tends to be a popular topic right now (31 of July, 2026). I have designed the program structure, coded most of the basics from scratch and I have quite extensively used Claude to further improve functionality. Claude has many times surpassed my expectations, but also underperformed. I take full responsibility for the code though. I have reviewed and approved all Claude's changes. Just wanted to get that out of the way in case someone has strong opinions on "vibe coding". If it's not for you, just don't use sgls. And stop googling and copy-pasting from stack overflow...