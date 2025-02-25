# Strategy Settings
LIMIT = 6
INTERVAL = '4hour'
profit_min = 1.2
profit_max = 100  # only required if you want to limit max profit
percent_below = 0.4  # change risk level:  0.7 = 70% below high_price, 0.5 = 50% below high_price
sleepunit = 15
all_info = True

# Display Setttings
"""
The Snail v 1.2
"Buy the dips! ... then wait"
A simple signal that waits for a coin to be X% below its X day high AND below a calculated price (buy_below), then buys it.
Change profit_min to your required potential profit amount
i.e. 20 = 20% potential profit (room for coin to increase by 20%)
profit_max can be used to limit the maximum profit to avoid pump and dumps

Recommended Snail Settings:
Limit = NUmber of days to look back.
Interval = timeframe (leave at 1d)
profit_min, profit_max  as described above

BVT or OLORIN Fork.
If using the Olorin fork (or a variation of it) you must set Olorin to True and BVT to False to change the signal format to work with Olorin.

Recommended config.yml settings
CHANGE_IN_PRICE: 100
STOP_LOSS: 100
TAKE_PROFIT: 2.5 #3.5 if after a large drop in the market
CUSTOM_LIST_AUTORELOAD: False
USE_TRAILING_STOP_LOSS: True
TRAILING_STOP_LOSS: 1 # 1.5 if you want bigger gains
TRAILING_TAKE_PROFIT: .1
Do NOT use pausebotmod as it will prevent the_snail from buying - The Snail buys the dips

Developed by scoobie
Big thank you to @vyacheslav for optimising the code with async and adding list sorting,
and Kevin.Butters for the meticulous testing and reporting

Good luck, but use The Snail LIVE at your own risk - TEST TEST TEST

v1.2 Update
New colour for "The Snail is checking..." to make it easier to spot if you're scrolling through the screen to see last results
Now does not show coins that you already hold
Added variable to change the 'Risk'
- It was previously hardcoded to buy at 70% below the high_price, this is now adjustable.
- e.g. percent_below  0.7 = 70% below high_price, 0.5 = 50% below high_price


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
from pprint import pprint as pp
# Load creds modules
from helpers.handle_creds import (
    load_correct_creds
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

# Load creds for correct environment
access_key, secret_key, passphrase_key = load_correct_creds(parsed_creds)
client = Client(access_key, secret_key, passphrase_key)

# If True, an updated list of coins will be generated from the site - http://edgesforledges.com/watchlists/binance.
# If False, then the list you create in TICKERS_LIST = 'tickers.txt' will be used.
CREATE_TICKER_LIST = False
def MyLog(msg):
    print(f'{TextColors.TURQUOISE}=================>  '+str(msg)+f'  <========================{TextColors.DEFAULT}')

# When creating a ticker list from the source site:
# http://edgesforledges.com you can use the parameter (all or innovation-zone).
# ticker_type = 'innovation-zone'
ticker_type = 'all'
if CREATE_TICKER_LIST:
    TICKERS_LIST = 'tickers_halal.txt'
else:
    TICKERS_LIST = 'tickers.txt'


BVT = False
OLORIN = True
if BVT:
    signal_file_type = '.exs'
else:
    signal_file_type = '.buy'

# not available yet
# extra_filter = False


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

async def create_urls_org(ticker_list, interval) -> dict:
    coins_urls = {}

    if INTERVAL == '1day':
        st = datetime.now() - timedelta(days=float(LIMIT))
    elif INTERVAL == '4hour':
        st = datetime.now() - timedelta(hours=float(LIMIT/4))    
    elif INTERVAL == '1hour':
        st = datetime.now() - timedelta(hours=float(LIMIT))  
    elif INTERVAL == '1min':
        st = datetime.now() - timedelta(minuts=float(LIMIT/1))  
    elif INTERVAL == '3min':
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
    if os.name == 'nt':
        # only need this line for Windows based systems
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in urls:
            link = urls[url]['url']
            tasks.append(get(session=session, url=link))
        response = await asyncio.gather(*tasks, return_exceptions=True)
        return response


def get_prices_high_low2(list_coins, interval):
    if os.name == 'nt':
        # only need this line for Windows based systems
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    prices_low_high = {}
    hist_data = asyncio.run(get_historical_data(ticker_list=list_coins, interval=interval))
    for item in hist_data:
        coin_symbol = item['symbol']
        h_p = []
        l_p = []
        for i in item['data']['data']:
            open_time = i[0]
            open_price = float(i[1])
            close_price = float(i[2])
            high_price = float(i[3])
            low_price = float(i[4])
            volume = float(i[5])
            quote_volume = i[6]
            h_p.append(high_price)
            l_p.append(low_price)
        prices_low_high[coin_symbol] = {'symbol': coin_symbol, 'high_price': h_p, 'low_price': l_p,
                                        'current_potential': 0.0}
    return prices_low_high

def get_prices_high_low(list_coins, interval):
    prices_low_high = {}
    hist_data = asyncio.run(get_historical_data(ticker_list=list_coins, interval=interval))
    #time.sleep(0.5)
    for item in hist_data:
        #time.sleep(0.5)
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
        #MyLog(prices_low_high)
    return prices_low_high

def do_work():
    while True:
        print("+++++++++++++++++++++++   Scoobie_thesnail V1 Working   +++++++++++++++")

        try:

            init_price = get_price(client)
            coins = get_prices_high_low(init_price, INTERVAL)
            MyLog("List coins when using get_prices_high_low")
            pp(coins)
            MyLog("Try fo while")
            print(f'{TextColors.TURQUOISE}The Snail is checking for potential profit and buy signals{TextColors.DEFAULT}')
            if os.path.exists(f'signals/snail_scan{signal_file_type}'):
                os.remove(f'signals/snail_scan{signal_file_type}')

            current_potential_list = []
            held_coins_list = {}


            if TEST_MODE:
                coin_path = 'test_coins_bought.json'
                MyLog("This is test mode fake money")
            else:
                if BVT:
                    coin_path = 'coins_bought.json'
                else:
                    coin_path = 'live_coins_bought.json'
                    MyLog("This is real money")

            if os.path.isfile(coin_path) and os.stat(coin_path).st_size != 0:
                with open(coin_path) as file:
                    held_coins_list = json.load(file)


            for coin in coins:
                if len(coins[coin]['high_price']) == LIMIT:
                    high_price = float(max(coins[coin]['high_price']))
                    low_price = float(min(coins[coin]['low_price']))
                    last_price = float(init_price[coin + PAIR_WITH]['price'])


                    # Calculation
                    diapason = high_price - low_price
                    potential = (low_price / high_price) * 100
                    buy_above = low_price * 1.00
                    buy_below = high_price - (diapason * percent_below)  # percent below affects Risk
                    max_potential = potential * 0.98
                    min_potential = potential * 0.6
                    safe_potential = potential - 12
                    current_range = high_price - last_price
                    current_potential = ((high_price / last_price) * 100) - 100
                    coins[coin]['current_potential'] = current_potential

                    if profit_min < current_potential < profit_max and last_price < buy_below and coin not in held_coins_list:
                        current_potential_list.append(coins[coin])

            if current_potential_list:
                sort_list = sorted(current_potential_list, key=lambda x: x[f'current_potential'], reverse=True)
                for i in sort_list:
                    coin = i['symbol']
                    current_potential = i['current_potential']
                    last_price = float(init_price[coin + PAIR_WITH]['price'])
                    high_price = float(max(coins[coin]['high_price']))
                    low_price = float(min(coins[coin]['low_price']))
                    diapason = high_price - low_price
                    potential = (low_price / high_price) * 100
                    buy_above = low_price * 1.00
                    buy_below = high_price - (diapason * percent_below)
                    current_range = high_price - last_price

                    print(f'{TextColors.TURQUOISE}{coin}{TextColors.DEFAULT} Potential profit: {TextColors.TURQUOISE}{current_potential:.0f}%{TextColors.DEFAULT}')

                    if all_info:
                        print(f'\nPrice:            ${last_price:.3f}\n'
                            f'High:             ${high_price:.3f}\n'
                            # f'Plan: TP {TP}% TTP {TTP}%\n'
                            f'Day Max Range:    ${diapason:.3f}\n'
                            f'Current Range:    ${current_range:.3f} \n'
                            # f'Daily Range:      ${diapason:.3f}\n'
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
            time.sleep(sleepunit)

        except Exception as e:
            print(f'xxxxxxxxxxxxxxx The Snail: Exception do_work() 1: {e}')
            time.sleep(sleepunit*4)
            continue
        except KeyboardInterrupt as ki:
            print(f'xxxxxxxxxxxxxxx The Snail: KeyboardInterrupt do_work() 1: {ki}')
            continue
        time.sleep(sleepunit)
        print("+++++++++++++++++++++++   END Snail V1   +++++++++++++++")

