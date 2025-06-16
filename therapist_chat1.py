from flask import Flask, render_template, request, jsonify, session
import google.generativeai as genai
import os
import uuid
from datetime import datetime
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

try:
    API_KEY = os.environ.get("GEMINI_API_KEY", "")
    if API_KEY == "PASTE_YOUR_API_KEY_HERE":
        logger.warning("API Key not set. Please replace 'PASTE_YOUR_API_KEY_HERE' with your actual key.")
    genai.configure(api_key=API_KEY)
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {e}")
    raise

SYSTEM_PROMPT = """
You are a compassionate and empathetic AI therapist. Your primary goal is to create a 
safe and supportive space for users to explore their thoughts and feelings. 

You should:
- Listen actively and patiently.
- Reflect on what the user shares to show you are paying attention.
- Ask open-ended questions to encourage deeper self-exploration.
- Maintain a warm, non-judgmental, and encouraging tone at all times.
- Validate the user's feelings and experiences.
- Provide helpful insights and gentle guidance when appropriate.
- Keep responses conversational and supportive.

You should NOT:
- Provide direct medical advice or diagnoses.
- Act as a replacement for a human therapist.
- Engage in casual, non-therapeutic conversation.
- Judge or criticize the user.

You are a source of comfort and support. If the user seems to be in crisis, 
gently suggest that talking to a professional or a crisis hotline might be helpful.
"""

MOOD_ANALYSIS_PROMPT = """
Analyze the user's mood from the following text. Respond with only ONE of the 
following single-word moods: [Happy, Sad, Angry, Anxious, Neutral, Calm, Stressed, Grateful, Confused].
If the mood is not clear, respond with 'Neutral'.
"""

MODEL_NAME = "gemini-2.0-flash"

chat_sessions = {}


def get_user_mood(user_message: str) -> str:
    try:
        mood_model = genai.GenerativeModel(MODEL_NAME, system_instruction=MOOD_ANALYSIS_PROMPT)
        response = mood_model.generate_content(user_message)
        mood = response.text.strip().capitalize()
        return mood
    except Exception as e:
        logger.error(f"Error during mood analysis: {e}")
        return "Unknown"


def get_or_create_chat_session(session_id):
    if session_id not in chat_sessions:
        logger.info(f"Creating new chat session for session_id: {session_id}")
        model = genai.GenerativeModel(
            MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
        )
        chat_sessions[session_id] = {
            'chat': model.start_chat(history=[]),
            'created_at': datetime.now(),
            'message_count': 0,
            'history_json': []
        }
    return chat_sessions[session_id]


@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return render_template('index.html')


@app.route('/send_message', methods=['POST'])
def send_message():
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400

        session_id = session.get('session_id')
        if not session_id:
            session['session_id'] = str(uuid.uuid4())
            session_id = session['session_id']

        chat_session_data = get_or_create_chat_session(session_id)
        chat = chat_session_data['chat']

        user_mood = get_user_mood(user_message)

        chat_session_data['history_json'].append({
            'role': 'user',
            'text': user_message,
            'mood': user_mood,
            'timestamp': datetime.now().isoformat()
        })

        response = chat.send_message(user_message)
        ai_response_text = response.text
        chat_session_data['message_count'] += 1

        chat_session_data['history_json'].append({
            'role': 'model',
            'text': ai_response_text,
            'timestamp': datetime.now().isoformat()
        })

        try:
            log_file_path = os.path.join('chat_logs', f'{session_id}.json')
            full_session_log = {
                'session_id': session_id,
                'created_at': chat_session_data['created_at'].isoformat(),
                'message_count': chat_session_data['message_count'],
                'history': chat_session_data['history_json']
            }
            with open(log_file_path, 'w', encoding='utf-8') as f:
                json.dump(full_session_log, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Failed to save chat history to file for session {session_id}: {e}")

        return jsonify({
            'response': ai_response_text,
            'mood': user_mood,
            'message_count': chat_session_data['message_count']
        })

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return jsonify({
            'error': 'I apologize, but I encountered an issue processing your message. Please try again.'
        }), 500


@app.route('/new_session', methods=['POST'])
def new_session():
    try:
        if 'session_id' in session:
            old_session_id = session['session_id']
            if old_session_id in chat_sessions:
                del chat_sessions[old_session_id]

        session['session_id'] = str(uuid.uuid4())
        return jsonify({'status': 'success', 'message': 'New session started'})
    except Exception as e:
        logger.error(f"Error starting new session: {e}")
        return jsonify({'error': 'Failed to start new session'}), 500


@app.route('/get_history', methods=['GET'])
def get_history():
    session_id = session.get('session_id')
    if not session_id or session_id not in chat_sessions:
        return jsonify({'error': 'No active session found'}), 404

    return jsonify({
        'session_id': session_id,
        'history': chat_sessions[session_id].get('history_json', [])
    })


@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('chat_logs', exist_ok=True)

    app.run(debug=True, host='0.0.0.0', port=5000)
