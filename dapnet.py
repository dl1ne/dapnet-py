import requests
from requests.auth import HTTPBasicAuth
import json
import os
import time
from datetime import datetime
import configparser

class DapNet:
	api_url = "dapnet.di0han.as64636.de.ampr.org";
	api_prefix = "/api/"
	api_user = "";
	api_pass = "";
	api_proto = "http://"
	api_alternate_port = "8080"
	api_timeout = 4

	use_alternate_port = False

	debug = False

	callsigns = {}
	regions = [ "dl-ni" ]

	dapnet_nodes = {}
	dapnet_failure = []

	config = configparser.RawConfigParser()
	config_file = "./dapnet.ini"

	def __init__(self, api_user, api_pass, url = ""):
		self.api_user = api_user
		self.api_pass = api_pass
		if url != "":
			self.api_url = url

		self.callsigns = self.get_userlist()
		self.nodes_fetch()


	def debugme(self, txt):
		if self.debug:
			print("DEBUG:  " + str(txt))


	def makereq(self, json_path, post_data = ""):
		fail = False
		if post_data == "":
			self.debugme("API-Request via GET")
			self.debugme("Query: " + self.api_proto + self.api_url + self.api_prefix + json_path)
			try:
				res = requests.get(self.api_proto + self.api_url + self.api_prefix + json_path, auth=HTTPBasicAuth(self.api_user, self.api_pass), timeout=self.api_timeout)
			except:
				fail = True
		else:
			headers = {'Content-type': 'application/json'}
			payload = json.dumps(post_data)
			self.debugme("API-Request via POST")
			self.debugme("Query: " + self.api_proto + self.api_url + self.api_prefix + json_path)
			self.debugme("JSON : " + payload)
			try:
				res = requests.post(self.api_proto + self.api_url + self.api_prefix + json_path, data=payload, headers=headers, auth=HTTPBasicAuth(self.api_user, self.api_pass), timeout=self.api_timeout)
			except:
				fail = True
		if fail or (res.status_code != 200 and res.status_code != 201):
			self.debugme("API not reachable, trying another one - if available...")
			self.dapnet_failure.append(self.api_url)
			if not self.use_alternate_port:
				self.api_url = self.api_url + ":" + self.api_alternate_port
				self.use_alternate_port = True
				self.api_prefix = "/"
			else:
				self.use_alternate_port = False
				self.api_prefix = "/api/"
				self.nodes_select()
			return self.makereq(json_path, post_data)
		else:
			return res.json()


	def get_nodelist(self):
		nodes = self.makereq("nodes")
		return nodes

	def get_userlist(self):
		users = self.makereq("users")
		self.debugme("Fetched userlist:")
		self.debugme(str(users))
		return users

	def get_rubriclist(self):
		rubrics = self.makereq("rubrics")
		return rubrics

	def get_transmitterlist(self):
		transmitters = self.makereq("transmitters")
		return transmitters

	def get_nodelist(self):
		nodes = self.makereq("nodes")
		return nodes

	def get_dapnetnode(self):
		return self.api_url

	def get_dapnetuser(self):
		return self.api_user

	def check_user(self, callsign):
		found = False
		self.debugme("Checking if call " + str(callsign) + " is existing...")
		for call in self.callsigns:
			if call["name"].upper() == callsign.upper():
				found = True
				self.debugme("Found callsign in list! :-)")

		if not found:
			self.debugme("Callsign is not in list :-(")

		return found


	def page_user(self, callsigns, txt, emergency = False, regions = ""):
		if regions != "":
			self.regions = regions
		data = {}
		data["text"] = txt
		data["emergency"] = emergency
		data["transmitterGroupNames"] = self.regions
		calls = []
		pagecall = []
		found = False
		res = False
		if type(callsigns) is str:
			self.debugme("Call is only string, convert it to list...")
			pagecall = callsigns.split(',')
		else:
			self.debugme("Call is already list, passthrough...")
			pagecall = callsigns


		self.debugme("List is now: " + str(pagecall))
		for call in pagecall:
			if self.check_user(call):
				calls.append(call)
				found = True
			else:
				print("Warning: Call " + call + " not found, could not submit transmitting job.")
		if found:
			data["callSignNames"] = calls
			self.debugme("Lets run function makereq() to send page to api...")
			res = self.makereq("calls", data)
		return res

	def nodes_fetch(self):
		res = self.get_nodelist()
		if not 'nodes' in self.config:
			self.config.add_section('nodes')
		nodes = res
		for node in nodes:
			if not node["address"] == None:
				self.config.set('nodes', node["name"], node["address"]["ip_addr"])
		with open(self.config_file, 'w') as configfile:
			self.config.write(configfile)

	def nodes_select(self):
		self.config.read(self.config_file)
		if 'nodes' in self.config:
			self.debugme("Nodes in configuration existing")
			self.dapnet_nodes = self.config["nodes"]
		else:
			self.debugme("Could not get nodes from configuration file!")
		found = False
		for node in self.dapnet_nodes:
			if not self.dapnet_nodes[node] in self.dapnet_failure:
				self.debugme("Checking Node " + node + " / " + self.dapnet_nodes[node])
				self.api_url = self.dapnet_nodes[node]
				found = True
				break
		if not found:
			exit(1)

	def testing(self):
		for call in self.get_userlist():
			print(call)
		self.page_user("dl1ne", "nur ein test :-)")


