from discord.ext import commands
import discord


@commands.command()
async def help(message, *args):  # 'message' stands for 'context'
    if not args:
        # If no arguments were provided, show all command names
        bot_commands = message.bot.commands

        # Create an Embed object with color blue
        embed = discord.Embed(
            title="Help",
            description="List of commands",
            color=0x00ff00
        )

        # Add fields to the embed with command names and brief descriptions
        command_list = [command.name for command in bot_commands]

        embed.description = "\n".join(command_list)

        # Send the embed to the channel where the command was used
        await message.send(embed=embed)
    else:
        # If an argument was provided, try to find the help for the specific command
        command_name = args[0].lower()
        command = message.bot.get_command(command_name)

        if command:
            # Create an Embed object with color green
            embed = discord.Embed(
                title=f"Help Command:  !{command.name}",
                description=command.description or "No help information available.",
                color=0x00ff00
            )

            # Send the embed to the channel where the command was used
            await message.send(embed=embed)
        else:
            await message.send(f"Command '{command_name}' not found.")


def setup(bot):
    bot.remove_command('help')
    bot.add_command(help)
