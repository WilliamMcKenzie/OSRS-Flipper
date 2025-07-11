import socket
import requests
import threading
import time
import math

# Server config
delay_secs = 10
connections = {}
port = 12855

# Create the server
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', port))
s.listen()

# Flipping data
flips = []
m = None
h = None
l = None

mapping = None
hourly = None
latest = None

def FetchData():
    global m, h, l, mapping, hourly, latest
    
    m = requests.get("https://prices.runescape.wiki/api/v1/osrs/mapping")
    h = requests.get("https://prices.runescape.wiki/api/v1/osrs/1h")
    l = requests.get("https://prices.runescape.wiki/api/v1/osrs/latest")
    
    mapping = m.json()
    hourly = h.json()["data"]
    latest = l.json()["data"] if "data" in l.json() else latest

def CompareSimilarity(n1, n2):
    if not n1 or not n2:
        return 1
    
    b = max(n1, n2)
    s = min(n1, n2)
    return (b - s) / s

def CheckVolatility(id, buy, sell):
    # Timetracker goes back 15 days and checks all price points
    # margin of 1h between each point
    t = requests.get(f"https://prices.runescape.wiki/api/v1/osrs/timeseries?timestep=1h&id={id}")
    timetracker = t.json()["data"] if "data" in  t.json() else []
    
    ceiling = 0
    floor = math.inf
    
    for data in timetracker:
        try:
            if (high := data["avgHighPrice"]) > ceiling:
                ceiling = high
            if (low := data["avgLowPrice"]) > ceiling:
                ceiling = low
        except:
            continue
    
    high_volatility = CompareSimilarity(buy, floor) > 0.1 or CompareSimilarity(sell, ceiling) > 0.1
    return high_volatility

def FlipCheck():
    global flips

    if not m:
        return

    flips = []
    for i in mapping:
        id = str(i["id"])
        if latest and id in latest and id in hourly:
            instabuy = latest[id]["high"]
            instasell = latest[id]["low"]
            
            sell_diff = CompareSimilarity(instabuy, hourly[id]["avgHighPrice"])
            buy_diff = CompareSimilarity(instasell, hourly[id]["avgLowPrice"])
            
            if instabuy and instabuy > 9 and instasell and "limit" in i and sell_diff < 0.1 and buy_diff < 0.1:
                sell_price = instabuy
                buy_price = instasell
                
                profit = ((sell_price - buy_price - math.floor(sell_price * 0.01)) * i["limit"])
                buy_volume = hourly[id]["lowPriceVolume"]
                sell_volume = hourly[id]["highPriceVolume"]
                ratio = buy_volume/sell_volume if sell_volume > 0 else -1
                
                valid_ratio = ratio > 0.75 and ratio < 1.5
                valid_profit = profit > 0
                valid_volume = buy_volume > 50000 and sell_volume > 50000
                
                if valid_ratio and valid_volume and valid_profit and CheckVolatility(id, buy_price, sell_price):
                #if not i["members"] and valid_volume:
                    # Append the flip, with its id, profit and how much it would cost to achieve that profit.
                    flips.append({
                        "name" : i["name"],
                        "id" : id,
                        "members" : i["members"],
                        "profit" : profit,
                        "profit_per_gp" : (profit/(i["limit"] * buy_price)),
                        "buy" : buy_price,
                        "sell" : sell_price,
                        "limit" : i["limit"]
                    })
    
    flips.sort(key=lambda flip : flip["profit_per_gp"], reverse=True)

def BuyItems():
    global flips, connections

    for id in connections:
        connection = connections[id]
        for flip in flips:
            if connection["gp"] < flip["buy"] or (flip["members"] and not connection["members"]):
                continue

            try:
                slots = connection["slots"]
                gp_avaliable = connection["gp"] / (len([slot for slot in connection["slots"] if not slot["id"]]))
                amount_to_buy = math.floor(gp_avaliable / flip["buy"])
                connection["gp"] -= flip["buy"] * amount_to_buy
                for i in range(len(slots)):
                    if slots[i]["id"] == None:
                        SendMessage(connection["socket"], f"buy {amount_to_buy} {flip["id"]} {flip["buy"]} {i}")
                        connection["slots"][i] = { "id" : flip["id"], "bought" : False, "amount" : amount_to_buy, "buy_price" : flip["buy"], "sell_price" : flip["sell"] }
                        break
            except:
                pass

def ReassessFlips():
    global flips, connections
    flips_by_id = {}

    for flip in flips:
        flips_by_id[flip["id"]] = flip

    for connection_id in connections:
        connection = connections[connection_id]

        for i in range(len(connection["slots"])):
            slot = connection["slots"][i]

            if slot["id"] in latest:
                id = slot["id"]
                prev_buy = slot["buy_price"]
                prev_sell = slot["sell_price"]
                buy_price = latest[id]["low"]
                sell_price = latest[id]["high"]

                if not slot["bought"] and prev_buy != buy_price:
                    SendMessage(connection["socket"], f"cancel buy {i}")
                    connection["slots"][i] = { "id" : None }
                elif slot["bought"] and CompareSimilarity(prev_sell, sell_price) > 0.2:
                    SendMessage(connection["socket"], f"cancel sell {i}")
                    connection["slots"][i] = { "id" : slot["id"], "bought" : False, "amount" : slot["amount"], "buy_price" : slot["buy_price"], "sell_price" : sell_price }

def Main():
    while True:
        FetchData()
        FlipCheck()
        BuyItems()
        ReassessFlips()
        time.sleep(delay_secs)

# Given a socket, send it a message
def SendMessage(socket, message):
    print(f"SENDING: {message}")

    encoded = message.encode()
    socket.send(len(encoded).to_bytes(2, 'big') + encoded)

# Given a socket, wait for it to send you a message
def RecieveMessage(socket):
    return socket.recv(1024).decode()

def AcceptConnections():
    global connections

    while True:
        c, (address, id) = s.accept()

        client_data = [int(data) for data in c.recv(1024).decode().split(" ") if data.isdigit()]
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
        account_thread.start()

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
                connections[id]["slots"][slot_index] = { "id" : None }
        elif type == "gp":
            [n, t, gp] = message
            connections[id]["gp"] = int(gp)


main_thread = threading.Thread(target=Main)
accept_thread = threading.Thread(target=AcceptConnections)

main_thread.start()
accept_thread.start()

