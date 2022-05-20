import discord
from discord import Message
import os
import websockets
import asyncio

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
		finally:
			await self.unregister(ws)
		await asyncio.sleep(0.01)

	async def distribute(self, ws):
		async for message in ws:
			if token in message:
				message = message.replace(token, '')
				websockets.broadcast(self.clients, message)
				print(message)


@d_client.event
async def on_message(message: Message):
	if message.author.id == 708334730457645119 and message.channel.id == 708365137660215330:
		async for m in message.channel.history(limit=1):  # this is how you can get message content when using a self bot
			async with websockets.connect('ws://127.0.0.1:4000') as ws:
				await ws.send(token + m.content)  # a means of authenticating message source


@d_client.event
async def on_connect():
	server = Server()
	await websockets.serve(server.ws_handler, 'localhost', 4000)


if __name__ == '__main__':
	token = os.environ.get('TOKEN')
	d_client.run(token, bot=False)
