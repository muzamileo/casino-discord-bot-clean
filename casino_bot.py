import discord
from discord.ext import commands
import aiosqlite
import asyncio
from datetime import datetime
import random
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Create table if not exist on startup
@bot.event
async def on_ready():
    async with aiosqlite.connect("casino.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER,
                last_daily TEXT
            )
        """)
        await db.commit()
    print(f'Logged in as {bot.user}!')

# Balance command
@bot.command()
async def balance(ctx):
    async with aiosqlite.connect("casino.db") as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
        row = await cursor.fetchone()
        if row is None:
            await db.execute("INSERT INTO users (user_id, balance, last_daily) VALUES (?, ?, ?)", (ctx.author.id, 1000, None))
            await db.commit()
            balance = 1000
        else:
            balance = row[0]
        await ctx.send(f"{ctx.author.mention} Your balance is {balance} coins!")

# Daily reward command
@bot.command()
async def daily(ctx):
    async with aiosqlite.connect("casino.db") as db:
        cursor = await db.execute("SELECT balance, last_daily FROM users WHERE user_id = ?", (ctx.author.id,))
        row = await cursor.fetchone()
        today = datetime.utcnow().date().isoformat()

        if row is None:
            await db.execute("INSERT INTO users (user_id, balance, last_daily) VALUES (?, ?, ?)", (ctx.author.id, 1500, today))
            await db.commit()
            await ctx.send(f"{ctx.author.mention} You've received 1500 coins as your first daily reward!")
        else:
            balance, last_daily = row
            if last_daily == today:
                await ctx.send(f"{ctx.author.mention} You already claimed your daily reward today, try again after 24 Hrs!")
            else:
                balance += 500
                await db.execute("UPDATE users SET balance = ?, last_daily = ? WHERE user_id = ?", (balance, today, ctx.author.id))
                await db.commit()
                await ctx.send(f"{ctx.author.mention} You've received 500 coins as your daily reward!")

# Leaderboard command
@bot.command()
async def leaderboard(ctx):
    async with aiosqlite.connect("casino.db") as db:
        cursor = await db.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10")
        rows = await cursor.fetchall()

        if not rows:
            await ctx.send("Leaderboard is empty!")
            return

        embed = discord.Embed(title="🏆 Casino Leaderboard", color=discord.Color.brand_green())
        for i, (user_id, balance) in enumerate(rows, start=1):
            user = await bot.fetch_user(user_id)
            embed.add_field(name=f"{i}. {user.name}", value=f"{balance} coins", inline=False)

        await ctx.send(embed=embed)

# Roulette command
@bot.command()
async def roulette(ctx, bet: str, amount: int):
    bet = bet.lower()
    valid_colors = ['red', 'black', 'green']
    valid_ranges = ['1-12', '13-24', '25-36']
    valid_special = ['even', 'odd']

    try:
        bet_num = int(bet)
    except:
        bet_num = None

    async with aiosqlite.connect("casino.db") as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
        row = await cursor.fetchone()

        if row is None:
            await ctx.send("You don't have an account yet. Use `!balance` first.")
            return

        balance = row[0]
        if amount > balance or amount <= 0:
            await ctx.send("Invalid bet amount. Check your balance and try again.")
            return

        msg = await ctx.send(f"🎰 {ctx.author.display_name} Bet on **{bet.upper()}** with **{amount} coins**\nCountdown: 30 seconds")

        for i in range(29, -1, -1):
            await asyncio.sleep(1)
            await msg.edit(content=f"🎰 {ctx.author.display_name} Bet on **{bet.upper()}** with **{amount} coins**\nCountdown: {i} seconds")

        result = random.randint(0, 36)
        result_color = "green" if result == 0 else ("red" if result % 2 != 0 else "black")

        payout = 0
        win = False

        if bet in valid_colors and bet == result_color:
            payout = amount * (15 if bet == "green" else 2)
            win = True
        elif bet_num is not None and 0 <= bet_num <= 36 and bet_num == result:
            payout = amount * 36
            win = True
        elif bet in valid_special:
            if bet == "even" and result != 0 and result % 2 == 0:
                payout = amount * 2
                win = True
            elif bet == "odd" and result % 2 != 0:
                payout = amount * 2
                win = True
        elif bet in valid_ranges:
            if bet == "1-12" and 1 <= result <= 12:
                payout = amount * 6
                win = True
            elif bet == "13-24" and 13 <= result <= 24:
                payout = amount * 6
                win = True
            elif bet == "25-36" and 25 <= result <= 36:
                payout = amount * 6
                win = True
        else:
            await ctx.send("❌ Invalid bet!\nUsage examples:\n"
                           "`!roulette red 100`\n"
                           "`!roulette even 50`\n"
                           "`!roulette 17 20`\n"
                           "`!roulette 1-12 30`")
            return

        if win:
            balance += payout - amount
            await ctx.send(f"🎯 The ball landed on **{result} ({result_color.upper()})**!\n🎉 You won **{payout} coins!**")
        else:
            balance -= amount
            await ctx.send(f"❌ The ball landed on **{result} ({result_color.upper()})**.\nYou lost **{amount} coins.**")

        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance, ctx.author.id))
        await db.commit()
        await ctx.send(f"{ctx.author.mention} New balance: **{balance} coins**.")

# Run bot
async def main():
    async with bot:
        await bot.start(TOKEN)

asyncio.run(main())
