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

def get_user_id(tg_id):

    with conn.cursor() as cur:
        cur.execute("""
            SELECT user_id FROM public."user" WHERE tg_id = %s
        """, (str(tg_id),))
        user_id = cur.fetchone()

    return user_id

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

# Function to format long text into multiple lines
def format_long_text(text, width=30):
    return '\n'.join(text[i:i+width] for i in range(0, len(text), width))

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('update.effective_user.id', update.effective_user.id)
    user_sessions[get_user_id(update.effective_user.id)] = {'questions': [], 'current_question': None, 'correct_count': 0}
    
    # Start menu with "Start Exam" button
    keyboard = [[InlineKeyboardButton("Start Exam", callback_data='start_exam')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Welcome! Please press "Start Exam" to begin.', reply_markup=reply_markup)

# Callback handler for start exam button
async def start_exam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Ask for the domain of knowledge area
    keyboard = [
        [InlineKeyboardButton("CIA", callback_data='CIA'), InlineKeyboardButton("CISA", callback_data='CISA')],
        [InlineKeyboardButton("PMP", callback_data='PMP'), InlineKeyboardButton("Python", callback_data='Python')],
        [InlineKeyboardButton("English", callback_data='English'), InlineKeyboardButton("Russian Auditor License", callback_data='Russian Auditor License')],
        [InlineKeyboardButton("Leaders of Russia Challenge", callback_data='Leaders of Russia Challenge')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text('Please select the knowledge area:', reply_markup=reply_markup)

# Callback handler for knowledge area selection
async def select_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    domain = query.data
    user_id = update.effective_user.id

    # print('str(update.effective_user.id) =', str(update.effective_user.id))
    # with conn.cursor() as cur:
    #     cur.execute("""
    #         SELECT user_id FROM public."user" WHERE tg_id = %s
    #     """, (str(update.effective_user.id),))
    #     user_id = cur.fetchone()

    user_sessions[get_user_id(update.effective_user.id)]['domain'] = domain

    # Ask for the number of questions
    await query.message.reply_text('How many questions would you like to answer?')

# Message handler to get the number of questions
async def handle_question_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id(update.effective_user.id)
    try:
        num_questions = int(update.message.text)
        user_sessions[user_id]['total_questions'] = num_questions
        
        # Start asking questions
        await ask_question(update, context)
    except ValueError:
        await update.message.reply_text('Please enter a valid number.')

# Function to ask a question
async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    domain = user_sessions[get_user_id(update.effective_user.id)]['domain']
    question_data = get_random_question(domain)
    
    if question_data:
        question_id, question_text, option_a, option_b, option_c, option_d, correct_answer = question_data
        
        # Store the current question in the session
        user_sessions[get_user_id(update.effective_user.id)]['current_question'] = {
            'question_id': question_id,
            'correct_answer': correct_answer
        }
        
        # Format options to handle long text
        option_a = format_long_text(option_a)
        option_b = format_long_text(option_b)
        option_c = format_long_text(option_c)
        option_d = format_long_text(option_d)

        # Format the question with options
        formatted_question = f"{question_text}\n\nA) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}"
        
        # Buttons only with labels A, B, C, D, placed 2 in each row
        keyboard = [
            [InlineKeyboardButton("A", callback_data=f'A-{question_id}'), InlineKeyboardButton("B", callback_data=f'B-{question_id}')],
            [InlineKeyboardButton("C", callback_data=f'C-{question_id}'), InlineKeyboardButton("D", callback_data=f'D-{question_id}')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(formatted_question, reply_markup=reply_markup)
    else:
        await update.message.reply_text('No questions available in this domain.')

# Callback handler for answer selection
async def answer_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data

    # Extract answer and question ID from callback data
    user_answer, question_id = data.split('-')
    
    user_session = user_sessions[get_user_id(update.effective_user.id)]
    current_question = user_session['current_question']
    correct_answer = current_question['correct_answer']

    is_correct = (user_answer == correct_answer)
    
    if is_correct:
        user_sessions[get_user_id(update.effective_user.id)]['correct_count'] += 1
    
    # Save the attempt in the database
    attempt_date = datetime.now()

    # with conn.cursor() as cur:
    #     cur.execute("""
    #         SELECT user_id FROM user WHERE tg_id = %s
    #     """, (update.effective_user.id))
    #     user_id = cur.fetchone()
    
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO attempt (user_id, question_id, attempt_date, user_answer, is_correct)
            VALUES (%s, %s, %s, %s, %s)
        """, (get_user_id(update.effective_user.id), question_id, attempt_date, user_answer, is_correct))
        conn.commit()
    
    response_text = "Correct!" if is_correct else f"Wrong! The correct answer was {correct_answer}."
    await query.message.reply_text(response_text)
    
    user_sessions[get_user_id(update.effective_user.id)]['questions'].append(current_question)
    
    # Check if there are more questions to ask
    if len(user_sessions[get_user_id(update.effective_user.id)]['questions']) < user_sessions[get_user_id(update.effective_user.id)]['total_questions']:
        await ask_question(update, context)
    else:
        correct_count = user_sessions[get_user_id(update.effective_user.id)]['correct_count']
        total_questions = user_sessions[get_user_id(update.effective_user.id)]['total_questions']
        await query.message.reply_text(f'Exam finished! You answered {correct_count} out of {total_questions} questions correctly.', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("OK", callback_data='OK')]]))
        del user_sessions[get_user_id(update.effective_user.id)]  # Clean up the session after completion

# Callback handler for OK button after exam
async def return_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await start(query, context)

async def main():
    application = Application.builder().token("7213212919:AAFSFnnshDBcG7oMbOH3195udH0EvGVqGJw").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(start_exam, pattern='start_exam'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question_count))
    application.add_handler(CallbackQueryHandler(select_area, pattern=r'^(CIA|CISA|PMP|Python|English|Russian Auditor License|Leaders of Russia Challenge)$'))
    application.add_handler(CallbackQueryHandler(answer_question, pattern=r'^(A|B|C|D)-\d+$'))
    application.add_handler(CallbackQueryHandler(return_to_start, pattern='OK'))

    await application.run_polling()

if __name__ == '__main__':
    # Use the existing event loop instead of asyncio.run
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())