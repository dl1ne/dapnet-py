
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import socket
import struct
import binascii
import string
import re
import datetime
import threading
import time
import crcmod

class ax25udp:

	""" 
		Layer 2 Frame
		=============

		|----------------------------------------------------------------------------------------------|
		| Destination Call + SSID | Source Call + SSID | via Digipeater | Control | PID    | Info Text |
		|----------------------------------------------------------------------------------------------|
		| A B C D E F      |  0   | A B C D E F |  0   |                |   0     |  0     |           |
		|----------------------------------------------------------------------------------------------|
		| 6 Byte           | 1 B  | 6 Byte      | 1 B  | up to 8x 7 B   | 1 B     | 1 Byte | 256 B     |
		|----------------------------------------------------------------------------------------------|
		| all Frames       | all  | all Frames  | all  | all Frames     | all     | only I | only I    |
		|----------------------------------------------------------------------------------------------|

						^----------------------^	    ^
							  /			     \
							 /			      \
							/			       \
					last call is masked with: 0x01,		special functions:
					via address is masked during		a.) poll/final bit, mask: 0x10
					repeating with:0x80			b.) rx-sequence and tx-sequence is masking
										    within the byte:
										    11101110
										    ^-^|^-^|
										    /  |  \ \
								    tx sequence	___/   |   \ \___  specifies I Frame
										      /     \
									      Poll Flag      rx sequence

		Remember:

											 Control Field
										       |-----------------|
										       |7|6|5| 4 |3|2|1|0|
										       |-----------------|

			==================================================================================
			I Frame:	- Poll Flag

				Frame							S E Q  P  S E Q 0
			==================================================================================
			S Frame:	- Poll/Final Flag

				Receive Ready			RR			S E Q P/F 0 0 0 1
				Receive Not Ready		RNR			S E Q P/F 0 1 0 1
				Reject				REJ			S E Q P/F 1 0 0 1
			==================================================================================
			U Frame:	- Poll/Final Flag

				Set Async Balanced Mode		SABM	Res		0 0 1  P  1 1 1 1
				Disconnect			DISC	Cmd		0 1 0  P  0 0 0 0
				Disconnect Mode			DM	Res		0 0 0  F  1 1 1 1
				Unnumbered Acknowledge		UA	Res		0 1 1  F  0 0 1 1
				Frame Reject			FRMR	Res		1 0 0  F  0 1 1 1
				Unnumbered Information		UI	Either		0 0 0 P/F 0 0 1 1
			==================================================================================



	""" 

	# Size of Headers
	L2_CALLLEN	= 6				# callsign max 6
	L2_SSIDLEN	= 1				# call ssid max 1
	L2_IDLEN	= L2_CALLLEN + L2_SSIDLEN	# complete call: callsign + ssid
	L2_VIACOUNT	= 8				# max 8 via fields
	L2_ADDR		= 2 * L2_IDLEN			# address fields (dst + src)
	L2_VIALEN	= L2_VIACOUNT * L2_IDLEN	# max size of digipeaters
	L2_PACLEN	= 255
	L2_INFOLEN	= L2_PACLEN - (L2_ADDR + L2_VIALEN + 2)

	# I Frame
	L2_CTRL_I	= 0x00

	# S Frame
	L2_CTRL_RR	= 0x01
	L2_CTRL_RNR	= 0x05
	L2_CTRL_REJ	= 0x09
	L2_CTRL_SREJ	= 0x0D

	# U Frame
	L2_CTRL_SABME	= 0x6F
	L2_CTRL_SABM	= 0x2F
	L2_CTRL_DISC	= 0x43
	L2_CTRL_DM	= 0x0F
	L2_CTRL_UA	= 0x63
	L2_CTRL_FRMR	= 0x87
	L2_CTRL_UI	= 0x03
	L2_CTRL_XID	= 0xAF
	L2_CTRL_TEST	= 0xE3

	# Mask
	L2_MASK_VIA	= 0x80
	L2_MASK_LAST	= 0x01
	L2_MASK_POLL	= 0x10	# also final bit


	P_VERSION	= "0.1"
	P_NAME		= "ax25udp-py"

	# Welcome Banner
	P_MOTD = "Welcome to " + P_NAME + ", " + P_VERSION + " (by DL1NE)\r"
	banner = ""

	# Connection Table
	connections = {}

	# build connections id
	def conid(self, packet, rx = True):
		if rx:
			( con_call, con_ssid, last ) = self.parseAX25call(packet, 7)
		else:
	                ( con_call, con_ssid, last ) = self.parseAX25call(packet, 0)
		return (con_call, con_ssid)

	# create connection entry
	def conmk(self, conid):
		if not conid in self.connections:
			self.connections[conid] = {}
			self.connections[conid]["tx_seq"] = 0
			self.connections[conid]["rx_seq"] = 0

	# remove connection entry
	def conrm(self, conid):
		if conid in self.connections:
			del self.connections[conid]

	# update connection state
	def conupd(self, conid, state = ""):
		if state != "":
			self.connections[conid]["state"] = state
		if not "state" in self.connections[conid]:
			return "UNKNOWN"
		return self.connections[conid]["state"]

	# set banner for connect
	def banner(self, msg = ""):
		if msg:
			if msg[:-2] != '\r':
				msg = msg + '\r'
			self.banner = msg
		return self.banner

	# decode received packet
	def decode(self, packet, rx = False):
		# get con and create connection
		conid = self.conid(packet, rx = rx)
		self.conmk(conid)
		if rx:
			stamp = "packet_rx"
		else:
			stamp = "packet_tx"
		self.connections[conid][stamp] = packet
		# build source and destination call signs
		( self.connections[conid]["dst_call"], self.connections[conid]["dst_ssid"], last ) = self.parseAX25call(packet, 0)
		( self.connections[conid]["src_call"], self.connections[conid]["src_ssid"], last ) = self.parseAX25call(packet, 7)

		# discard decoded fields
		packet = packet[14:]

		# check if digipeating/via is used
		self.connections[conid]["digipeater"] = []
		if not last:
			while len(packet) > 7 and packet[0] != 0x03 and not last:
				# decode digi
				(call, ssid, last) = self.parseAX25call(packet, 0)
				# append digi to list
				self.connections[conid]["digipeater"].append((call, ssid))
				# discard digi fields
				packet = packet[7:]

		# get control field
		self.connections[conid]["ctrl"] = self.parseAX25ctrl(packet[0:1])

		# discard control field, save byte for I Frame, to decode sequences
		ctrl = packet[0:1]
		packet = packet[1:]

		# reset some variables
		self.connections[conid]["pid"] = ""
		self.connections[conid]["info"] = ""

		# Received Frame is I Frame, try to get info field
		if self.connections[conid]["ctrl"] == "I":
			# next is pid, decode
			self.connections[conid]["pid"] = self.parseAX25pid(packet[0:1])
			# discard pid field
			packet = packet[1:]
			# next is info?
			# get infolen without crc fields
			infolen = len(packet) - 2
			if infolen > 0:
				# decode info field
				info = ""
				for i in range(infolen):
					p = packet[i:i+1]
					ichar = chr(ord(p))
					info += ichar
				self.connections[conid]["info"] = info.replace('\r','').replace('\n','')

		# Received Frame is I Frame, try to parse sequences
		if self.connections[conid]["ctrl"] == "I":
			(byte,) = struct.unpack("<B", ctrl)
			txn = (byte>>1 & 0x07)
			rxn = (byte>>5 & 0x07)
			# only 0-7 are valid as value
			if txn < 7:
				self.connections[conid]["rx_seq"] = txn + 1
			else:
				self.connections[conid]["rx_seq"] = 0

		return conid


	# parse ax25 control field
	def parseAX25ctrl(self, bytein):
		ctrl = ord(bytein)
		if ctrl & 0x01 == 0x00: # I Fame
			return "I"
		if ctrl & 0x03 == 0x01: # S Frame
			if ctrl & 0x0F == self.L2_CTRL_RR:		return "RR"	# Recv Ready
			if ctrl & 0x0F == self.L2_CTRL_RNR:		return "RNR"	# Recv Not Ready
			if ctrl & 0x0F == self.L2_CTRL_REJ:		return "REJ"	# Reject
			if ctrl & 0x0F == self.L2_CTRL_SREJ:		return "SREJ"	# Selective Reject
			return "UNKNOWN S-FRAME (" + hex(ctrl) + ")"
		if ctrl & 0x03 == 0x03: # U Frame
			if ctrl & 0xEF == self.L2_CTRL_SABME:		return "SABME"	# Connect Req EAX
			if ctrl & 0xEF == self.L2_CTRL_SABM:		return "SABM"	# Connect Req
			if ctrl & 0xEF == self.L2_CTRL_DISC:		return "DISC"	# Disconnect Req
			if ctrl & 0xEF == self.L2_CTRL_DM:		return "DM"	# Disconnect Mode
			if ctrl & 0xEF == self.L2_CTRL_UA:		return "UA"	# Unnumbered Ack
			if ctrl & 0xEF == self.L2_CTRL_FRMR:		return "FRMR"	# Frame Reject
			if ctrl & 0xEF == self.L2_CTRL_UI:		return "UI"	# Unnumbered Info
			if ctrl & 0xEF == self.L2_CTRL_XID:		return "XID"	# Exchange Ident
			if ctrl & 0xEF == self.L2_CTRL_TEST:		return "TEST"	# Test Frame
			return "UNKNOWN U-FRAME (" + hex(ctrl) + ")"
		return "UNKNOWN CTRL (" + hex(ctrl) + ")"


	# parse ax25 protocol id field
	def parseAX25pid(self, bytein):
		pid = ord(bytein)
		if pid & 0x30 in [0x10, 0x20]:		return "Layer 3 implemented"
		if pid == 0x01:				return "ISO 8208/CCITT X.25 PLP"
		if pid == 0x06:				return "Compressed TCP/IP"
		if pid == 0x07:				return "Uncompressed TCP/IP"
		if pid == 0x08:				return "Segmentation Fragment"
		if pid == 0xC3:				return "TEXNET Datagram Protocol"
		if pid == 0xC4:				return "Link Quality Protocol"
		if pid == 0xCA:				return "Appletalk"
		if pid == 0xCB:				return "Appletalk ARP"
		if pid == 0xCC:				return "ARPA Internet Protocol"
		if pid == 0xCD:				return "ARPA Address Resolution"
		if pid == 0xCE:				return "Flexnet"
		if pid == 0xCF:				return "NET/ROM"
		if pid == 0xF0:				return "No Layer 3"
		return "UNKNOWN PID"


	# parse ax25 callsign field (with ssid)
	def parseAX25call(self, byte, cursor = 0):
		if len(byte) >= self.L2_IDLEN:
			last = False
			if ord(byte[cursor+self.L2_IDLEN-1]) & self.L2_MASK_LAST:
				last = True
			call = ""
			ssid = 0
			ident_encoded = byte[cursor:cursor+self.L2_IDLEN]
			for p in range(self.L2_CALLLEN):
				c = chr((ord(ident_encoded[p]) >> 1) & 0x7F)
				if c != " " and c != "" and c != "-":
					call += c
			ssid = (ord(ident_encoded[self.L2_CALLLEN]) >> 1) & 0x0F
			return (call, ssid, last)
		else:
			return False


	# encode ascii callsign
	def encode_address(self, address, ssid = 0, final = False, via = False, direct = False):
		if ssid > 15:
			raise
		result = ""
		# encode callsign
		for letter in address.ljust(6):
			result += chr(ord(letter.upper()) << 1)
		# encode ssid and if needed,
		# set some flags for direct, via or final into ssid field
		rssid = (int(ssid) << 1) | 0b1100000
		if direct:		rssid = rssid | self.L2_MASK_VIA
		if not direct and via:	rssid = rssid & ~self.L2_MASK_VIA
		if final:		rssid = rssid | self.L2_MASK_LAST
		result += chr(rssid)
		return result

	# build a new packet
	def build(self, conid, ctrl, msg = "", poll = False):
		packet = self.encode_address(self.connections[conid]["src_call"], self.connections[conid]["src_ssid"])
		rlen = len(self.connections[conid]["digipeater"])
		if rlen > 0:
			# repeaters/via must fill into frame
			packet += self.encode_address(self.connections[conid]["dst_call"], self.connections[conid]["dst_ssid"], direct = True)
			rptcount = 0
			for i in self.connections[conid]["digipeater"]:
				# loop for adding one repeater after another, last repeater becames final flag
				rptcount = rptcount + 1
				if rptcount == rlen:	final = True
				packet += self.encode_address(i[0], i[1], via = True, final = final)
		else:
			# seems to be direct communication, not adding
			# repeaters/via field, and set direct flags
			packet += self.encode_address(self.connections[conid]["dst_call"], self.connections[conid]["dst_ssid"], final = True, via = True, direct = True)

		# poll/final flag is set
		if poll:
			packet += struct.pack("<B", ctrl | self.L2_MASK_POLL)
		else:
			# if packet is i frame, lets build sequence numbers for it
			if ctrl == self.L2_CTRL_I:
				left = self.connections[conid]["rx_seq"] << 5
				right = self.connections[conid]["tx_seq"] << 1
				packet += struct.pack("<B", (left | right))
			else:
				# otherwise, just put the control bit into
				packet += struct.pack("<B", ctrl)

		# I Frame, set Layer 3
		if ctrl == self.L2_CTRL_I:
			packet += struct.pack("<B", 0xF0) # no layer 3

		# Set info to Frame
		if msg:
			packet += struct.pack("<{}s".format(len(msg)), msg)

		# calculate CRC for packet
		crc = self.calc_crc(packet)
		self.connections[conid]["packet_tx"] = packet + crc
		return packet + crc


	def __init__(self,host,port,mycall,myssid):
	        self.host = host
	        self.port = port
		self.my_call = mycall
		self.my_ssid = myssid
	        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.x25_crc_func = crcmod.predefined.mkCrcFun('x-25')


	def swap16(self,x):
		data = struct.pack("<H", x)
		return data

	def calc_crc(self, packet):
		# Calculate the CRC
		c = self.x25_crc_func(packet)
		return self.swap16(c)


	def send(self, addr, conid, ctrl, msg = "", poll = False):
		# build new packet and send it to socket
		self.sock.sendto(self.build(conid, ctrl, msg, poll), addr)
		# if packet is i frame, we have to increase our counter
		if ctrl == self.L2_CTRL_I:
			# increase tx sequence
			if self.connections[conid]["tx_seq"] < 7:
				# max counter is 7, so lets do +1
				self.connections[conid]["tx_seq"] = self.connections[conid]["tx_seq"] + 1
			else:
				# max counter is reached, set it to zero
				self.connections[conid]["tx_seq"] = 0


	def prompt(self, addr, conid):
		# build prompt for user interaction
		self.send(addr, conid, self.L2_CTRL_I, self.connections[conid]["src_call"] + " de " + self.connections[conid]["dst_call"] + "-" + str(self.connections[conid]["dst_ssid"]) + "> ")


	def listen(self, callback = None):
		# lets bind our socket
		self.sock.bind((self.host, self.port))

		# run listening loop forever
		while True:
			# try to receive data from socket
			data, addr = self.sock.recvfrom(2048)
			# parse incoming packet and get connection id
			conid = self.decode(data, rx = True)

			# incoming packet is not for me ;-(
			if self.connections[conid]["dst_call"] != self.my_call or self.connections[conid]["dst_ssid"] != self.my_ssid:
				continue

			# incoming packet is connection request
			if self.connections[conid]["ctrl"] == "SABM":
				self.conmk(conid)
				self.send(addr, conid, self.L2_CTRL_UA, "", poll = True)
				# mark connections as established
				self.conupd(conid, "ESTABLISHED")
				self.send(addr, conid, self.L2_CTRL_I, self.P_MOTD)
				if self.banner:
					self.send(addr, conid, self.L2_CTRL_I, self.banner)
				self.prompt(addr, conid)

			# incoming packet is info frame
			if self.connections[conid]["ctrl"] == "I":
				# if no connection established, send disc
				if self.conupd(conid) != "ESTABLISHED":
					self.send(addr, conid, self.L2_CTRL_DISC, poll = True)

				# if callback is set, run into more functions
				# callback have to return (disc, tosend):
				# disc   = bool, Should connection be disconnected? Maybe request from user?
				# tosend = string, should we send an output to connected user?
				if not callback == None:
					(disc, tosend) = callback(self.connections[conid]["src_call"], self.connections[conid]["info"])
					# if disconnect request received, send DISC
					if disc:
						self.send(addr, conid, self.L2_CTRL_DISC, poll = True)
						self.conrm(conid)
						continue
					# if we have to send output, make sure that newline is set,
					# buffer the string and send i frame packet
					if tosend:
						if tosend[:-2] != '\r':
							tosend = tosend + '\r'
						while len(tosend)>0:
							plen = len(tosend)
							if len(tosend) > self.L2_INFOLEN:	plen = self.L2_INFOLEN
							self.send(addr, conid, self.L2_CTRL_I, tosend[0:plen])
							tosend = tosend[plen:]
				# send prompt back
				self.prompt(addr, conid)

			# incoming packet is disconnect request
			if self.connections[conid]["ctrl"] == "DISC":
				# only respond to existing connections
				if self.conupd(conid) == "ESTABLISHED":
					self.send(addr, conid, self.L2_CTRL_UA, poll = True)
					self.conrm(conid)


			# many more to fix here,
			# have to check if frames received from peer correctly,
			# handle frame and connection errors,
			# etc.
			# maybe if there is more time... :-)

