import random

import discord
from discord.ext import commands

from utils import checks


class JoinAnnouncer:
    def __init__(self, bot):
        self.bot = bot

    async def on_member_join(self, member):
        await self.bot.wait_until_ready()
        server_settings = await self.bot.mdb.join.find_one({"server": member.server.id})
        if server_settings is None or not server_settings['enabled']:
            return
        destination = member.server.get_channel(server_settings['destination'])
        messages = server_settings['messages']
        if messages:
            message = random.choice(messages).replace('@', member.mention)
        else:
            message = "Welcome to the server " + member.mention + "!"

        if destination:
            await self.bot.send_message(destination, message)

    @commands.group(pass_context=True, no_pm=True)
    @checks.mod_or_permissions(manage_server=True)
    async def ja(self, ctx):
        """Commands to manage server join announcements."""
        if ctx.invoked_subcommand is None:
            await self.bot.say("Incorrect usage. Use .help ja for help.")

    @ja.command(pass_context=True)
    @checks.mod_or_permissions(manage_server=True)
    async def toggle(self, ctx):
        """Toggles join announcements in a server."""
        server_settings = await self.get_server_settings(ctx.message.server.id, ['enabled'])

        server_settings['enabled'] = not server_settings['enabled']

        await self.set_server_settings(ctx.message.server.id, server_settings)

        await self.bot.say("Server join announcements {}."
                           .format('enabled' if server_settings['enabled'] else 'disabled'))

    @ja.command(pass_context=True)
    @checks.mod_or_permissions(manage_server=True)
    async def channel(self, ctx, chan: discord.Channel):
        """Sets the channel that join announcements are displayed in."""
        server_settings = await self.get_server_settings(ctx.message.server.id, ['destination'])
        server_settings['destination'] = chan.id
        await self.set_server_settings(ctx.message.server.id, server_settings)
        await self.bot.say("Server join announcement channel set to {}.".format(chan))

    @ja.group(pass_context=True)
    @checks.mod_or_permissions(manage_server=True)
    async def messages(self, ctx):
        """Commands to edit a server's join messages. Any `@` will be replaced with the name of the joining member."""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.list)

    @messages.command(pass_context=True)
    @checks.mod_or_permissions(manage_server=True)
    async def list(self, ctx):
        """Lists all the join announcement messages."""
        server_settings = await self.get_server_settings(ctx.message.server.id)
        messages = server_settings['messages']
        if not messages:
            return await self.bot.say("This server does not have any custom join messages.")
        else:
            await self.bot.say('\n\n'.join(messages))  # TODO make this tidier

    @messages.command(pass_context=True)
    @checks.mod_or_permissions(manage_server=True)
    async def add(self, ctx, *, msg):
        """Adds a join announcement message. Any `@` will be replaced with the name of the new user."""
        server_settings = await self.get_server_settings(ctx.message.server.id)
        server_settings['messages'].append(msg)
        await self.set_server_settings(ctx.message.server.id, server_settings)
        await self.bot.say("Added new join message.")

    @messages.command(pass_context=True)
    @checks.mod_or_permissions(manage_server=True)
    async def remove(self, ctx, *, msg):
        """Removes a join announcement message."""
        server_settings = await self.get_server_settings(ctx.message.server.id)

        try:
            msg = next(m for m in server_settings['messages'] if msg in m)
        except StopIteration:
            return await self.bot.say("Join message not found.")
        server_settings['messages'].remove(msg)
        await self.set_server_settings(ctx.message.server.id, server_settings)

        await self.bot.say("Removed join message: `{}`".format(msg))

    async def get_server_settings(self, server_id, projection=None):
        server_settings = await self.bot.mdb.join.find_one({"server": server_id}, projection)
        if server_settings is None:
            server_settings = get_default_settings(server_id)
        return server_settings

    async def set_server_settings(self, server_id, settings):
        await self.bot.mdb.join.update_one(
            {"server": server_id},
            {"$set": settings}, upsert=True
        )


def get_default_settings(server):
    return {
        "server": server,
        "messages": [],
        "destination": None,
        "enabled": False
    }


def setup(bot):
    bot.add_cog(JoinAnnouncer(bot))
