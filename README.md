# Abby

## Discord Bot for the Breeze Club Discord Server

[![Discord](https://img.shields.io/discord/819650821808273408?color=7289da&logo=discord&logoColor=white)](https://discord.gg/yGsBGQAC49)
[![Python](https://img.shields.io/badge/python-3.9.1-blue.svg?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-391/)
[![discord.py](https://img.shields.io/badge/discord.py-1.7.3-blue.svg?logo=discord&logoColor=white)](

[Join the Discord Server](https://discord.gg/yGsBGQAC49)

---

## About

Abby is a Discord bot for the Breeze Club Discord Server. It is written in Python and uses the [discord.py](https://discordpy.readthedocs.io/en/stable/) library. It is hosted on [Linode](https://www.linode.com/). She is designed to be a fun and useful bot for the server, packed with features and the ability to be expanded upon.

She's still under development, so expect bugs and missing features. If you find any bugs, please report them in the Discord server. If you have any suggestions, please also post them in the Discord server. If you want to contribute, please contact me on Discord. (I'm `@z8phyr_`)

Many notable features include her bunny personality, her image-generation commands, and her experience system. But there's a lot more to her than that! Check out the commands section below for more information.

## Features

- Banking
- Calender
- Chatbot
- [Commands](#commands)
- Exp
- Fun
- Greetings
- handlers
- Twtich
- Twitter
- utils

---

## Commands

Admin commands are only available to users with the `Administrator` permission. Moderator commands are only available to users with the `Moderator` permission. All other commands are available to everyone. The default prefix is `!`. You can change the prefix in the `main.py` or create a command to do so.

### Admin Commands

#### `clear_conv <user>`

Clears the conversation of a user. This is useful if the chatbot is stuck in a loop or is otherwise misbehaving.

#### `persona <persona>`

Sets the chatbot's persona. This is useful if you want to change the chatbot's personality. There are currently 6 personas: `bunny` (default), `kitten`, `owl`, `squirrel`, `fox`, and `panda`.

#### `personality <#>`

Sets the personality strength of Abby. This is useful if you want to change Abby's creativity in her response. The strength can be any number between 0 and 1, with 0 being the weakest and 1 being the strongest. The default is 0.5.

#### `record` - Not Implemented Fully

This starts an audio recording in the voice channel of the user who issued the command. The recording will stop after 10 seconds or when the user leaves the voice channel. The recording will be saved to the `recordings` folder.

##### `update_log`

This command updates the bot's log file. This is useful for tracking logs without having to restart the bot. It automatically saves to "logs/".

### Image Commands

Image commands are built as default commands and as slash commands. This is to demonstrate both methods of creating commands. The default commands are prefixed with `!` and the slash commands are prefixed with `/`. The slash commands are only available in servers that have the bot added to them. The default commands are available in all servers.

#### `!imagine <text> <style_preset> (optional)` or `/imagine <text> <style_preset>(optional)`

This utilizes Stability AI's API to generate an image based upon the text provided. You can learn more about this command in the [Image Generation](#image-generation) section below. (To be added)

##### `meme`

This pulls a random meme from a specified channel (#breeze-memes) and posts it in the current channel. It also has a "popular" weighting that will pull memes from the #breeze-memes channel that have a higher amount of reactions. This is useful for pulling the best memes from the channel.

### More Commands (To be added)

---

## Chatbot

Abby's most notable feature is her chatbot. She uses the [OpenAI API](https://openai.com/) to generate responses to messages. She has a few different personas that you can set her to. You can also set her personality strength. The default persona is `bunny` and the default personality strength is 0.5. You start up a conversation with Abby by using a summon word such as `hey abby` or anything that is in the `summon.json` file, She will start interacting with the user and continue to do so until the user dismisses her or a minute passes. The conversation with the user is saved to a database (Mongo Database) and is encrypted. You can clear this database by using the `clear_conv` command. This is useful if the conversation logs are too long.


## Other Awesome Features (To be added)

This will be a evolving documentation as the bot is still under development. I will be adding more features as I go along. If you have any suggestions, please post them in the Discord server. If you want to contribute, please contact me on Discord. (I'm `@z8phyr_`)


## Credits

Thanks to brndndiaz for helping me with setting up a lot of the bot's features. You can check out his github [here](github.com/brndndiaz).

Thanks to the [Breeze Club](https://discord.gg/yGsBGQAC49) members for being awesome and for letting me make this bot for them.


## License

This project is not licensed. You are free to use it however you want. I would appreciate it if you gave me credit for it, but it's not required.
