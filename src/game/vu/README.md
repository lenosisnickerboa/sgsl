# Venice Unleashed [Read more here](https://veniceunleashed.net/)

## Installation [Read more here](https://docs.veniceunleashed.net/hosting/prereq/)

Depending on how you want to run your server, here comes some scenarios.

### Simplest possible, LAN only, just want to play locally with friends

1. Get your original BF3 working. Start it up and make sure you can run multiplayer.
1. Register some stuff with VU, like a VU account, linking of your VU and Origin account and a server key.
1. Drop sgsl.exe into an empty folder where you want your VU game server installed and click sgsl.exe.
1. When sgsl.exe launches, click the install button. I recommend first opening the terminal (Toggle to the far right).
1. When sgsl.exe relaunches, enter the server key in the sgsl.exe config.
1. Start your server.
1. ENJOY!

Your friends need to install the VU client and register as described on the VU site when downloading VU. After that they will be able to see your server in the VU server browser.

### My friends are scattered over the Internet

If you want to have friends connect from outside your LAN the easy way is to just use [tailscale](https://tailscale.com/) or some other VPN solution. It's free and you can invite all your external friends to your game server. Once they are connected it again works just like they're all on your LAN. This is how I run things.

If you don't like this approach proceed to the next scenario.

### I want my server publically available

If you want your server publically available in the VU server browser, and have friends connect to it from outside your LAN, this is what you need to do:

1. Get your original BF3 working. Start it up and make sure you can run multiplayer.
1. Register some stuff with VU, like a VU account, linking of your VU and Origin account and a server key.
1. Drop sgsl.exe into an empty folder where you want your VU game server installed and click sgsl.exe. 
1. When sgsl.exe launches, click the install button. I recommend first opening the terminal (Toggle to the far right).
1. When sgsl.exe relaunches, enter the server key in the sgsl.exe config.
1. Start your server.
1. Open up ports for VU in your router and firewall, e.g. look [here](https://docs.veniceunleashed.net/hosting/setup-win/#port-forwarding)
1. ENJOY!
