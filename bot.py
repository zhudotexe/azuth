import os
import sys

import discord
import motor.motor_asyncio
from discord.ext.commands import Bot

TOKEN = os.environ.get("TOKEN")
MONGO_URI = os.environ.get("MONGO", "mongodb://localhost:27017")
COGS = (
    "cogs.customcommands",
    "cogs.joinannouncer",
    "cogs.moderation",
    "cogs.owner",
    "cogs.roles"
)


class Azuth(Bot):
    def __init__(self, *args, **kwargs):
        super(Azuth, self).__init__(*args, **kwargs)
        self.mclient = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        self.mdb = self.mclient.azuth
        self.testing = 'test' in sys.argv


bot = Azuth(".")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}: {bot.user.id}")
    await bot.change_presence(game=discord.Game(name='on Discord & Dragons'))


@bot.event
async def on_message(message):
    await bot.process_commands(message)


for cog in COGS:
    bot.load_extension(cog)

if __name__ == '__main__':
    bot.run(TOKEN)
