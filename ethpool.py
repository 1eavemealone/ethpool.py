import os
import logging
import time
import requests
import json
import sys
import signal
import sqlite3
from flask import Flask, render_template, url_for, request
from threading import Thread, Lock
import Queue


# START - Parameters
SECRET = "CHANGETHIS"
SERVER_NAME = "localhost:5000"
SERVER_POOL = "localhost:5082"
DBSHARE_FILE = "ethshares.db"
DBPAYOUT_FILE = "ethpayout.db"
BLOCK_REWARD = 5.00
FEE = 0.2
COINBASE = "0x18f081247ad32af38404d071eb8c246cc4f33534"
# END - Parameters

DEBUG = True
app = Flask(__name__)
app.config.from_object(__name__)
shqueue = Queue.Queue ()
bllock = Lock ()
bl = False
paylock = Lock ()
cround = {'shares': 0, 'accounts': {}, 'miners': 0}
croundlock = Lock ()

def node_request (command, args = []):
	payload = { "method": command, "params": args, "jsonrpc": "2.0", "id": 0 }
	try:
		return requests.post('http://localhost:8545', data=json.dumps(payload), headers={'content-type': 'application/json'}).json()['result']
	except:
		return None


@app.route("/")
def index():
	return render_template('index.html', cround=cround, server=SERVER_POOL)

@app.route("/miner", methods=['POST'])
def miner ():
	address = request.form['address'].replace ('0x', '')
	payouts = []
	paylock.acquire ()
	conn2 = sqlite3.connect(DBPAYOUT_FILE)
	db2 = conn2.cursor()

	for row in db2.execute ('SELECT * FROM payout WHERE miner=?', [address]):
		payouts.append (row)

	conn2.commit ()
	conn2.close ()
	paylock.release ()

	if address in cround['accounts']:
		rshare = cround['accounts'][address]
	else:
		rshare = 0
	print rshare, cround
	return render_template('miner.html', address=address, payouts=payouts, shares=rshare)



@app.route("/submit", methods=['POST'])
def submitShare ():
	data = request.form
	if data['secret'] == SECRET:
		shqueue.put ((data['miner'], data['mixdigest'], data['diff'], str (time.time ())))
	return ''

@app.route("/foundblock", methods=['POST'])
def foundBlock ():
	bllock.acquire ()
	bl = True
	bllock.release ()


def sendTransaction (address, value):
	tx = { 'from': COINBASE, 'to': address, 'value': value }
	node_request ('eth_sendTransaction', [tx])

def db_thread ():
	global cround, bl
	conn = sqlite3.connect(DBSHARE_FILE)
	db = conn.cursor()

	while True:	
		for x in range (10):
			item = shqueue.get()
			db.execute ('INSERT INTO share VALUES (?,?,?,?)', item)	
			shqueue.task_done()
			conn.commit ()

			croundlock.acquire ()
			cround['shares'] += int (item [2])
			if item[0] in cround['accounts']:
				cround['accounts'][item[0]] += int (item [2])
			else:
				cround['accounts'][item[0]] = int (item [2])
			cround['miners'] = len (cround['accounts'])
			croundlock.release ()
		bllock.acquire ()

		# New block, split the reward
		if bl:
			bl = False
			bllock.release ()

			accounts = {}
			totshare = 0
			reward = BLOCK_REWARD - FEE
			for row in db.execute('SELECT miner, sum(share) FROM share GROUP BY miner'):
				accounts [row [0]] = row [1]
				totshare += row [1]

			# totshare : reward = sharegianni : rewardpergianni
			paylock.acquire ()
			conn2 = sqlite3.connect(DBPAYOUT_FILE)
			db2 = conn2.cursor()

			for acc in accounts:
				racc = accounts[acc] * reward / float (totshare)
				sendTransaction (acc, racc)
				db2.execute ('INSERT INTO payout VALUES (?,?,?,?)', [acc, accounts[acc], totshare, racc, str (time.time ())])	
			conn2.commit ()
			conn2.close ()
			paylock.release()

			db.execute ('DELETE FROM share')	

			croundlock.acquire ()
			cround = {'shares': 0, 'accounts': {}, 'miners': 0}
			croundlock.release ()
		else:
			bllock.realease ()

	conn.close ()

	

if __name__ == "__main__":
	if len (sys.argv) < 2:
		print 'usage:',sys.argv[0],'init|start'
	elif sys.argv[1] == 'init':
		try:
			conn = sqlite3.connect(DBSHARE_FILE)
			db = conn.cursor()
			db.execute('''CREATE TABLE share (miner text, mixdigest text, diff text, date text)''')
			conn.commit()
			conn.close()
		except:
			pass
		try:
			conn = sqlite3.connect(DBPAYOUT_FILE)
			db = conn.cursor()
			db.execute('''CREATE TABLE payout (miner text, shares int, roundshares int, amount real, time text)''')
			conn.commit()
			conn.close()
		except:
			pass
	elif sys.argv[1] == 'start':
		dbt = Thread(target=db_thread, args=())
		dbt.start()

		with app.app_context():
			url_for('static', filename='bootstrapflatly.min.css')
			url_for('static', filename='font-awesome.min.css')
		app.run(threaded=True)
