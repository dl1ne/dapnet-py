from __future__ import print_function
import json
import os
import time
from datetime import datetime
import dapnet

class DapNetCLI:

	api = None
	api_url = "dapnet.di0han.as64636.de.ampr.org"
	api_user = ""
	api_pass = ""

	my_call = ""
	user_call = ""

	prompt = ""

	default_regions = [ ]


	commands = {	"help":			"Shows this help message" ,
			"exit":			"Disconnect from this session" ,
			"quit":			"Disconnect from this session" ,
			"nodelist": 		"Shows a list of all registeres nodes/cores" ,
			"userlist": 		"Shows a list of registered users",
			"transmitterlist":	"Shows a list of registered transmitters",
			"rubriclist":		"Shows all configured rubrics",
			"page":			"Sends a message to an user/pager",
			"sregion":		"Sets the region to transmit",
			"semergency":		"Sets the emergency mode for calls",
			"set":			"Shows all running parameters" }


	help_txt = {	"page":			"Sends a message to an user/pager,\n"
					+	"the message is sent to transmitters in the sregion list,\n"
					+	"if you wish to address multiple callsigns in one command,\n"
					+	"please use the comma as seperator.\n"
					+	"\n"
					+	"Syntax:\n"
					+	"page <callsign> <message>\n",
			"sregion":		"Sets the region to transmit,\n"
					+	"you can specify one group - or multiple,\n"
					+	"please use the comma as seperator.\n"
					+	"\n"
					+	"Syntax:\n"
					+	"sregion <destregion>\n" }


	arguments = ""
	argparse = False

	list_node = {}
	list_tx = {}
	list_user = {}
	list_rubric = {}

	page_emergency = False

	def __init__(self, my_call, api_user, api_pass, default_regions = [ "dl-ni" ], api_url = ""):
		self.api_user = api_user
		self.api_pass = api_pass
		self.my_call = my_call
		self.default_regions = default_regions
		if api_url != "":
			self.api_url = api_url


	def check_input(self, input):
		if input == "":
			return
		words = input.split()
		self.arguments = words
		if len(words)>1:
			self.argparse = True
		else:
			self.argparse = False
		count = 0
		func = ""
		for cmd in self.commands:
			if words[0] in cmd:
				count = count + 1
				func = cmd
		if count < 1:
			self.msg("Command not found, try help for more information.")
			return
		if count > 1:
			self.msg("Ambiguous command, try help for more information.")
			return
		eval("self.cmd_" + func + "()")


	def msg(self, txt):
		print(txt)

	def fmsg(self, txt, fields, newline = True):
		if newline:
			print(txt % fields)
		else:
			print(txt % fields, end='')

	def sortTuple(self, tup, field = 1):
		lst = len(tup)
		for i in range(0, lst):
			for j in range(0, lst-i-1):
				if tup[j][field] > tup[j + 1][field]:
					temp = tup[j]
					tup[j] = tup[j + 1]
					tup[j + 1] = temp
		return tup


	def help(self, topic):
		if topic in self.help_txt:
			for line in self.help_txt[topic].split('\n'):
				self.msg(line)
		else:
			self.msg("No help found!")



	def cmd_page(self):
		if not self.argparse:
			self.help("page")
			return
		if len(self.arguments) < 3:
			self.help("page")
			return
		destcall = self.arguments[1]
		message = ' '.join(self.arguments).replace("page " + destcall + " ", "")
		message = self.user_call.upper() + ": " + message
		res = self.api.page_user(destcall, message, self.page_emergency, self.default_regions)
		self.msg("Result:")
		self.msg(res)


	def cmd_set(self, filter = ""):
		self.msg("- SET -")
		tmp = { "Host Call":		"self.my_call",
			"User Call":		"self.user_call",
			"DapNet API Node":	"self.api.get_dapnetnode()",
			"DapNet API User":	"self.api.get_dapnetuser()",
			"Regions":		"self.default_regions",
			"Emergency":		"self.page_emergency" }
		for e in tmp:
			if filter != "" and filter not in tmp[e]:
				continue
			v = eval(tmp[e])
			self.fmsg("%-18s : %s", (e, v))


	def cmd_sregion(self):
		if not self.argparse:
			self.help("sregion")
			return
		if len(self.arguments) < 2:
			self.help("sregion")
			return
		region = ' '.join(self.arguments).replace(self.arguments[0] + " ", "").split(" ")
		self.default_regions = region
		self.cmd_set("regions")


	def cmd_semergency(self):
		if not self.argparse:
			self.help("semergency")
			return
		if len(self.arguments) < 2:
			self.help("semergency")
			return
		if str(self.arguments[1]).upper() in "TRUE" or str(self.arguments[1]) == "1" or str(self.arguments[1]).upper() in "YES":
			self.page_emergency = True
		else:
			self.page_emergency = False
		self.cmd_set("emergency")


	def cmd_nodelist(self):
		self.msg("- NODELIST -")
		if len(self.list_node) < 1:
			self.list_node = self.sortTuple(self.api.get_nodelist(), "name")
		for node in self.list_node:
			if self.argparse and not self.arguments[1] in node["name"]:
				continue
			self.fmsg("%-16s Status: %s", (node["name"], node["status"]))

	def cmd_userlist(self):
		self.msg("- USERLIST -")
		if len(self.list_user) < 1:
			self.list_user = self.sortTuple(self.api.get_userlist(), "name")
		count = 0
		for user in self.list_user:
			if self.argparse and not self.arguments[1] in user["name"]:
				continue
			if count > 4:
				self.msg(" ")
				count = 0
			self.fmsg("%-16s", user["name"], False)
			count = count + 1
		self.msg(" ")


	def cmd_transmitterlist(self):
		self.msg("- TRANSMITTERLIST -")
		if len(self.list_tx) < 1:
			self.list_tx = self.sortTuple(self.api.get_transmitterlist(), "name")
		self.fmsg("%-6.6s : %-6.6s : %-24.24s : %s", ("CALL", "NODE", "TYPE", "STATUS"))
		for tx in self.list_tx:
			if self.argparse and not self.arguments[1] in tx["name"] and (tx["nodeName"] == None or not self.arguments[1] in tx["nodeName"]):
				continue
			self.fmsg("%-6.6s : %-6.6s : %-24.24s : %s", (tx["name"], tx["nodeName"], tx["deviceType"], tx["status"]))


	def cmd_rubriclist(self):
		self.msg("- RUBRICLIST -")
		if len(self.list_rubric) < 1:
			self.list_rubric = self.sortTuple(self.api.get_rubriclist(), "number")
		self.fmsg("%02s : %-16.16s : %-14.14s : %s", ("NR", "NAME", "LABEL", "TRANSMITTERGROUPS"))
		for r in self.list_rubric:
			if self.argparse and not self.arguments[1] in r["name"] and not self.arguments[1] in str(r["number"]):
				continue
			self.fmsg("%02d : %-16.16s : %-14.14s : %s", (r["number"], r["name"], r["label"], ','.join(r["transmitterGroupNames"])))


	def cmd_help(self):
		self.msg("- HELP -")
		keylist = self.commands.keys()
		keylist.sort()
		for key in keylist:
			self.fmsg("%-15s - %s", (key, self.commands[key]))

	def cmd_quit(self):
		self.disconnect()

	def cmd_exit(self):
		self.disconnect()

	def disconnect(self):
		exit(0)

	def run(self, usercall):
		self.user_call = usercall
		self.prompt = self.user_call + " de " + self.my_call + "> "
		self.api = dapnet.DapNet(self.api_user, self.api_pass, self.api_url)
		loop = True
		while loop:
			self.check_input(raw_input(self.prompt))
