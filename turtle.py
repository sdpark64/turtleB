import ccxt 
import pprint
import time
import datetime
import pandas as pd
import numpy as np
import math
import logging
import telegram

my_token = '1721040065:AAEL2MdXAUBVCjVQGBWCT2l2tb1sUYcrOVw'   #토큰을 설정해 줍니다.
bot = telegram.Bot(token = my_token)                          #봇을 생성합니다.
chat_id = '@sdbinance'

formater = logging.Formatter('[%(asctime)s] %(levelname)s:%(message)s')
logger = logging.getLogger("logger")
file_handler = logging.FileHandler("turtle.log")
file_handler.setFormatter(formater)
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)

with open("binance.txt") as f:
    lines = f.readlines()
    api_key = lines[0].strip()
    secret  = lines[1].strip()
    f.close()

binance = ccxt.binance(config={
    'apiKey': api_key, 
    'secret': secret,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'
    }
})

tickers = ["BTC", "ETH"]
# tickers = ["BTC"]

def cal_atr(symbol):

    btc = binance.fetch_ohlcv(
        symbol=symbol,
        timeframe='12h', 
        since=None, 
        limit=56
    )

    df = pd.DataFrame(data=btc, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
    df.set_index('datetime', inplace=True)

    df.tail()
    df['pclose'] = df['close'].shift(1)
    df['diff1'] = abs(df['high'] - df['low'])
    df['diff2'] = abs(df['pclose'] - df['high'])
    df['diff3'] = abs(df['pclose'] - df['low'])
    df['TR'] = df[['diff1', 'diff2', 'diff3']].max(axis=1)

    data = np.array(df['TR'])    # no previous day's N 
    for i in range(1, len(df)):
        data[i] = (19 * data[i-1] + df['TR'].iloc[i]) / 20 

    df['N'] = data
    
    atr[symbol] = round(df['N'][-1], 2)
    high10[symbol] = round(df['high'][-11:-1].max(), 3)
    high20[symbol] = round(df['high'][-21:-1].max(), 3)
    high55[symbol] = round(df['high'][-56:-1].max(), 3)
    low10[symbol] = round(df['low'][-11:-1].min(), 3)
    low20[symbol] = round(df['low'][-21:-1].min(), 3)
    low55[symbol] = round(df['low'][-56:-1].min(), 3)

    time.sleep(0.1)

def cal_unit(symbol, usdt):
    unit[symbol] = round(((((usdt * 0.02) / len(tickers))/2)/atr[symbol]) * 3, 3) # 레버리지 3배, /2 는 절반은 55일 돌파시 매수유닛

def position_marking():
    balance = binance.fetch_balance()
    positions = balance['info']['positions']

    for positionA in positions:
        for ticker in tickers:
            tickerE = ticker + "USDT"
            tickerF = ticker + "/USDT"
            if positionA["symbol"] == tickerE:
                if float(positionA['positionAmt']) > 0:
                    position[tickerF]['type'] = 'long'
                    position[tickerF]['amount'] = float(positionA['positionAmt'])
                elif float(positionA['positionAmt']) < 0:
                    position[tickerF]['type'] = 'short'
                    position[tickerF]['amount'] = float(positionA['positionAmt'])
                elif float(positionA['positionAmt']) == 0:
                    position[tickerF]['type'] = None
                    position[tickerF]['amount'] = float(positionA['positionAmt'])

def enter_position1():
    try:
        global coin_num
        for symbol in tickers:
            symbol = symbol + "/USDT"
            if cur_price[symbol] > high20[symbol] and cur_price[symbol] < high55[symbol] and position[symbol]['type'] is None:         # 현재가 > 15ma
                position[symbol]['type'] = 'long'
                position[symbol]['amount'] = float(unit[symbol])
                buy_price[symbol] = cur_price[symbol]
                buy_num[symbol] = 1
                binance.create_market_buy_order(symbol=symbol, amount=float(unit[symbol]))
                text = '{} 선물 시스템1(롱) 진입\n가격: {:>0.1f} 달러, 수량: {:>0.3f}'.format(symbol, cur_price[symbol], unit[symbol])
                logger.info(text)
                bot.sendMessage(chat_id=chat_id, text=text)
                coin_num = coin_num - 1
                time.sleep(0.1)
            elif cur_price[symbol] < low20[symbol] and cur_price[symbol] > low55[symbol] and position[symbol]['type'] is None:      # 현재가 < 50ma
                position[symbol]['type'] = 'short'
                position[symbol]['amount'] = float(unit[symbol])
                buy_price[symbol] = cur_price[symbol]
                buy_num[symbol] = 1
                binance.create_market_sell_order(symbol=symbol, amount=float(unit[symbol]))
                text = '{} 선물 시스템1(숏) 진입\n가격: {:>0.1f} 달러, 수량: {:>0.3f}'.format(symbol, cur_price[symbol], unit[symbol])
                logger.info(text)
                bot.sendMessage(chat_id=chat_id, text=text)
                coin_num = coin_num - 1
                time.sleep(0.1)
    except Exception as e:
        logger.warning(e)
        # bot.sendMessage(chat_id=chat_id, text='error enter_position')
        time.sleep(1)

def enter_position2(usdt_now):
    try:    
        for symbol in tickers:
            symbol = symbol + "/USDT"
            amount_now = float(unit[symbol]) * cur_price[symbol] / 3
            if usdt_now > amount_now and position[symbol]['type'] == 'long' and cur_price[symbol] > (buy_price[symbol] + (atr[symbol]/2)) and buy_num[symbol] < 5:         # 현재가 > 15ma
                position[symbol]['amount'] = float(position[symbol]['amount']) + float(unit[symbol])
                buy_price[symbol] = cur_price[symbol]
                buy_num[symbol] = buy_num[symbol] + 1
                binance.create_market_buy_order(symbol=symbol, amount=float(unit[symbol]))
                text = '{} 선물 시스템1(롱) 진입\n가격: {:>0.1f} 달러, 수량: {:>0.3f}'.format(symbol, cur_price[symbol], unit[symbol])
                logger.info(text)
                bot.sendMessage(chat_id=chat_id, text=text)
                time.sleep(0.1)
            elif usdt_now > amount_now and position[symbol]['type'] == 'short' and cur_price[symbol] < (buy_price[symbol] - (atr[symbol]/2)) and buy_num[symbol] < 5:         # 현재가 > 15ma
                position[symbol]['amount'] = float(position[symbol]['amount']) + float(unit[symbol])
                buy_price[symbol] = cur_price[symbol]
                buy_num[symbol] = buy_num[symbol] + 1
                binance.create_market_sell_order(symbol=symbol, amount=float(unit[symbol]))
                text = '{} 선물 시스템1(숏) 진입\n가격: {:>0.1f} 달러, 수량: {:>0.3f}'.format(symbol, cur_price[symbol], unit[symbol])
                logger.info(text)
                bot.sendMessage(chat_id=chat_id, text=text)
                time.sleep(0.1)
    except Exception as e:
        logger.warning(e)
        # bot.sendMessage(chat_id=chat_id, text='error enter_position')
        time.sleep(1)

def enter_position3(usdt_now):
    try:    
        for symbol in tickers:
            symbol = symbol + "/USDT"
            amount_now = float(unit[symbol]) * cur_price[symbol] / 3
            if cur_price[symbol] > high55[symbol] and (position[symbol]['type'] == 'long' or position[symbol]['type'] is None):         # 현재가 > 15ma
                position[symbol]['type'] = 'long2'
                buy_price[symbol] = cur_price[symbol]
                buy_num55[symbol] = 1
                if usdt_now > amount_now:
                    position[symbol]['amount'] = float(position[symbol]['amount']) + float(unit[symbol])
                    binance.create_market_buy_order(symbol=symbol, amount=float(unit[symbol]))
                    text = '{} 선물 시스템2(롱) 진입\n가격: {:>0.1f} 달러, 수량: {:>0.3f}'.format(symbol, cur_price[symbol], unit[symbol])
                    logger.info(text)
                    bot.sendMessage(chat_id=chat_id, text=text)
                time.sleep(0.1)
            elif cur_price[symbol] < low55[symbol] and (position[symbol]['type'] == 'short' or position[symbol]['type'] is None):      # 현재가 < 50ma
                position[symbol]['type'] = 'short2'
                buy_price[symbol] = cur_price[symbol]
                buy_num55[symbol] = 1
                if usdt_now > amount_now:
                    position[symbol]['amount'] = float(position[symbol]['amount']) + float(unit[symbol])
                    binance.create_market_sell_order(symbol=symbol, amount=float(unit[symbol]))
                    text = '{} 선물 시스템2(숏) 진입\n가격: {:>0.1f} 달러, 수량: {:>0.3f}'.format(symbol, cur_price[symbol], unit[symbol])
                    logger.info(text)
                    bot.sendMessage(chat_id=chat_id, text=text)
                time.sleep(0.1)
    except Exception as e:
        logger.warning(e)
        # bot.sendMessage(chat_id=chat_id, text='error enter_position')
        time.sleep(1)

def enter_position4(usdt_now):
    try:    
        for symbol in tickers:
            symbol = symbol + "/USDT"
            amount_now = float(unit[symbol]) * cur_price[symbol] / 3
            if position[symbol]['type'] == 'long2' and cur_price[symbol] > (buy_price[symbol] + (atr[symbol]/2)) and buy_num55[symbol] < 5:         # 현재가 > 15ma
                buy_price[symbol] = cur_price[symbol]
                buy_num55[symbol] = buy_num[symbol] + 1
                if usdt_now > amount_now:
                    position[symbol]['amount'] = float(position[symbol]['amount']) + float(unit[symbol])
                    binance.create_market_buy_order(symbol=symbol, amount=float(unit[symbol]))
                    text = '{} 선물 시스템2(롱) 진입\n가격: {:>0.1f} 달러, 수량: {:>0.3f}'.format(symbol, cur_price[symbol], unit[symbol])
                    logger.info(text)
                    bot.sendMessage(chat_id=chat_id, text=text)
                time.sleep(0.1)
            elif position[symbol]['type'] == 'short2' and cur_price[symbol] < (buy_price[symbol] - (atr[symbol]/2)) and buy_num55[symbol] < 5:         # 현재가 > 15ma
                buy_price[symbol] = cur_price[symbol]
                buy_num55[symbol] = buy_num[symbol] + 1
                if usdt_now > amount_now:
                    position[symbol]['amount'] = float(position[symbol]['amount']) + float(unit[symbol])
                    binance.create_market_sell_order(symbol=symbol, amount=float(unit[symbol]))
                    text = '{} 선물 시스템2(숏) 진입\n가격: {:>0.1f} 달러, 수량: {:>0.3f}'.format(symbol, cur_price[symbol], unit[symbol])
                    logger.info(text)
                    bot.sendMessage(chat_id=chat_id, text=text)
                time.sleep(0.1)
    except Exception as e:
        logger.warning(e)
        # bot.sendMessage(chat_id=chat_id, text='error enter_position')
        time.sleep(1)

def exit_position():
    try:
        global coin_num
        for symbol in tickers:
            symbol = symbol + "/USDT"
            amount_p = abs(float(position[symbol]['amount']))    # 포지션 보유량
            if position[symbol]['type'] == 'long' and \
                ((cur_price[symbol] < (buy_price[symbol] - (atr[symbol]*2))) or \
                cur_price[symbol] < low10[symbol]):

                binance.create_market_sell_order(symbol=symbol, amount=amount_p)
                position[symbol]['amount'] = 0
                position[symbol]['type'] = None
                text = '{} 선물 청산\n가격: {:>0.1f} 달러, 수량: {:>0.3f}'.format(symbol, cur_price[symbol], amount_p)
                logger.info(text)
                bot.sendMessage(chat_id=chat_id, text=text)

                coin_num = coin_num + 1
                cal_atr(symbol)
                balance = binance.fetch_balance(params={"type": "future"})
                usdt = balance['USDT']['total']
                cal_unit(symbol, usdt)
                
                time.sleep(0.1)

            elif position[symbol]['type'] == 'long2' and \
                ((cur_price[symbol] < (buy_price[symbol] - (atr[symbol]*2))) or \
                cur_price[symbol] < low20[symbol]):

                binance.create_market_sell_order(symbol=symbol, amount=amount_p)
                position[symbol]['amount'] = 0
                position[symbol]['type'] = None
                text = '{} 선물 청산\n가격: {:>0.1f} 달러, 수량: {:>0.3f}'.format(symbol, cur_price[symbol], amount_p)
                logger.info(text)
                bot.sendMessage(chat_id=chat_id, text=text)

                coin_num = coin_num + 1
                cal_atr(symbol)
                balance = binance.fetch_balance(params={"type": "future"})
                usdt = balance['USDT']['total']
                cal_unit(symbol, usdt)
                
                time.sleep(0.1)

            elif position[symbol]['type'] == 'short' and ((cur_price[symbol] > (buy_price[symbol] + (atr[symbol]*2))) or cur_price[symbol] > high10[symbol]):

                binance.create_market_buy_order(symbol=symbol, amount=amount_p)
                position[symbol]['amount'] = 0
                position[symbol]['type'] = None
                text = '{} 선물 청산\n가격: {:>0.1f} 달러, 수량: {:>0.3f}'.format(symbol, cur_price[symbol], amount_p)
                logger.info(text)
                bot.sendMessage(chat_id=chat_id, text=text)

                coin_num = coin_num + 1
                cal_atr(symbol)
                balance = binance.fetch_balance(params={"type": "future"})
                usdt = balance['USDT']['total']
                cal_unit(symbol, usdt)

                time.sleep(0.1)

            elif position[symbol]['type'] == 'short2' and \
                ((cur_price[symbol] > (buy_price[symbol] + (atr[symbol]*2))) or \
                cur_price[symbol] > high20[symbol]):

                binance.create_market_buy_order(symbol=symbol, amount=amount_p)
                position[symbol]['amount'] = 0
                position[symbol]['type'] = None
                text = '{} 선물 청산\n가격: {:>0.1f} 달러, 수량: {:>0.3f}'.format(symbol, cur_price[symbol], amount_p)
                logger.info(text)
                bot.sendMessage(chat_id=chat_id, text=text)

                coin_num = coin_num + 1
                cal_atr(symbol)
                balance = binance.fetch_balance(params={"type": "future"})
                usdt = balance['USDT']['total']
                cal_unit(symbol, usdt)

                time.sleep(0.1)

    except Exception as e:
        logger.warning(e)
        bot.sendMessage(chat_id=chat_id, text=e)
        time.sleep(1)

def money_status():                    # 잔고현황을 텔레그램 봇으로 전송
    with open("moneyB.txt") as f:
        lines = f.readlines()
        money = float(lines[0].strip())
        f.close()
    balance = binance.fetch_balance(params={"type": "future"})
    usdt_balance = balance['USDT']['total']

    profits = usdt_balance - money
    profits_rate = ((usdt_balance / money)-1) * 100
    text = '코인거래 진행상황\n\n평가액: {:>0.1f}달러,\n수익금: {:>0.1f}달러,\n수익율: {:>0.1f}%\n\n오늘도 화이팅'.format(usdt_balance, profits, profits_rate)
    bot.sendMessage(chat_id=chat_id, text=text)

def status():                    # 현상황 로그기록
    for symbol in tickers:
        symbol = symbol + "/USDT"
        cal_atr(symbol)
        cal_unit(symbol, usdt)

        text0 = symbol
        text1 = "atr : {:,}".format(atr[symbol])
        text2 = "unit : {:,}".format(unit[symbol])
        text3 = "high10 : {:,}".format(high10[symbol])
        text4 = "high20 : {:,}".format(high20[symbol])
        text5 = "high55 : {:,}".format(high55[symbol])
        text6 = "low10 : {:,}".format(low10[symbol])
        text7 = "low20 : {:,}".format(low20[symbol])
        text8 = "low55 : {:,}".format(low55[symbol])
        text9 = "position : " + str(position[symbol]['type']) + "\n"
        logger.info(text0)
        logger.info(text1)
        logger.info(text2)
        logger.info(text3)
        logger.info(text4)
        logger.info(text5)
        logger.info(text6)
        logger.info(text7)
        logger.info(text8)

        if position[symbol]['type'] == 'long':
            loss_price = round(buy_price[symbol]-(atr[symbol] * 2), 1)
            text9 = "position : " + str(position[symbol]['type'])
            text10 = "buy_price : {:,}".format(buy_price[symbol])
            text11 = "loss price1 : {:,}".format(loss_price)
            text12 = "loss price2 : {:,}".format(low10[symbol])
            logger.info(text9)
            logger.info(text10)
            logger.info(text11)
            logger.info(text12)
            if loss_price > low10[symbol]:
                text13 = "loss price : {:,}".format(loss_price) + "\n"
                logger.info(text13)
                text14 = "{} 손절가 : {:,}".format(symbol, loss_price)
                bot.sendMessage(chat_id=chat_id, text=text14)
            else:
                text13 = "loss price : {:,}".format(low10[symbol]) + "\n"
                logger.info(text13)
                text14 = "{} 손절가 : {:,}".format(symbol, low10[symbol])
                bot.sendMessage(chat_id=chat_id, text=text14)

        elif position[symbol]['type'] == 'long2':
            loss_price = round(buy_price[symbol]-(atr[symbol] * 2), 1)
            text9 = "position : " + str(position[symbol]['type'])
            text10 = "buy_price : {:,}".format(buy_price[symbol])
            text11 = "loss price1 : {:,}".format(loss_price)
            text12 = "loss price2 : {:,}".format(low20[symbol])
            logger.info(text9)
            logger.info(text10)
            logger.info(text11)
            logger.info(text12)
            if loss_price > low20[symbol]:
                text13 = "loss price : {:,}".format(loss_price) + "\n"
                logger.info(text13)
                text14 = "{} 손절가 : {:,}".format(symbol, loss_price)
                bot.sendMessage(chat_id=chat_id, text=text14)
            else:
                text13 = "loss price : {:,}".format(low20[symbol]) + "\n"
                logger.info(text13)
                text14 = "{} 손절가 : {:,}".format(symbol, low20[symbol])
                bot.sendMessage(chat_id=chat_id, text=text14)

        elif position[symbol]['type'] == 'short':
            loss_price = round(buy_price[symbol]+(atr[symbol] * 2), 1)
            text9 = "position : " + str(position[symbol]['type'])
            text10 = "buy_price : {:,}".format(buy_price[symbol])
            text11 = "loss price1 : {:,}".format(loss_price)
            text12 = "loss price2 : {:,}".format(high10[symbol])
            logger.info(text9)
            logger.info(text10)
            logger.info(text11)
            logger.info(text12)
            if loss_price < high10[symbol]:
                text13 = "loss price : {:,}".format(loss_price) + "\n"
                logger.info(text13)
                text14 = "{} 손절가 : {:,}".format(symbol, loss_price)
                bot.sendMessage(chat_id=chat_id, text=text14)
            else:
                text13 = "loss price : {:,}".format(high10[symbol]) + "\n"
                logger.info(text13)
                text14 = "{} 손절가 : {:,}".format(symbol, high10[symbol])
                bot.sendMessage(chat_id=chat_id, text=text14)

        elif position[symbol]['type'] == 'short2':
            loss_price = round(buy_price[symbol]+(atr[symbol] * 2), 1)
            text9 = "position : " + str(position[symbol]['type'])
            text10 = "buy_price : {:,}".format(buy_price[symbol])
            text11 = "loss price1 : {:,}".format(loss_price)
            text12 = "loss price2 : {:,}".format(high20[symbol])
            logger.info(text9)
            logger.info(text10)
            logger.info(text11)
            logger.info(text12)
            if loss_price < high20[symbol]:
                text13 = "loss price : {:,}".format(loss_price) + "\n"
                logger.info(text13)
                text14 = "{} 손절가 : {:,}".format(symbol, loss_price)
                bot.sendMessage(chat_id=chat_id, text=text14)
            else:
                text13 = "loss price : {:,}".format(high20[symbol]) + "\n"
                logger.info(text13)
                text14 = "{} 손절가 : {:,}".format(symbol, high20[symbol])
                bot.sendMessage(chat_id=chat_id, text=text14)

        else:
            logger.info(text9)

#-------------------------------------------------------------------------
# 알고리즘 시작
#-------------------------------------------------------------------------

atr, high10, high20, high55, low10, low20, low55, unit = {}, {}, {}, {}, {}, {}, {}, {}
cur_price, buy_price, buy_num, buy_num55 = {}, {}, {}, {}

position = {}
for symbol in tickers:
    symbol = symbol + "/USDT"
    position[symbol] = {
        "type": None,
        "amount": 0
    }
# position_marking()

cur_price = {}
for symbol in tickers:
    symbol = symbol + "/USDT"
    ticker = binance.fetch_ticker(symbol)
    cur_price[symbol] = ticker['last']

balance = binance.fetch_balance(params={"type": "future"})
usdt = balance['USDT']['total']

# 재실행용 필요데이터
#buy_price['BTC/USDT'] = 38223.8
#buy_num['BTC/USDT'] = 3
# buy_num55['BTC/USDT'] = 1
#position['BTC/USDT']['type'] = 'short'

#buy_price['ETH/USDT'] = 2627.1
#buy_num['ETH/USDT'] = 4
#position['ETH/USDT']['type'] = 'short'
# 재실행용 필요데이터

status()
# money_status()
coin_num = len(tickers)
coin_num = 0

op_mode = True

while True:
    try:
        now = datetime.datetime.now()

        # if (now.hour == 1 or now.hour == 9 or now.hour == 17) and now.minute == 1 and (0 <= now.second < 10):   # 바이낸스용
            # text = '바이낸스 포지션확인'
            # bot.sendMessage(chat_id=chat_id, text=text)
            # time.sleep(10)

        if (now.hour == 8 or now.hour == 20) and now.minute == 59 and (50 <= now.second < 59) and op_mode is True:
            op_mode = False

        if (now.hour == 9 or now.hour == 21) and now.minute == 0 and (10 <= now.second < 20) and op_mode is False:
            status()
            money_status()
            op_mode = True
            time.sleep(1)

        cur_price = {}
        for symbol in tickers:
            symbol = symbol + "/USDT"
            ticker = binance.fetch_ticker(symbol)
            cur_price[symbol] = ticker['last']

            # if (position[symbol]['type'] == 'long' or position[symbol]['type'] == 'long2') and (buy_price[symbol] < cur_price[symbol]):
                # buy_price[symbol] = cur_price[symbol]

            # if (position[symbol]['type'] == 'short' or position[symbol]['type'] == 'short2') and (buy_price[symbol] > cur_price[symbol]):
                # buy_price[symbol] = cur_price[symbol]

        balance_now = binance.fetch_balance(params={"type": "future"})
        usdt_now = balance_now['USDT']['free']
        enter_position1()
        enter_position2(usdt_now)
        enter_position3(usdt_now)
        enter_position4(usdt_now)
        exit_position()
        time.sleep(0.1)

    except Exception as e:
        logger.warning(e)
        #bot.sendMessage(chat_id='@fteamcoin', text="오류확인")
        time.sleep(1)