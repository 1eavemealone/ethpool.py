import os
import logging
import time
import requests
import json
import sys
import signal
from flask import Flask, render_template, url_for, request
from threading import Thread
from threading import Lock

DEBUG = True
app = Flask(__name__)
app.config.from_object(__name__)

secret = "CHANGETHIS!"

def node_request (command, args = []):
	payload = { "method": command, "params": args, "jsonrpc": "2.0", "id": 0 }
	try:
		return requests.post('http://localhost:8545', data=json.dumps(payload), headers={'content-type': 'application/json'}).json()['result']
	except:
		return None


#url_for('static', filename='style.css')

@app.route("/submit", methods=['POST'])
def submitShare ():
	if request.form['secret'] == secret:
		print request.form
		print 'Secret is correct'
	return ''


@app.route("/")
def index():
	return render_template('index.html')


@app.route("/miner/<address>")
def miner(address):
	return render_template('index.html')


if __name__ == "__main__":
	app.run(threaded=True)
