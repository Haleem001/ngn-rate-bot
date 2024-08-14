import json
from datetime import datetime
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler
from playwright.async_api import async_playwright
import statistics
from pytz import timezone
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv('BOTAPITOKEN')
URL = os.getenv('URL')

SCRAPE_INTERVAL = 60  # 60 seconds for testing
PRICE_FILE = 'price_data.json'

def save_price(price):
    data = {
        'price': price,
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(PRICE_FILE, 'w') as f:
        json.dump(data, f)

def load_price():
    try:
        with open(PRICE_FILE, 'r') as f:
            data = json.load(f)
        saved_time = datetime.strptime(data['time'], "%Y-%m-%d %H:%M:%S")
        return data['price'], saved_time
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None, None

            
async def scrape_prices():
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with async_playwright() as p:
                browser = await p.firefox.launch(headless=True)
                context = await browser.new_context(
                    http_credentials={'username': '', 'password': ''},
                    ignore_https_errors=True
                )
                page = await context.new_page()
                await page.goto(URL, 
                                timeout=60000, 
                                wait_until='networkidle')
                await page.click("button.ant-btn.css-7o12g0.ant-btn-primary.ant-btn-custom.ant-btn-custom-middle.ant-btn-custom-primary.bds-theme-component-light")
                await page.wait_for_selector("span.price-amount", timeout=60000)
                price_elements = await page.query_selector_all("span.price-amount")
                prices = [float((await element.inner_text()).split()[0].replace(',', '')) for element in price_elements[:10]]
                average_price = statistics.mean(prices)
                await browser.close()
            save_price(average_price)
            return average_price
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}")
    print("All attempts failed")
    return None


async def get_current_price():
    price, saved_time = load_price()
    current_time = datetime.now()
    if price is None or (current_time - saved_time).total_seconds() > SCRAPE_INTERVAL:
        new_price = await scrape_prices()
        return new_price if new_price is not None else price
    return price

# async def start(update, context):
#     await update.message.reply_text('Welcome! Use /price to get the average price.')
async def start(update, context):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Hello, welcome to dollar to naira rates bot \n "
        'Use /help to show commands list'
    )

async def help(update, context):
   await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='/start - Start bot\n' +
        '/help - Show currency list\n' +
        '\n' +
        '/usd - Get current Dollar (USD) rate\n' +
        '/ngnusd - Convert Naira (NGN) to Dollar (USD). Example /ngnusd 1000  \n ' +
        '/usdngn - Convert Dollar (USD) to Naira (NGN). Example /usdngn 10 \n' +
        'For enquiries contact @HaleemG\n'
    )


async def get_price(update, context):
    price = await get_current_price()
    if price is not None:
        nigeria_time = timezone('Africa/Lagos')
        dt = datetime.now( nigeria_time)
        dt_string = dt.strftime("%A, %d-%m-%Y  • %H:%M:%S")
        note = '\U0001f4b5'
        await update.message.reply_text(f"{dt_string}\n\t\t\t\t\t\t\t USD-NGN \n\t\t\t\t\t\t\t {note} 1 USD => ₦{price :.2f}")
    else:
        await update.message.reply_text("Sorry, I couldn't fetch the price at the moment. Please try again later.")

async def ngnusdd(update, context):
    real = update.message.text.replace('/ngnusd', '')
    real = real.replace(',', '.')
    price = await get_current_price()
    if price is not None:
        real = float(real)
        convert = real/price
        await update.message.reply_text('₦{:,.2f} is ${:,.3f}'.format(real, convert))
    else:
        await update.message.reply_text("Sorry, I couldn't fetch the price at the moment. Please try again later.")


async def usdngnn(update, context):
    real = update.message.text.replace('/usdngn', '')
    real = real.replace(',', '.')
    real = float(real)
    price = await get_current_price()
    if price is not None:
        convert = real*price
        await update.message.reply_text('₦{:,.2f} is ${:,.3f}'.format(real, convert))
    else:
        await update.message.reply_text("Sorry, I couldn't fetch the price at the moment. Please try again later.")



async def scheduled_scrape(context):
    await scrape_prices()


def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("usd", get_price))
    application.add_handler(CommandHandler("usdngn", usdngnn))
    application.add_handler(CommandHandler("ngnusd", ngnusdd))
    application.add_handler(CommandHandler("help", help))
    application.job_queue.run_repeating(scheduled_scrape, interval=SCRAPE_INTERVAL)

    application.run_polling()

if __name__ == '__main__':
    main()
