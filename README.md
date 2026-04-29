# BigDataAssingment2

Simple Python project for tracking the BTC price from Binance and sending Discord alerts. The bot can start and stop the watcher, change alert settings, and post a message when BTC moves by a chosen percentage or crosses a price level.

## Project Structure

```text
btc_watcher/
  alert_engine.py
  binance_stream.py
  bot.py
  config.py
  main.py
  models.py
  service.py
  settings_store.py
requirements.txt
README.md
```

## Commands

The default command prefix is `!`, so the commands look like this:

- `!watch start`
- `!watch stop`
- `!watch status`
- `!watch price`
- `!watch percent 1.5`
- `!watch percent off`
- `!watch above 70000`
- `!watch above off`
- `!watch below 65000`
- `!watch below off`
- `!watch cooldown 120`
- `!watch channel`
- `!watch channel #alerts`

When you run `!watch start`, the bot uses the current channel for notifications if no channel has been set before.

## Settings

Use `.env.example` as a template and set the variables in your shell or Docker command.

- `DISCORD_TOKEN`: Discord bot token. Required to run the bot.
- `DISCORD_COMMAND_PREFIX`: Prefix used for commands. Default: `!`
- `BINANCE_STREAM_URL`: Binance WebSocket URL. Default: `wss://stream.binance.com:9443/ws/btcusdt@ticker`
- `DEFAULT_PERCENT_THRESHOLD`: Default percentage change threshold. Default: `1.0`
- `DEFAULT_UPPER_PRICE`: Optional default alert price for upward crossing
- `DEFAULT_LOWER_PRICE`: Optional default alert price for downward crossing
- `DEFAULT_COOLDOWN_SECONDS`: Minimum seconds between repeated notifications for the same alert type. Default: `60`
- `DISCORD_NOTIFICATION_CHANNEL_ID`: Optional channel id for alert delivery
- `AUTO_START_ON_READY`: Start the Binance listener when the bot connects. Default: `false`
- `SETTINGS_FILE`: Path used to persist runtime settings. Default: `data/settings.json`

## Discord Bot Setup

1. Open the Discord Developer Portal: https://discord.com/developers/applications
2. Create a new application and open the `Bot` page.
3. Create the bot user and copy the bot token.
4. In `Bot`, enable `Message Content Intent` because this project uses prefix commands like `!watch start`.
5. In `Installation`, enable `Guild Install`.
6. In `Guild Install` scopes, select `bot` and `applications.commands`.
7. Give the bot at least these permissions: `View Channels`, `Send Messages`, `Read Message History`.
8. Use the generated install link to add the bot to your Discord server.

