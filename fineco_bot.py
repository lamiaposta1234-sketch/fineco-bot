"""
Fineco Italia Trading Bot per Telegram
Usa Claude (Anthropic) con web search per analisi di mercato italiano
"""

import os
import anthropic
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

# ─── CONFIGURAZIONE ───────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_KEY  = os.environ["ANTHROPIC_API_KEY"]

ALLOWED_USER_ID = None  # es: 123456789 oppure None per accesso libero

# ─── PROMPT DI SISTEMA ────────────────────────────────────────────────────────
SYSTEM = """Sei un agente esperto di trading e investimenti per il mercato italiano, con focus su:
- Azioni italiane e FTSE MIB / FTSE Italia All-Share
- ETF disponibili su Fineco Bank
- BTP, obbligazioni e mercato obbligazionario italiano
- Fondi comuni e PAC disponibili su Fineco
- Fiscalità italiana per investitori (capital gain, dividendi, regime dichiarativo vs amministrato)
- Mercati europei rilevanti per investitori italiani (DAX, CAC, Eurostoxx)
- Notizie macro Italia ed Europa (BCE, spread BTP-Bund, inflazione)
- Analisi tecnica e fondamentale su titoli italiani

Hai accesso a ricerca web in tempo reale. Quando ti viene fatta una domanda:
1. Cerca le informazioni più aggiornate sul web
2. Analizza i dati in modo chiaro e strutturato
3. Fornisci insight pratici e actionable per un investitore retail italiano

Rispondi sempre in italiano. Sii preciso, chiaro e orientato all'azione.
Usa formattazione Markdown semplice (grassetto, elenchi puntati) che funziona su Telegram.
Quando parli di prezzi usa sempre EUR. Ricorda sempre che non sei un consulente finanziario autorizzato.
"""

conversation_history = {}
client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

def is_allowed(user_id: int) -> bool:
    if ALLOWED_USER_ID is None:
        return True
    return user_id == ALLOWED_USER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Accesso non autorizzato.")
        return
    conversation_history[update.effective_user.id] = []
    await update.message.reply_text(
        "👋 *Fineco Italia Trading Bot* attivo!\n\n"
        "Chiedimi qualsiasi cosa su:\n"
        "• Azioni italiane e FTSE MIB\n"
        "• ETF e fondi su Fineco\n"
        "• BTP e obbligazioni\n"
        "• Fiscalità per investitori italiani\n"
        "• Notizie macro Italia ed Europa\n\n"
        "Usa /reset per azzerare la conversazione.",
        parse_mode="Markdown"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_history[update.effective_user.id] = []
    await update.message.reply_text("🔄 Conversazione azzerata.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("⛔ Accesso non autorizzato.")
        return

    user_text = update.message.text
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({"role": "user", "content": user_text})

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=SYSTEM,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=conversation_history[user_id]
        )

        reply_text = ""
        for block in response.content:
            if block.type == "text":
                reply_text += block.text

        if response.stop_reason == "tool_use" and not reply_text:
            conversation_history[user_id].append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Ricerca completata. Elabora i risultati e rispondi."
                    })
            conversation_history[user_id].append({"role": "user", "content": tool_results})

            response2 = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                system=SYSTEM,
                messages=conversation_history[user_id]
            )
            for block in response2.content:
                if block.type == "text":
                    reply_text += block.text

            conversation_history[user_id].append({"role": "assistant", "content": reply_text})
        else:
            conversation_history[user_id].append({"role": "assistant", "content": reply_text})

        if len(conversation_history[user_id]) > 20:
            conversation_history[user_id] = conversation_history[user_id][-20:]

        if reply_text:
            try:
                await update.message.reply_text(reply_text, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(reply_text)
        else:
            await update.message.reply_text("⚠️ Nessuna risposta ricevuta. Riprova.")

    except Exception as e:
        await update.message.reply_text(f"❌ Errore: {str(e)}")


if __name__ == "__main__":
    print("🤖 Fineco Italia Bot avviato...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ In ascolto su Telegram")
    app.run_polling()
