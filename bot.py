import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import anthropic
import json
import random
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Simulated price data
def get_gold_price():
    base = 3230
    change = random.uniform(-15, 15)
    price = base + change
    return round(price, 2)

def get_market_data():
    price = get_gold_price()
    prices = [price + random.uniform(-20, 20) for _ in range(20)]
    prices[-1] = price
    
    # RSI calculation
    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [c for c in changes if c > 0]
    losses = [-c for c in changes if c < 0]
    avg_gain = sum(gains[-14:]) / 14 if gains else 0
    avg_loss = sum(losses[-14:]) / 14 if losses else 0.001
    rs = avg_gain / avg_loss
    rsi = round(100 - (100 / (1 + rs)), 1)
    
    # EMA
    ema9 = round(sum(prices[-9:]) / 9, 2)
    ema21 = round(sum(prices[-20:]) / 20, 2) if len(prices) >= 20 else price
    
    # ATR
    atr = round(random.uniform(4, 12), 2)
    
    prev_price = prices[-2]
    change_pct = round((price - prev_price) / prev_price * 100, 3)
    
    return {
        "price": price,
        "prev_price": prev_price,
        "change": round(price - prev_price, 2),
        "change_pct": change_pct,
        "rsi": rsi,
        "ema9": ema9,
        "ema21": ema21,
        "atr": atr,
        "high": round(price + atr * 0.8, 2),
        "low": round(price - atr * 0.8, 2)
    }

def analyze_with_ai(data):
    prompt = f"""Sen profesyonel bir XAUUSD (Altın/Dolar) trader botusun. Aşağıdaki verileri analiz et.

GÜNCEL VERİLER:
- Fiyat: {data['price']}
- Değişim: {data['change']} ({data['change_pct']}%)
- RSI(14): {data['rsi']}
- EMA9: {data['ema9']} | EMA21: {data['ema21']}
- ATR: {data['atr']}
- Günlük High: {data['high']} | Low: {data['low']}

Sadece JSON döndür, başka hiçbir şey yazma:
{{
  "signal": "BUY" veya "SELL" veya "WAIT",
  "confidence": 1-100,
  "entry": giriş fiyatı,
  "sl": stop loss,
  "tp1": hedef 1,
  "tp2": hedef 2,
  "reason": "Türkçe açıklama max 100 karakter",
  "risk": "DÜŞÜK" veya "ORTA" veya "YÜKSEK",
  "timeframe": "kısa-vade" veya "orta-vade"
}}"""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    
    text = message.content[0].text
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Analiz Et", callback_data="analyze")],
        [InlineKeyboardButton("💰 Fiyat", callback_data="price"),
         InlineKeyboardButton("📈 Göstergeler", callback_data="indicators")],
        [InlineKeyboardButton("ℹ️ Hakkında", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🥇 *XAUUSD Altın Sinyal Botu*\n\n"
        "Merhaba! Ben yapay zeka destekli altın trading botuyum.\n"
        "Size giriş/çıkış sinyalleri veriyorum.\n\n"
        "⚠️ _Bu bot eğitim amaçlıdır. Yatırım tavsiyesi değildir._",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "analyze":
        await query.edit_message_text("⏳ Piyasa analiz ediliyor...")
        
        try:
            data = get_market_data()
            analysis = analyze_with_ai(data)
            
            signal = analysis.get("signal", "WAIT")
            emoji = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "🟡"
            signal_tr = "AL 📈" if signal == "BUY" else "SAT 📉" if signal == "SELL" else "BEKLE ⏸"
            
            msg = f"{emoji} *SİNYAL: {signal_tr}*\n\n"
            msg += f"💵 Fiyat: `${data['price']}`\n"
            msg += f"📊 Güven: `%{analysis.get('confidence', 0)}`\n"
            msg += f"⚠️ Risk: `{analysis.get('risk', 'ORTA')}`\n\n"
            
            if signal != "WAIT":
                msg += f"🎯 Giriş: `${analysis.get('entry', data['price'])}`\n"
                msg += f"🛑 Stop Loss: `${analysis.get('sl', '')}`\n"
                msg += f"✅ Hedef 1: `${analysis.get('tp1', '')}`\n"
                msg += f"✅ Hedef 2: `${analysis.get('tp2', '')}`\n\n"
            
            msg += f"📝 _{analysis.get('reason', '')}_\n\n"
            msg += f"⏱ Vade: {analysis.get('timeframe', 'kısa-vade')}"
            
            keyboard = [[InlineKeyboardButton("🔄 Yenile", callback_data="analyze"),
                        InlineKeyboardButton("🏠 Ana Menü", callback_data="menu")]]
            
            await query.edit_message_text(
                msg,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            await query.edit_message_text(
                "❌ Analiz sırasında hata oluştu. Tekrar deneyin.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Tekrar", callback_data="analyze")
                ]])
            )
    
    elif query.data == "price":
        data = get_market_data()
        change_emoji = "📈" if data['change'] >= 0 else "📉"
        
        msg = f"💰 *XAUUSD Anlık Fiyat*\n\n"
        msg += f"💵 Fiyat: `${data['price']}`\n"
        msg += f"{change_emoji} Değişim: `{data['change']:+.2f}` ({data['change_pct']:+.3f}%)\n"
        msg += f"📊 Yüksek: `${data['high']}`\n"
        msg += f"📊 Düşük: `${data['low']}`"
        
        keyboard = [[InlineKeyboardButton("🔄 Güncelle", callback_data="price"),
                    InlineKeyboardButton("🏠 Menü", callback_data="menu")]]
        
        await query.edit_message_text(
            msg, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "indicators":
        data = get_market_data()
        
        rsi_status = "🔴 Aşırı Alım" if data['rsi'] > 70 else "🟢 Aşırı Satım" if data['rsi'] < 30 else "🟡 Nötr"
        ema_status = "🟢 Yukari" if data['ema9'] > data['ema21'] else "🔴 Aşağı"
        
        msg = f"📈 *Teknik Göstergeler*\n\n"
        msg += f"RSI(14): `{data['rsi']}` — {rsi_status}\n"
        msg += f"EMA9: `{data['ema9']}`\n"
        msg += f"EMA21: `{data['ema21']}`\n"
        msg += f"EMA Trend: {ema_status}\n"
        msg += f"ATR(14): `{data['atr']}`\n\n"
        msg += f"_Veriler simüle edilmiştir_"
        
        keyboard = [[InlineKeyboardButton("🔄 Güncelle", callback_data="indicators"),
                    InlineKeyboardButton("🏠 Menü", callback_data="menu")]]
        
        await query.edit_message_text(
            msg, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data in ["menu", "about"]:
        keyboard = [
            [InlineKeyboardButton("📊 Analiz Et", callback_data="analyze")],
            [InlineKeyboardButton("💰 Fiyat", callback_data="price"),
             InlineKeyboardButton("📈 Göstergeler", callback_data="indicators")],
            [InlineKeyboardButton("ℹ️ Hakkında", callback_data="about")]
        ]
        
        if query.data == "about":
            text = ("ℹ️ *XAUUSD Sinyal Botu Hakkında*\n\n"
                   "Bu bot yapay zeka kullanarak altın piyasasını analiz eder.\n\n"
                   "📊 RSI, EMA, ATR göstergelerini kullanır\n"
                   "🤖 Claude AI ile sinyal üretir\n"
                   "⚡ Anlık analiz yapar\n\n"
                   "⚠️ _Yatırım tavsiyesi değildir!_")
        else:
            text = ("🥇 *XAUUSD Altın Sinyal Botu*\n\n"
                   "Ne yapmak istersiniz?")
        
        await query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Analiz ediliyor...")
    try:
        data = get_market_data()
        analysis = analyze_with_ai(data)
        signal = analysis.get("signal", "WAIT")
        emoji = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "🟡"
        signal_tr = "AL 📈" if signal == "BUY" else "SAT 📉" if signal == "SELL" else "BEKLE ⏸"
        
        msg = f"{emoji} *SİNYAL: {signal_tr}*\n\n"
        msg += f"💵 Fiyat: `${data['price']}`\n"
        msg += f"📊 Güven: `%{analysis.get('confidence', 0)}`\n"
        if signal != "WAIT":
            msg += f"🎯 Giriş: `${analysis.get('entry', '')}`\n"
            msg += f"🛑 Stop: `${analysis.get('sl', '')}`\n"
            msg += f"✅ TP1: `${analysis.get('tp1', '')}`\n"
            msg += f"✅ TP2: `${analysis.get('tp2', '')}`\n\n"
        msg += f"📝 _{analysis.get('reason', '')}_"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text("❌ Hata oluştu, tekrar deneyin.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analiz", analyze_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("Bot başlatıldı...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
