import socket
import sys
import os
import atexit
import requests
import threading
import time
import math
import json

versionname = "v99.3.5" # ----- UPDATE VERSION NAME EACH UPDATE -----

headers = {
	'User-Agent': 'Osrs real time prices graphing',
}

tax = 0.02
delay_secs = 10
connections = {}
port = 12856

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', port))
s.listen()

flips = []
m = None
h = None
l = None

mapping = None
hourly = None
latest = None

def FetchData():
	global m, h, l, mapping, hourly, latest
	m = requests.get("https://prices.runescape.wiki/api/v1/osrs/mapping",headers=headers)
	h = requests.get("https://prices.runescape.wiki/api/v1/osrs/1h",headers=headers)
	l = requests.get("https://prices.runescape.wiki/api/v1/osrs/latest",headers=headers)
	
	mapping = m.json()
	hourly = h.json()["data"]
	latest = l.json()["data"]

def CheckItems(mapping, hourly, latest):
	global flips
	
	if mapping and latest and hourly:
		flips = []
		
		for item in mapping:
			id = str(item["id"])
			
			if id in hourly and "limit" in item:
				h = hourly[id]
				l = latest[id]
				limit = item["limit"]
				
				if (total_volume := h["highPriceVolume"] + h["lowPriceVolume"]) > 25000 and (avgHigh := h["avgHighPrice"]):
					buy_price = l["low"] + 1
					sell_price = l["high"] - 1
					
					profit = (sell_price - buy_price - math.floor(sell_price * tax)) * limit
					
					# Make sure we will be able to sell it in the future by checking against the average sell price an hour back
					valid_sellability = avgHigh > sell_price
					
					if profit > 0 and not item["members"] and valid_sellability:
						flips.append({
							"id" : id,
							"name" : item["name"],
							"profit" : profit,
							"limit" : limit,
							"members" : item["members"],
							"value" : profit / (buy_price  * limit),
							"buy" : buy_price,
							"sell" : sell_price
						})
		
		flips.sort(key=lambda flip : flip["value"], reverse=False)

def PrintFlips(flips):
    os.system('clear')
    for flip in flips:
        print(flip["name"])
        print(flip["profit"])
        print(f"Buy: {flip["buy"]}")
        print(f"Sell: {flip["sell"]}")
        print(flip["value"])
        print("\n")





def BuyItems(flips, connections):
	for id in connections:
		connection = connections[id]
		for flip in flips:
			buy_price = flip["buy"]
			sell_price = flip["sell"]
			slots = connection["slots"]
			empty_slots = len([slot for slot in slots if not slot["id"]])
			gold_avaliable = connection["gp"] / empty_slots
			
			if gold_avaliable >= buy_price and (not flip["members"] or connection["members"]):
				try:
					buy_quantity = math.floor(gold_avaliable / buy_price)
					connection["gp"] -= buy_price * amount_to_buy
					
					for i in range(len(slots)):
						if slots[i]["id"] == None:
							SendMessage(connection["socket"], f"buy {buy_quantity} {flip["id"]} {buy_price} {i}")
							connection["slots"][i] = { 
								"id" : flip["id"],
								"bought" : False,
								"amount" : buy_quantity,
								"buy_price" : buy_price,
								"sell_price" : sell_price,
								"gp_spent": buy_price * buy_quantity,
								"gp_earned": 0}
							break
				except:
					pass

def SendMessage(socket, message):
	encoded = message.encode()
	socket.send(len(encoded).to_bytes(2, 'big') + encoded)

def RecieveMessage(socket):
    return socket.recv(1024).decode()

def AcceptConnections():
    global connections
    
    while True:
        try:
            print("Accepting connections")
            c, (address, id) = s.accept()
            
            client_data = [int(data) for data in c.recv(1024).decode().split(" ") if data.isdigit()]
            os.system('clear')
            print(f"Recieved connection from {address}")
            print(f"GP: {client_data[0]}  SLOTS: {client_data[1]}")
            
            slots = [ { "id" : None } for i in range(client_data[1]) ]
            connections[id] = {
                "commands" : [],
                "socket" : c,
                "gp" : client_data[0],
                "slots" : slots,
                "members" : client_data[1] > 3
            }
            
            account_thread = threading.Thread(target=ManageAccount,args=[id])
            account_thread.daemon = True
            account_thread.start()
        except:
            print("Error accepting connections")
            os._exit(1)

def ManageAccount(id):
    while True:
        message = RecieveMessage(connections[id]["socket"]).split(" ")
        type = message[1]
        
        if type == "collected":
            [n, t, slot_index] = message
            slot_index = int(slot_index)
            slot = connections[id]["slots"][slot_index]

            if not "bought" in slot or not slot["bought"]:
                connections[id]["slots"][slot_index]["bought"] = True

                high = latest[slot["id"]]["high"] if slot["id"] in latest else 0
                sell_price = max(high, slot["sell_price"])

                SendMessage(connections[id]["socket"], f"sell {slot["amount"]} {slot["id"]} {sell_price} {slot_index}")
            else:
                sell_price = slot["sell_price"]
                earned_gp = sell_price * slot["amount"] - math.floor(sell_price * slot["amount"] * tax)
                slot["gp_earned"] = earned_gp
                connections[id]["slots"][slot_index] = { "id" : None }
        elif type == "gp":
            [n, t, gp] = message
            connections[id]["gp"] = int(gp)

def Exit():
    input("Enter to stop server\n")
    s.close()
    
exit_thread = threading.Thread(target=Exit)
exit_thread.daemon = True
exit_thread.start()

server_thread = threading.Thread(target=AcceptConnections)
server_thread.daemon = True
server_thread.start()

def exit_handler():
    s.close()

atexit.register(exit_handler)

while True:
	FetchData()
	CheckItems(mapping, hourly, latest)
	PrintFlips(flips)
	
	time.sleep(delay_secs)










def DataCollection():
	while True:
		# Opens data file
		with open("profitdata.json", "r") as profit_file:
			profitdata = json.load(profit_file)
        
		# Initializes data vars from current version, if not found then returns 0 on all values
		versiondata = profitdata.get(versionname, {
			"time-ran-mins": 0,
			"avg-roi": 0,
			"total-spent-gp": 0,
			"total-earned-gp": 0,
			"total-profit-gp": 0
		})

		# Updates and prints data every 10 seconds
		for i in range(3):
			versiondata["time-ran-mins"] = round(versiondata["time-ran-mins"] + 0.1667, 4)

			totalspent = totalearned = 0
			for conn in connections.values():
				for slot in conn["slots"]:
					if slot.get("gp_spent"):
						totalspent += slot["gp_spent"]
					if slot.get("gp_earned"):
						totalearned += slot["gp_earned"]
				slot["gp_spent"] = slot["gp_earned"] = 0
			versiondata["total-spent-gp"] += totalspent
			versiondata["total-earned-gp"] += totalearned
            
			versiondata["avg-roi"] = (versiondata["total-earned-gp"]/versiondata["total-spent-gp"] - 1) if versiondata["total-spent-gp"]>0 else 0
			versiondata["total-profit-gp"] = versiondata["total-earned-gp"] - versiondata["total-spent-gp"]
			
			print(f"RSMM {versionname}: Avg. ROI: {versiondata["avg-roi"]*100:.2f}%. Total Profit: {versiondata["total-profit-gp"]} GP. Time Ran: {math.floor(versiondata["time-ran-mins"])} min.")
			time.sleep(10)
		
		# Every 30 seconds, compiles and sends updated version data to file
		profitdata[versionname] = versiondata
		with open("profitdata.json", "w") as profit_file:
			json.dump(profitdata, profit_file, indent=4)

#data_thread = threading.Thread(target=DataCollection)
#data_thread.start()
