import asyncio
import nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
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

# Global variable to store user data
user_sessions = {}

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
    user_sessions[update.effective_user.id] = {'questions': [], 'current_question': None, 'correct_count': 0}

    await update.message.reply_text('How many questions would you like to answer?')

# Message handler to get the number of questions
async def handle_question_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        num_questions = int(update.message.text)
        user_sessions[user_id]['total_questions'] = num_questions
        
        # Ask for the domain of knowledge area
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
    except ValueError:
        await update.message.reply_text('Please enter a valid number.')

# Callback handler for knowledge area selection
async def select_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    domain = query.data
    user_id = update.effective_user.id
    user_sessions[user_id]['domain'] = domain

    await ask_question(update, context)

# Function to ask a question
async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    domain = user_sessions[user_id]['domain']
    question_data = get_random_question(domain)
    
    if question_data:
        question_id, question_text, option_a, option_b, option_c, option_d, correct_answer = question_data
        
        # Store the current question in the session
        user_sessions[user_id]['current_question'] = {
            'question_id': question_id,
            'correct_answer': correct_answer
        }
        
        keyboard = [
            [InlineKeyboardButton(option_a, callback_data=f'A-{question_id}')],
            [InlineKeyboardButton(option_b, callback_data=f'B-{question_id}')],
            [InlineKeyboardButton(option_c, callback_data=f'C-{question_id}')],
            [InlineKeyboardButton(option_d, callback_data=f'D-{question_id}')],
            [InlineKeyboardButton("Answer", callback_data='Answer')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text(question_text, reply_markup=reply_markup)
    else:
        await update.callback_query.message.reply_text('No questions available in this domain.')

# Callback handler for answer selection
async def answer_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data == 'Answer':
        user_session = user_sessions[user_id]
        current_question = user_session['current_question']
        user_answer = current_question.get('user_answer')

        if user_answer is None:
            await query.message.reply_text("Please select an option before submitting your answer.")
            return
        
        question_id = current_question['question_id']
        correct_answer = current_question['correct_answer']
        is_correct = (user_answer == correct_answer)
        
        if is_correct:
            user_sessions[user_id]['correct_count'] += 1
        
        # Save the attempt in the database
        attempt_date = datetime.now()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO attempt (user_id, question_id, attempt_date, user_answer, is_correct)
                VALUES (1, %s, %s, %s, %s)
            """, (question_id, attempt_date, user_answer, is_correct))
            conn.commit()
        
        response_text = "Correct!" if is_correct else f"Wrong! The correct answer was {correct_answer}."
        await query.message.reply_text(response_text)
        
        user_sessions[user_id]['questions'].append(current_question)
        
        # Check if there are more questions to ask
        if len(user_sessions[user_id]['questions']) < user_sessions[user_id]['total_questions']:
            await ask_question(update, context)
        else:
            correct_count = user_sessions[user_id]['correct_count']
            total_questions = user_sessions[user_id]['total_questions']
            await query.message.reply_text(f'Exam finished! You answered {correct_count} out of {total_questions} questions correctly.')
            del user_sessions[user_id]  # Clean up the session after completion
    else:
        # Store the selected answer
        user_sessions[user_id]['current_question']['user_answer'] = data[0]

async def main():
    application = Application.builder().token("7213212919:AAFSFnnshDBcG7oMbOH3195udH0EvGVqGJw").build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question_count))
    application.add_handler(CallbackQueryHandler(select_area, pattern='^(CIA|CISA|PMP|Python|English|Russian Auditor License|Leaders of Russia Challenge)$'))
    application.add_handler(CallbackQueryHandler(answer_question, pattern='^(A|B|C|D|Answer)-?'))

    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
