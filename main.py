import discord
from discord import Message
from discord.ext import tasks
import os
import websockets
import asyncio
import snscrape.modules.twitter as snt
from datetime import datetime
import pytz
import requests
import xmltodict
import json

headers = {'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36 RuxitSynthetic/1.0 v3277245740052736821 t7774180644855091482 athe94ac249 altpriv cvcv=2 smf=0"}
utc = pytz.UTC

twitter_users = ['elonmusk', 'FirstSquawk', 'EPSGUID']
last_tweet = {}
for user in twitter_users:
	last_tweet[user] = datetime.utcnow().replace(tzinfo=utc)

filings_ids = []
r = requests.get('https://www.sec.gov/Archives/edgar/xbrlrss.all.xml', headers=headers)
d = xmltodict.parse(r.text)
items = d['rss']['channel']['item']
for filing in items:
	filings_ids.append(filing['guid'])

r1 = requests.get('https://www.sec.gov/files/company_tickers.json', headers=headers)
data: dict = r1.json()
ticker_cik = {}
for d in data.values():
	ticker_cik[str(d['cik_str'])] = d['ticker']


d_client = discord.Client()


class Server:
	clients = set()

	async def register(self, ws):
		self.clients.add(ws)
		# print(f'{ws.remote_address} has connected.')

	async def unregister(self, ws):
		self.clients.remove(ws)
		# print(f'{ws.remote_address} has disconnected.')

	async def client_gen(self):
		for client in self.clients:
			await asyncio.sleep(0.01)
			yield client

	async def ws_handler(self, ws, uri):
		await self.register(ws)
		try:
			await self.distribute(ws)
		except Exception as e:
			print('distribution error: ' + str(e))
		finally:
			await self.unregister(ws)
		await asyncio.sleep(0.01)

	async def distribute(self, ws):
		async for message in ws:
			if not message.startswith('{"token": ' + f'"{token}"'):  # means of authentication - bit hacky, but works
				return
			try:
				message = json.loads(message)
			except Exception as e:
				print('error: ' + str(e))
				return
			message.pop('token')
			message = json.dumps(message)
			websockets.broadcast(self.clients, message)
			print(message)


@d_client.event
async def on_message(message: Message):
	# the following line has Walter Bloomberg's Discord ID and the #market-updates channel ID he posts in
	# could be done via twitter scraping also
	if message.author.id == 708334730457645119 and message.channel.id == 708365137660215330:
		async for m in message.channel.history(limit=1):  # this is how you can get message content when using a self bot
			async with websockets.connect('ws://127.0.0.1:4000') as ws:
				broadcast = {
					"token": token,
					"message_type": 'news',
					"source": 'Walter Bloomberg',
					"content": m.content
				}
				await ws.send(str(broadcast))


@d_client.event
async def on_connect():
	check_for_tweets.start()
	check_for_filings.start()
	server = Server()
	await websockets.serve(server.ws_handler, 'localhost', 4000)


@tasks.loop(seconds=15)
async def check_for_tweets():
	tweet = None
	for t_user in twitter_users:
		for t in snt.TwitterSearchScraper(f'from:{t_user}').get_items():
			tweet = t
			break  # we only want the most recent tweet, which is the first yielded
		if tweet is None:  # this won't happen unless the account has no tweets
			return
		message_type = 'earnings' if t_user == 'EPSGUID' else 'news'
		if tweet.date > last_tweet[t_user]:
			last_tweet[t_user] = tweet.date
			async with websockets.connect('ws://127.0.0.1:4000') as ws:
				broadcast = {
					"token": token,
					"message_type": message_type,
					"source": f'@{t_user}',
					"content": tweet.content
				}
				await ws.send(json.dumps(broadcast))


@tasks.loop(seconds=15)
async def check_for_filings():
	req = requests.get('https://www.sec.gov/Archives/edgar/xbrlrss.all.xml', headers={'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36 RuxitSynthetic/1.0 v3277245740052736821 t7774180644855091482 athe94ac249 altpriv cvcv=2 smf=0"})
	current_data = xmltodict.parse(req.text)
	current_filings = current_data['rss']['channel']['item']
	for f in current_filings:
		if f['guid'] in filings_ids:
			continue
		try:
			ticker = ticker_cik[f['edgar:xbrlFiling']['edgar:cikNumber']]
		except KeyError:
			ticker = 'None'
		broadcast = {
			"token": token,
			"message_type": "filing",
			"type": f['description'],
			"ticker": ticker,
			"company": f['edgar:xbrlFiling']['edgar:companyName'],
			"link": f['edgar:xbrlFiling']['edgar:xbrlFiles']['edgar:xbrlFile'][0]['@edgar:url']
		}
		filings_ids.append(f['guid'])
		async with websockets.connect('ws://127.0.0.1:4000') as ws:
			await ws.send(json.dumps(broadcast))


if __name__ == '__main__':
	token = os.environ.get('TOKEN')
	d_client.run(token, bot=False)
