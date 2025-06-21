import discord
from discord.ext import commands
import aiosqlite
import asyncio
from datetime import datetime
import random
import os
from dotenv import load_dotenv

# Load environment variables
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
                cash INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                last_daily TEXT
            )
        """)
        await db.commit()
    print(f'Logged in as {bot.user}!')

# Ensure user exists
async def ensure_user(db, user_id):
    cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    if row is None:
        await db.execute("INSERT INTO users (user_id, cash, bank, last_daily) VALUES (?, ?, ?, ?)", (user_id, 1000, 0, None))
        await db.commit()

# Balance command
@bot.command()
async def balance(ctx):
    async with aiosqlite.connect("casino.db") as db:
        await ensure_user(db, ctx.author.id)
        cursor = await db.execute("SELECT cash, bank FROM users WHERE user_id = ?", (ctx.author.id,))
        cash, bank = await cursor.fetchone()
        total = cash + bank
        await ctx.send(f"{ctx.author.mention} | 💰 Cash: {cash} | 🏦 Bank: {bank} | 🧮 Total: {total}")

# Deposit command
@bot.command()
async def deposit(ctx, amount: int):
    if amount <= 0:
        await ctx.send("You can't deposit 0 or negative!")
        return

    async with aiosqlite.connect("casino.db") as db:
        await ensure_user(db, ctx.author.id)
        cursor = await db.execute("SELECT cash, bank FROM users WHERE user_id = ?", (ctx.author.id,))
        cash, bank = await cursor.fetchone()

        if amount > cash:
            await ctx.send("Not enough cash to deposit!")
            return

        cash -= amount
        bank += amount

        await db.execute("UPDATE users SET cash = ?, bank = ? WHERE user_id = ?", (cash, bank, ctx.author.id))
        await db.commit()
        await ctx.send(f"{ctx.author.mention} Deposited {amount} coins to bank.")

# Withdraw command
@bot.command()
async def withdraw(ctx, amount: int):
    if amount <= 0:
        await ctx.send("You can't withdraw 0 or negative!")
        return

    async with aiosqlite.connect("casino.db") as db:
        await ensure_user(db, ctx.author.id)
        cursor = await db.execute("SELECT cash, bank FROM users WHERE user_id = ?", (ctx.author.id,))
        cash, bank = await cursor.fetchone()

        if amount > bank:
            await ctx.send("Not enough coins in bank!")
            return

        cash += amount
        bank -= amount

        await db.execute("UPDATE users SET cash = ?, bank = ? WHERE user_id = ?", (cash, bank, ctx.author.id))
        await db.commit()
        await ctx.send(f"{ctx.author.mention} Withdrew {amount} coins from bank.")

# Daily reward command (updated for cash)
@bot.command()
async def daily(ctx):
    async with aiosqlite.connect("casino.db") as db:
        await ensure_user(db, ctx.author.id)
        cursor = await db.execute("SELECT cash, last_daily FROM users WHERE user_id = ?", (ctx.author.id,))
        cash, last_daily = await cursor.fetchone()
        today = datetime.utcnow().date().isoformat()

        if last_daily == today:
            await ctx.send(f"{ctx.author.mention} You already claimed your daily reward today!")
        else:
            cash += 500
            await db.execute("UPDATE users SET cash = ?, last_daily = ? WHERE user_id = ?", (cash, today, ctx.author.id))
            await db.commit()
            await ctx.send(f"{ctx.author.mention} You received your daily reward of 500 coins!")

# Leaderboard command
@bot.command()
async def leaderboard(ctx):
    async with aiosqlite.connect("casino.db") as db:
        cursor = await db.execute("SELECT user_id, cash, bank FROM users")
        rows = await cursor.fetchall()

        leaderboard = sorted(rows, key=lambda x: x[1] + x[2], reverse=True)
        embed = discord.Embed(title="🏆 Leaderboard", color=discord.Color.brand_green())

        for i, row in enumerate(leaderboard[:10], start=1):
            user = await bot.fetch_user(row[0])
            total = row[1] + row[2]
            embed.add_field(name=f"{i}. {user.name}", value=f"Total: {total} coins (Cash: {row[1]}, Bank: {row[2]})", inline=False)

        await ctx.send(embed=embed)

# Roulette command (only cash used for bets)
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
        await ensure_user(db, ctx.author.id)
        cursor = await db.execute("SELECT cash FROM users WHERE user_id = ?", (ctx.author.id,))
        cash = (await cursor.fetchone())[0]

        if amount > cash or amount <= 0:
            await ctx.send("Invalid bet amount!")
            return

        msg = await ctx.send(f"🎰 {ctx.author.display_name} Bet on **{bet.upper()}** with **{amount} coins**\nCountdown: 10 seconds")

        for i in range(9, -1, -1):
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
            await ctx.send("❌ Invalid bet!\nExample: `!roulette red 100`")
            return

        if win:
            cash += payout - amount
            await ctx.send(f"🎯 The ball landed on **{result} ({result_color.upper()})**!\n🎉 You won **{payout} coins!**")
        else:
            cash -= amount
            await ctx.send(f"❌ The ball landed on **{result} ({result_color.upper()})**.\nYou lost **{amount} coins.**")

        await db.execute("UPDATE users SET cash = ? WHERE user_id = ?", (cash, ctx.author.id))
        await db.commit()
        await ctx.send(f"{ctx.author.mention} New cash balance: **{cash} coins**.")

# Run bot
async def main():
    async with bot:
        await bot.start(TOKEN)

asyncio.run(main())
