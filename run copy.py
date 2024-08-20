import asyncio
import nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import psycopg2
from datetime import datetime

# Apply the nest_asyncio patch
nest_asyncio.apply()

# Connect to PostgreSQL database
conn = psycopg2.connect(
    dbname="examprep",
    user="postgres",
    password="Yjdjehfkmcr1!",
    host="192.168.0.11",
    port="5432"
)

# Function to fetch a question from the database
def get_random_question(domain):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT question_id, question_text, option_a, option_b, option_c, option_d, correct_answer
            FROM question
            WHERE certification_short = %s
            ORDER BY RANDOM() LIMIT 1
        """, (domain,))
        return cur.fetchone()

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("CIA", callback_data='CIA')],
        [InlineKeyboardButton("CISA", callback_data='CISA')],
        [InlineKeyboardButton("PMP", callback_data='PMP')],
        [InlineKeyboardButton("Python", callback_data='Python')],
        [InlineKeyboardButton("English", callback_data='English')],
        [InlineKeyboardButton("Russian Auditor License", callback_data='Russian Auditor License')],
        [InlineKeyboardButton("Leaders of Russia Challenge", callback_data='Leaders of Russia Challenge')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Please select the knowledge area:', reply_markup=reply_markup)

# Callback handler for knowledge area selection
async def select_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    domain = query.data
    question_data = get_random_question(domain)
    
    if question_data:
        question_id, question_text, option_a, option_b, option_c, option_d, correct_answer = question_data
        
        keyboard = [
            [InlineKeyboardButton(option_a, callback_data=f'A-{question_id}')],
            [InlineKeyboardButton(option_b, callback_data=f'B-{question_id}')],
            [InlineKeyboardButton(option_c, callback_data=f'C-{question_id}')],
            [InlineKeyboardButton(option_d, callback_data=f'D-{question_id}')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(question_text, reply_markup=reply_markup)
    else:
        await query.message.reply_text('No questions available in this domain.')

# Callback handler for answer selection
async def answer_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_answer, question_id = query.data.split('-')
    
    with conn.cursor() as cur:
        cur.execute("""
            SELECT correct_answer FROM question WHERE question_id = %s
        """, (question_id,))
        correct_answer = cur.fetchone()[0]
    
    is_correct = (user_answer == correct_answer)
    user_id = update.effective_user.id
    attempt_date = datetime.now()
    
    # Save the attempt in the database
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO attempt (user_id, question_id, attempt_date, user_answer, is_correct)
            VALUES ('1', %s, %s, %s, %s)
        """, (question_id, attempt_date, user_answer, is_correct))
        conn.commit()
    
    response_text = "Correct!" if is_correct else f"Wrong! The correct answer was {correct_answer}."
    await query.message.reply_text(response_text)

async def main():
    application = Application.builder().token("7213212919:AAFSFnnshDBcG7oMbOH3195udH0EvGVqGJw").build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(select_area, pattern='^(CIA|CISA|PMP|Python|English|Russian Auditor License|Leaders of Russia Challenge)$'))
    application.add_handler(CallbackQueryHandler(answer_question, pattern='^(A|B|C|D)-'))
    
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())