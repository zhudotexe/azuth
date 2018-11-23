import discord
from discord.ext import commands

from utils import checks, colors


class CustomCommands:
    def __init__(self, bot):
        self.bot = bot
        self._cache = {}

    @commands.group(pass_context=True)
    async def cc(self, ctx):
        """Commands to manage custom commands."""
        if ctx.invoked_subcommand is None:
            await self.bot.say("Incorrect usage. Use .help cc for help.")

    @cc.command(pass_context=True, name="add")
    @checks.mod_or_permissions(manage_messages=True)
    async def cc_add(self, ctx, command, *, response):
        """Adds a response to a command."""
        server_commands = await self.get_server_commands(ctx.message.server.id)
        existing = next((c for c in server_commands['commands'] if c['name'] == command.lower().strip()), None)
        if not existing:
            server_commands['commands'].append({
                "name": command.lower().strip(),
                "responses": [response]
            })
            out = f"Created command `{command.lower().strip()}` and added response `{response}`."
        else:
            existing['responses'].append(response)
            out = f"Added response `{response}` to command `{command.lower()}`."

        await self.set_server_commands(ctx.message.server.id, server_commands)
        await self.bot.say(out)

    @cc.command(pass_context=True, name="list")
    async def cc_list(self, ctx, page: int = 1):
        """Shows the list of custom commands."""
        if page < 1:
            return await self.bot.say("Page must be at least 1.")
        server_commands = await self.get_server_commands(ctx.message.server.id)
        commands_ = sorted(server_commands['commands'], key=lambda c: c['name'])
        start = (page - 1) * 10
        end = page * 10
        page_commands = commands_[start:end]

        embed = discord.Embed(colour=colors.BLURPLE)
        embed.title = f"Page {page} ({start+1}-{end})"
        for cmd in page_commands:
            responses = ' '.join(f"```\n{r}\n```" for r in cmd['responses'])
            embed.add_field(name=cmd['name'], value=responses)

        await self.bot.say(embed=embed)

    @cc.command(pass_context=True, name="remove")
    @checks.mod_or_permissions(manage_messages=True)
    async def cc_remove(self, ctx, cmd: str, *, response: str = None):
        """Removes a command or a certain response."""
        server_commands = await self.get_server_commands(ctx.message.server.id)

        command = next((c for c in server_commands['commands'] if c['name'] == cmd.lower()), None)
        if command is None:
            return await self.bot.say("No matching command found.")

        if response is not None:
            response = next((r for r in command['responses'] if response.lower() == r.lower()), None)
            if response is None:
                return await self.bot.say("No matching response found.")
            command['responses'].remove(response)
            await self.set_server_commands(ctx.message.server.id, server_commands)
            await self.bot.say(f"Removed response ```\n{response}\n```.")
        else:
            server_commands['commands'].remove(command)
            await self.set_server_commands(ctx.message.server.id, server_commands)
            await self.bot.say(f"Removed command {command['name']} and all responses.")

    async def get_server_commands(self, server_id):
        if server_id in self._cache:
            return self._cache[server_id]
        server_commands = await self.bot.mdb.custcommands.find_one({"server": server_id})
        if server_commands is None:
            server_commands = get_default_commands(server_id)
        return server_commands

    async def set_server_commands(self, server_id, cmds):
        await self.bot.mdb.custcommands.replace_one(
            {"server": server_id},
            {"$set": cmds}, upsert=True
        )
        self._cache[server_id] = cmds


def get_default_commands(server_id):
    return {
        "server": server_id,
        "commands": []
    }


def setup(bot):
    bot.add_cog(CustomCommands(bot))
