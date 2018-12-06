import io
import textwrap
import traceback
from contextlib import redirect_stdout

import discord
from discord.ext import commands

from utils import checks


class Owner:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    @checks.is_owner()
    async def chansay(self, channel: str, *, message: str):
        """Like .say, but works across servers. Requires channel id."""
        channel = discord.Object(id=channel)
        try:
            await self.bot.send_message(channel, message)
        except Exception as e:
            await self.bot.say(f'Failed to send message: {e}')

    @commands.command(pass_context=True, hidden=True, name='eval')
    @checks.is_owner()
    async def _eval(self, ctx, *, body: str):
        """Evaluates some code"""

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.message.channel,
            'author': ctx.message.author,
            'server': ctx.message.server,
            'message': ctx.message
        }

        env.update(globals())

        body = cleanup_code(body)
        stdout = io.StringIO()

        to_compile = 'async def func():\n{}'.format(textwrap.indent(body, "  "))

        try:
            exec(to_compile, env)
        except Exception as e:
            return await self.bot.say('```py\n{}: {}\n```'.format(e.__class__.__name__, e))

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as _:
            value = stdout.getvalue()
            await self.bot.say('```py\n{}{}\n```'.format(value, traceback.format_exc()))
        else:
            value = stdout.getvalue()
            try:
                await self.bot.add_reaction(ctx.message, '\u2705')
            except:
                pass

            if ret is None:
                if value:
                    await self.bot.say('```py\n{}\n```'.format(value))
            else:
                self._last_result = ret
                await self.bot.say('```py\n{}{}\n```'.format(value, ret))


def cleanup_code(content):
    """Automatically removes code blocks from the code."""
    # remove ```py\n```
    if content.startswith('```') and content.endswith('```'):
        return '\n'.join(content.split('\n')[1:-1])

    # remove `foo`
    return content.strip('` \n')


def setup(bot):
    bot.add_cog(Owner(bot))
