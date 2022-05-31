import os
import websockets
import asyncio
import snscrape.modules.twitter as snt
from datetime import datetime
import pytz
import requests
import xmltodict
import json

token = os.environ.get('TOKEN')
port = int(os.environ.get('PORT'))
host_ip = 'ws://news-websocket.herokuapp.com/'

headers = {'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36 RuxitSynthetic/1.0 v3277245740052736821 t7774180644855091482 athe94ac249 altpriv cvcv=2 smf=0"}
utc = pytz.UTC

twitter_users = ['Deltaone', 'elonmusk', 'FirstSquawk', 'EPSGUID']
last_tweet = {}
for user in twitter_users:
	last_tweet[user] = datetime.utcnow().replace(tzinfo=utc)

filings_ids = []
r = requests.get('https://www.sec.gov/Archives/edgar/xbrlrss.all.xml', headers=headers)
d = xmltodict.parse(r.text)
items = d['rss']['channel']['item']
for filing in items:
	filings_ids.append(filing['guid'])
print(f'{len(filings_ids)} filings found.')

r1 = requests.get('https://www.sec.gov/files/company_tickers.json', headers=headers)
data: dict = r1.json()
ticker_cik = {}
for d in data.values():
	if str(d['cik_str']) not in ticker_cik.keys():
		ticker_cik[str(d['cik_str'])] = d['ticker']
print(f'{len(ticker_cik)} ticker:CIK pairs found.')


class Server:
	clients = set()

	async def register(self, ws):
		self.clients.add(ws)

	async def unregister(self, ws):
		self.clients.remove(ws)

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
				print(message)
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


async def check_for_tweets():
	while True:
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
				async with websockets.connect(host_ip + str(port)) as ws:
					broadcast = {
						"token": token,
						"message_type": message_type,
						"source": f'@{t_user}',
						"content": tweet.content
					}
					await ws.send(json.dumps(broadcast))
		await asyncio.sleep(1)


async def check_for_filings():
	while True:
		req = requests.get('https://www.sec.gov/Archives/edgar/xbrlrss.all.xml', headers={'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36 RuxitSynthetic/1.0 v3277245740052736821 t7774180644855091482 athe94ac249 altpriv cvcv=2 smf=0"})
		current_data = xmltodict.parse(req.text)
		current_filings = current_data['rss']['channel']['item']
		for f in current_filings:
			if f['guid'] in filings_ids:
				continue
			try:
				cik = f['edgar:xbrlFiling']['edgar:cikNumber']
				while cik[0] == "0":
					cik = cik[1:]
				ticker = ticker_cik[cik]
			except KeyError:
				ticker = 'None'
			broadcast = {
				"token": token,
				"message_type": "filing",
				"type": f['description'],
				"ticker": ticker,
				"company": f['edgar:xbrlFiling']['edgar:companyName'],
				"url": f['edgar:xbrlFiling']['edgar:xbrlFiles']['edgar:xbrlFile'][0]['@edgar:url']
			}
			filings_ids.append(f['guid'])
			async with websockets.connect(host_ip + str(port)) as ws:
				await ws.send(json.dumps(broadcast))
		await asyncio.sleep(1)


async def main():
	server = Server()
	print('Starting websocket server...')
	async with websockets.serve(server.ws_handler, host="", port=port):
		print('Server started.')
		asyncio.create_task(check_for_tweets())
		asyncio.create_task(check_for_filings())
		print('Scraping tasks running.')
		await asyncio.Future()

if __name__ == '__main__':
	asyncio.run(main())
