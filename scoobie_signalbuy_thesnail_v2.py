

# Strategy Settings
LIMIT = 6
INTERVAL = '1hour'
profit_min = 1
profit_max = 100  # only required if you want to limit max profit
percent_below = 0.7  # change risk level:  0.7 = 70% below high_price, 0.5 = 50% below high_price
MOVEMENT = False
sleepunit = 15
# Display Setttings
all_info = True
# if using Windows OS set to True, else set to False
WINDOWS = False
# send message to discord
DISCORD = False

def MyLog(msg):
    print(f'{TextColors.TURQUOISE}=================>  '+str(msg)+f'  <========================{TextColors.DEFAULT}')

"""
The Snail v 2
"Buy the dips! ... then wait"

STRATEGY
1. Selects coins that are X% (percent_below) below their X day (LIMIT) maximum
2. ** NEW ** Finds movement (MOVEMENT) range over X Days
  - if MOVEMENT* > TAKE_PROFIT coins pass to 3
3. Check coins are not already owned
4. Uses MACD to check if coins are currently on an uptrend
5. Adds coins that pass all above tests to Signal file for the Bot to buy (ordered by Potential Profit from High to Low)

* MOVEMENT
  Looks at the fluctuation in price over LIMIT days and compares to your TAKE_PROFIT settings.
  i.e. if your TAKE_PROFIT is 3%, but the movement is only 1%, then you wont hit TP and will be left holding the coin
  This can be turned off if you want.


STRATEGY SETTINGS
LIMIT = 4
INTERVAL = '1d'
profit_min = 15
profit_max = 100  # only required if you want to limit max profit
percent_below = 0.6  # change risk level:  0.7 = 70% below high_price, 0.5 = 50% below high_price
MOVEMENT = True #

OTHER SETTINGS
BVT or OLORIN Fork.
Set True / False for compatibility

WINDOWS (WINDOWS OS)
Set True / False for compatibility

DISCORD
send message to Discord - Set True / False


CONFIG.YML SETTINGS
CHANGE_IN_PRICE: 100 REQUIRED
Do NOT use pausebotmod as it will prevent the_snail from buying - The Snail buys the dips

Developed by scoobie
Thanks to
@vyacheslav for optimising the code with async and adding list sorting,
@Kevin.Butters for the meticulous testing and reporting,
@OlorinSledge for the coding advice and a great fork

DISCLAIMER
CHECK YOU HAVE ALL THE REQUIRED IMPORTS INSTALLED
Developed for OlorinSledge fork - no support for any others as I don't use them.
Troubleshooting and help - please use the #troubleshooting channel
Settings - the settings in this file are what I currently use, please don't DM me for the 'best' settings - for me, these are the best so far.
There's a lot of options to adjust the strategy, test them out and share your results in #bot-strategies so others can learn from them too

Hope the Snail makes you rich!

"""

import os
import re
import aiohttp
import asyncio
import time
import json
from datetime import datetime, timedelta
from kucoin.client import Client
from helpers.parameters import parse_args, load_config
import pandas as pd
import pandas_ta as ta
import ccxt
from tradingview_ta import TA_Handler, Interval, Exchange
import requests

# Load creds modules
from helpers.handle_creds import (
    load_correct_creds, load_discord_creds
)

# Settings
args = parse_args()
DEFAULT_CONFIG_FILE = 'config.yml'
DEFAULT_CREDS_FILE = 'creds.yml'


config_file = args.config if args.config else DEFAULT_CONFIG_FILE
creds_file = args.creds if args.creds else DEFAULT_CREDS_FILE
parsed_creds = load_config(creds_file)
parsed_config = load_config(config_file)

# Load trading vars
PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
EX_PAIRS = parsed_config['trading_options']['FIATS']
TEST_MODE = parsed_config['script_options']['TEST_MODE']
TAKE_PROFIT = parsed_config['trading_options']['TAKE_PROFIT']
DISCORD_WEBHOOK = load_discord_creds(parsed_creds)
EXCHANGE_PLATFORM = parsed_config['script_options']['EXCHANGE']

# Load creds for correct environment
access_key, secret_key, passphrase_key = load_correct_creds(parsed_creds)
client = Client(access_key, secret_key, passphrase_key)



# If True, an updated list of coins will be generated from the site - http://edgesforledges.com/watchlists/binance.
# If False, then the list you create in TICKERS_LIST = 'tickers.txt' will be used.
CREATE_TICKER_LIST = True

# When creating a ticker list from the source site:
# http://edgesforledges.com you can use the parameter (all or innovation-zone).
# ticker_type = 'innovation-zone'
ticker_type = 'all'
if CREATE_TICKER_LIST:
    #LLLLL# TICKERS_LIST = 'tickers_all_USDT.txt'
    TICKERS_LIST = 'tickers_halal.txt'
else:
    TICKERS_LIST = 'tickers.txt'

# System Settings
BVT = False
OLORIN = True  # if not using Olorin Sledge Fork set to False
if OLORIN:
    signal_file_type = '.buy'
else:
    signal_file_type = '.exs'



class TextColors:
    BUY = '\033[92m'
    WARNING = '\033[93m'
    SELL_LOSS = '\033[91m'
    SELL_PROFIT = '\033[32m'
    DIM = '\033[2m\033[35m'
    DEFAULT = '\033[39m'
    YELLOW = '\033[33m'
    TURQUOISE = '\033[36m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    ITALICS = '\033[3m'


def msg_discord(msg):
    message = msg + '\n\n'
    mUrl = "https://discordapp.com/api/webhooks/"+DISCORD_WEBHOOK
    data = {"content": message}
    response = requests.post(mUrl, json=data)


def get_price(client_api):
    initial_price = {}
    tickers = [line.strip() for line in open(TICKERS_LIST)]
    prices = client_api.get_ticker()
    for coin in prices['ticker']:
        for item in tickers:
            if item + PAIR_WITH == coin['symbol'] and all(item + PAIR_WITH not in coin['symbol'] for item in EX_PAIRS):
                initial_price[coin['symbol']] = {'symbol': coin['symbol'],
                                                 'price': coin['last'],
                                                 'time': datetime.now(),
                                                 'price_list': [],
                                                 'change_price': 0.0,
                                                 'cov': 0.0}
    return initial_price



async def create_urls(ticker_list, interval) -> dict:
    coins_urls = {}

    if (INTERVAL == '1day') or (INTERVAL == '1d'):
        st = datetime.now() - timedelta(days=float(LIMIT))
    elif INTERVAL == '4hour':
        st = datetime.now() - timedelta(hours=float(LIMIT*4))    
    elif INTERVAL == '1hour':
        st = datetime.now() - timedelta(hours=float(LIMIT))  
    elif INTERVAL == '1min':
        st = datetime.now() - timedelta(minutes=float(LIMIT*1))  
    elif INTERVAL == '5min':
        st = datetime.now() - timedelta(minutes=float(LIMIT*5))  
    elif INTERVAL == '15min':
        st = datetime.now() - timedelta(minutes=float(LIMIT*15))  
        
    et = datetime.now()
    
    start_time = int(st.timestamp())
    stop_time = int(et.timestamp())

    for coin in ticker_list:
        if type(coin) == dict:
            if all(item + PAIR_WITH not in coin['symbol'] for item in EX_PAIRS):
                coins_urls[coin['symbol']] = {'symbol': coin['symbol'],
                                              'url': f"https://api.kucoin.com/api/v1/market/candles?symbol"
                                                     f"{coin['symbol']}&type={interval}&startAt={start_time}&endAt={stop_time}"}
        else:
            coins_urls[coin] = {'symbol': coin,
                                'url': f"https://api.kucoin.com/api/v1/market/candles?symbol={coin}&type={interval}&startAt={start_time}&endAt={stop_time}"}
    return coins_urls

async def create_urls2(ticker_list, interval) -> dict:
    coins_urls = {}
    if INTERVAL == '1day':
        st = datetime.now() - timedelta(days=float(LIMIT))
    elif INTERVAL == '4hour':
        st = datetime.now() - timedelta(hours=float(LIMIT/4))    
    elif INTERVAL == '1hour':
        st = datetime.now() - timedelta(hours=float(LIMIT))  
    elif INTERVAL == '1min':
        st = datetime.now() - timedelta(minuts=float(LIMIT/1))  
    elif INTERVAL == '5min':
        st = datetime.now() - timedelta(minuts=float(LIMIT/5))  
    elif INTERVAL == '15min':
        st = datetime.now() - timedelta(minuts=float(LIMIT/15))  
    et = datetime.now()
    start_time = int(st.timestamp())
    stop_time = int(et.timestamp())
    for coin in ticker_list:
        if type(coin) == dict:
            if all(item + PAIR_WITH not in coin['symbol'] for item in EX_PAIRS):
                coins_urls[coin['symbol']] = {'symbol': coin['symbol'],
                                              'url': f"https://api.kucoin.com/api/v1/market/candles?symbol"
                                                     f"{coin['symbol']}&type={interval}&startAt={start_time}&endAt={stop_time}"}
        else:
            coins_urls[coin] = {'symbol': coin,
                                'url': f"https://api.kucoin.com/api/v1/market/candles?symbol={coin}&type={interval}&startAt={start_time}&endAt={stop_time}"}
    return coins_urls


async def get(session: aiohttp.ClientSession, url) -> dict:
    data = {}
    symbol = re.findall(r'=\w+', url)[0][1:]
    try:
        resp = await session.request('GET', url=url)
        data['symbol'] = symbol
        # data['last_price'] = await get_last_price(session=session, symbol=symbol)
        data['data'] = await resp.json()
    except Exception as e:
        print(e)
    return data


async def get_historical_data(ticker_list, interval):
    urls = await create_urls(ticker_list=ticker_list, interval=interval)
    if WINDOWS:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in urls:
            link = urls[url]['url']
            tasks.append(get(session=session, url=link))
        response = await asyncio.gather(*tasks, return_exceptions=True)
        return response


def get_prices_high_low(list_coins, interval):
    if WINDOWS:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    prices_low_high = {}
    hist_data = asyncio.run(get_historical_data(ticker_list=list_coins, interval=interval))
    time.sleep(1)
    for item in hist_data:
        coin_symbol = item['symbol']
        h_p = []
        l_p = []
        try:
            for i in item['data']['data']:
                close_time = i[0]
                open_price = float(i[1])
                close_price = float(i[2])
                high_price = float(i[3])
                low_price = float(i[4])
                volume = float(i[5])
                quote_volume = i[6]
                h_p.append(high_price)
                l_p.append(low_price)
        except Exception as e:
                print(f'Exception {e}')
                print("=======> Remove this Simbol: "+ str(coin_symbol)+"  <==========")
                continue
        prices_low_high[coin_symbol] = {'symbol': coin_symbol, 'high_price': h_p, 'low_price': l_p, 'current_potential': 0.0}
    return prices_low_high


def do_work():    	
    while True:
        print("+++++++++++++++++++++++   Scoobie_thesnail V2 Working   +++++++++++++++")
        try:
            init_price = get_price(client)
            coins = get_prices_high_low(init_price, INTERVAL)
            print(f'{TextColors.TURQUOISE}The Snail is checking for potential profit and buy signals{TextColors.DEFAULT}')
            if os.path.exists(f'signals/snail_scan{signal_file_type}'):
                os.remove(f'signals/snail_scan{signal_file_type}')

            current_potential_list = []
            held_coins_list = {}

            if TEST_MODE:
                coin_path = 'test_coins_bought.json'
            elif BVT:
                coin_path = 'coins_bought.json'
            else:
                MyLog("No BVT")
                coin_path = 'live_coins_bought.json'
            if os.path.isfile(coin_path) and os.stat(coin_path).st_size != 0:
                with open(coin_path) as file:
                    held_coins_list = json.load(file)

            for coin in coins:
                if len(coins[coin]['high_price']) == LIMIT:
                    high_price = float(max(coins[coin]['high_price']))
                    low_price = float(min(coins[coin]['low_price']))
                    last_price = float(init_price[coin + PAIR_WITH]['price'])

                    # Calculation
                    range = high_price - low_price
                    potential = (low_price / high_price) * 100
                    buy_above = low_price * 1.00
                    buy_below = high_price - (range * percent_below)  # percent below affects Risk
                    max_potential = potential * 0.98
                    min_potential = potential * 0.6
                    safe_potential = potential - 12
                    current_range = high_price - last_price
                    current_potential = ((high_price / last_price) * 100) - 100
                    coins[coin]['current_potential'] = current_potential
                    movement = (low_price / range)
    #				print(f'{coin} {potential:.2f}% {movement:.2f}%')

                    if MOVEMENT:
                        MyLog("Test Mouvment")
                        if profit_min < current_potential < profit_max and last_price < buy_below and movement >= TAKE_PROFIT and coin not in held_coins_list:
                            current_potential_list.append(coins[coin])
                    else:
                        if profit_min < current_potential < profit_max and last_price < buy_below and coin not in held_coins_list:
                            current_potential_list.append(coins[coin])

            if current_potential_list:
                print(current_potential_list)
                # exchange = ccxt.binance()
                exchange = ccxt.kucoin({
                    'enableRateLimit': True,
                    'apiKey': access_key,
                    'secret': secret_key,
                    'password': passphrase_key
                })
                macd_list = []

                for i in current_potential_list:
                    coin = i['symbol'] + PAIR_WITH
                    if (coin.find("-")<=-1) and (EXCHANGE_PLATFORM=="kucoin"):
                        print("Coin Symbol correction from: "+str(coin))
                        coin = i['symbol'] + "-" + PAIR_WITH
                        print("To: "+str(coin))
                    current_potential = i['current_potential']
                    macd1 = exchange.fetch_ohlcv(coin, timeframe='1m', limit=36)
                    time.sleep(0.1)
                    macd5 = exchange.fetch_ohlcv(coin, timeframe='5m', limit=36)
                    time.sleep(0.1)
                    macd15 = exchange.fetch_ohlcv(coin, timeframe='15m', limit=36)
                    time.sleep(0.1)
                    try:
                        macd1day = exchange.fetch_ohlcv(coin, timeframe='1d', limit=15)
                    except Exception as e:
                        print(f'{coin} Exception {e}')
                        continue
                    if (EXCHANGE_PLATFORM=="kucoin"):
                        macdbtc = exchange.fetch_ohlcv('BTC-USDT', timeframe='1m', limit=36)
                    else:
                        macdbtc = exchange.fetch_ohlcv('BTCUSDT', timeframe='1m', limit=36)

                    df1 = pd.DataFrame(macd1, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                    df5 = pd.DataFrame(macd5, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                    df15 = pd.DataFrame(macd15, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                    df1day = pd.DataFrame(macd1day, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                    dfbtc = pd.DataFrame(macdbtc, columns=['time', 'open', 'high', 'low', 'close', 'volume'])

                    # Wait for 1 sec to prevent kucoin query limit
                    time.sleep(5)

                    try:
                        macd1 = df1.ta.macd(fast=12, slow=26)
                        macd5 = df5.ta.macd(fast=12, slow=26)
                        macd15 = df15.ta.macd(fast=12, slow=26)
                        macd1day = df1day.ta.macd(fast=12, slow=26)
                        macdbtc = dfbtc.ta.macd(fast=12, slow=26)

                        get_hist1 = macd1.iloc[35, 1]
                        get_hist5 = macd5.iloc[35, 1]
                        get_hist15 = macd15.iloc[35, 1]				
                        get_hist1day = macd1day.iloc[35, 1]
                        get_histbtc = macdbtc.iloc[35, 1]
                    
                    except Exception as e:
                        print(f'{coin} Exception {e}')
                        continue

                    if all_info:
                        if get_hist1 >= 0 and get_hist5 >= 0 and get_hist15 >= 0 and get_hist1day >= 0 and get_histbtc >= 0:
                            print(f'MACD HIST {coin} {current_potential:2f}% {TextColors.SELL_PROFIT}{get_hist1} {get_hist5} {get_hist15} {get_hist1day} {get_histbtc}{TextColors.DEFAULT}')
                        else:
                            print(f'MACD HIST {coin} {current_potential:2f}% {get_hist1} {get_hist5} {get_hist15} {get_hist1day} {get_histbtc}')

                    if get_hist1 >= 0 and get_hist5 >= 0 and get_hist15 >= 0 and get_hist1day >= 0 and get_histbtc >= 0:
                        # Add to coins for Snail to scan
                        print(f'{TextColors.TURQUOISE}{coin}{TextColors.DEFAULT} Potential profit: {TextColors.TURQUOISE}{current_potential:.0f}%{TextColors.DEFAULT}\n')
                        macd_list.append(coins[coin])
                    # else:
                    #     print(f'Do NOT buy {coin}')

                if macd_list:
                    MyLog(macd_list)
                    # print(macd_list)
                    sort_list = sorted(macd_list, key=lambda x: x[f'current_potential'], reverse=True)
                    for i in sort_list:
                        coin = i['symbol']
                        current_potential = i['current_potential']
                        last_price = float(init_price[coin + PAIR_WITH]['price'])
                        # print(f'list {coin} {last_price}')
                        high_price = float(max(coins[coin]['high_price']))
                        # print(f'list {coin} {high_price}')
                        low_price = float(min(coins[coin]['low_price']))
                        # print(f'list {coin} {low_price}')
                        range = high_price - low_price
                        potential = (low_price / high_price) * 100
                        buy_above = low_price * 1.00
                        buy_below = high_price - (range * percent_below)
                        current_range = high_price - last_price

                        if all_info:
                            print(f'\nPrice:            ${last_price:.3f}\n'
                                f'High:             ${high_price:.3f}\n'
                                # f'Plan: TP {TP}% TTP {TTP}%\n'
                                f'Day Max Range:    ${range:.3f}\n'
                                f'Current Range:    ${current_range:.3f} \n'
                                # f'Daily Range:      ${range:.3f}\n'
                                # f'Current Range     ${current_range:.3f} \n'
                                # f'Potential profit before safety: {potential:.0f}%\n'
                                # f'Buy above:        ${buy_above:.3f}\n'
                                f'Buy Below:        ${buy_below:.3f}\n'
                                f'Potential profit: {TextColors.TURQUOISE}{current_potential:.0f}%{TextColors.DEFAULT}'
                                # f'Max Profit {max_potential:.2f}%\n'
                                # f'Min Profit {min_potential:.2f}%\n'
                                )
                        # print(f'Adding {TextColors.TURQUOISE}{coin}{TextColors.DEFAULT} to buy list')

                        # add to signal
                        with open(f'signals/snail_scan{signal_file_type}', 'a+') as f:
                            f.write(str(coin + PAIR_WITH) + '\n')

                # else:
                # print(f'{TextColors.TURQUOISE}{coin}{TextColors.DEFAULT} may not be profitable at this time')
                snail_coins = len(current_potential_list)
                macd_coins = len(macd_list)
                snail_discord = f'Snail found {snail_coins} coins and MACD approved {macd_coins}'
                if DISCORD:
                    msg_discord(snail_discord)
                print(f'{TextColors.TURQUOISE}Snail found {snail_coins} coins and MACD approved {macd_coins} coins. L: {LIMIT}days Min: {profit_min}% Risk: {percent_below * 100}% {TextColors.DEFAULT}')
        except Exception as e:
            print(f'xxxxxxxxxxxxxxx The Snail: Exception do_work() 1: {e}')
            time.sleep(sleepunit*4)
            continue
        except KeyboardInterrupt as ki:
            print(f'xxxxxxxxxxxxxxx The Snail: KeyboardInterrupt do_work() 1: {ki}')
            continue
        time.sleep(sleepunit)
        MyLog("DoWork Sleep"+str(sleepunit))
        print(" ---- End Snail V2 ----")
