import discord
from discord.ext import commands

from utils import checks


class Owner:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, hidden=True)
    @checks.is_owner()
    async def chansay(self, ctx, channel: str, *, message: str):
        """Like .say, but works across servers. Requires channel id."""
        channel = discord.Object(id=channel)
        try:
            await self.bot.send_message(channel, message)
        except Exception as e:
            await self.bot.say(f'Failed to send message: {e}')


def setup(bot):
    bot.add_cog(Owner(bot))
