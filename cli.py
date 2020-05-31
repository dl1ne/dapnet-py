import dapnetcli
import sys
import ax25udp

nodecall = "DB0AAA"
nodessid = 3

ax25udp_addr = "127.0.0.1"
ax25udp_port = 10090

cli = dapnetcli.DapNetCLI(nodecall, "<dapnet call>", "<dapnet password>")
cli.udpapi() # start api

ax25 = ax25udp.ax25udp(ax25udp_addr, ax25udp_port, nodecall, nodessid)
ax25.banner("DAPNET AX25UDP/PY v0.2, by DL1NE")
ax25.listen(cli.udphandler)

