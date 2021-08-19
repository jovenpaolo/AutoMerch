import websocket, json, pprint
import numpy as np
import config
import pandas as pd
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
import logging

LOG = "history.log"                                                     
logging.basicConfig(filename=LOG,
 level=logging.DEBUG, 
 format='%(asctime)s %(message)s', 
 datefmt='%d/%m/%Y %H:%M:%S')  

#SOCKET = "wss://stream.binance.com:9443/ws/btcusdt@kline_1m"
SOCKET = "wss://testnet.binance.vision/ws/btcusdt@kline_1m"

TRADE_SYMBOL = 'BTCUSDT'
#TRADE_QUANTITY = 0.5

closes = []
opens = []
highs = []
lows = []
threshold = 0.001
in_position = False

client = Client(config.API_KEY, config.API_SECRET, testnet= True)

balancebtc = client.get_asset_balance(asset='BTC')
balanceusdt = client.get_asset_balance(asset='USDT')

print(balancebtc)
print(balanceusdt)
#create def for computing exchange rates
#quantity=100%
def order(side, quantity, symbol,order_type=ORDER_TYPE_MARKET):
    try:
        print("sending order")
        order = client.create_order(symbol=symbol, side=side, type=order_type, quantity=quantity)
        print(order)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return True

    
def on_open(ws):
    print('opened connection')

def on_close(ws):
    print('closed connection')

def on_message(ws, message):
    global closes, in_position, opens, highs, lows, threshold
    
    print('received message')
    json_message = json.loads(message)
    #pprint.pprint(json_message)

    candle = json_message['k']

    is_candle_closed = candle['x']
    close1 = candle['c']
    open1 = candle['o']
    high1 = candle['h']
    low1 = candle['l']

    if is_candle_closed:
        print("candle closed at {}".format(close1))
        closes.append(float(close1))
        opens.append(float(open1))
        highs.append(float(high1))
        lows.append(float(low1))
        
        print("closes")
        print(closes)
        

        if len(closes) > 3:
            closes.pop(0)
            opens.pop(0)
            lows.pop(0)
            highs.pop(0)
            
            print("closespop")
            print(closes)
        
            np_closes = np.array(closes)
            np_opens = np.array(opens)
            np_lows = np.array(lows)
            np_highs = np.array(highs)
            
            #convert to Heiken Ashi
            df = pd.DataFrame({'Open': np_opens,'High': np_highs, 'Low': np_lows,'Close': np_closes })
            
            ha_close=(pd.to_numeric(df.Open)+pd.to_numeric(df.Low)+pd.to_numeric(df.High)+pd.to_numeric(df.Close))/4
            ha_open=(pd.to_numeric(df.Open.shift(periods=1))+pd.to_numeric(df.Close.shift(periods=1)))/2
            ha_height=100*(ha_close-ha_open)/ha_close
            df['HaPercentChange']= ha_height

            df['larger1'] = np.logical_and(abs(df.HaPercentChange) > threshold, abs(df.HaPercentChange.shift(1)) > threshold)
            df['red'] = np.logical_and(df.HaPercentChange < 0, df.HaPercentChange.shift(1) < 0)
            df['green'] = np.logical_and(df.HaPercentChange > 0, df.HaPercentChange.shift(1) > 0)
            
            df[["larger1","green"]] *= 1
            df[["red"]] *= -1
            df["custom"] = df["larger1"]*(df["green"]+df["red"])
            print('heiken')
            print(df)
            if df.iloc[-1,-1] == 1: #bullish
                if in_position:
                    print("Bull sign, but you already own it, nothing to do.")
                    logging.info('Bull sign, but you already own it, nothing to do.')
                else:
                    print("Bullish! Buy! Buy! Buy!")
                    # put binance buy order logic here
                    usdtprice = client.get_asset_balance(asset='USDT')
                    TRADE_QUANTITY=round(closes[2]/float(usdtprice['free']), 4)
                    order_succeeded = order(SIDE_BUY, TRADE_QUANTITY, TRADE_SYMBOL)
                    
                    if order_succeeded:
                        logging.info('BOUGHT BTC')
                        in_position = True
            if df.iloc[-1,-1] == -1: #bearish
                if in_position:
                    print("Bear Warning! Sell! Sell! Sell!")
                    # put binance sell logic here
                    TRADE_QUANTITY = client.get_asset_balance(asset='BTC')
                    order_succeeded = order(SIDE_SELL, float(TRADE_QUANTITY['free']), TRADE_SYMBOL)
                    if order_succeeded:
                        logging.info('SOLD BTC')
                        in_position = False
                else:
                    print("Bear warning, but we don't own any. Nothing to do.")
                    logging.info("Bear warning, but we don't own any. Nothing to do.")
            else:
                print('do nothing')
            
            
ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message)
ws.run_forever()