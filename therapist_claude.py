from flask import Flask, render_template, request, jsonify, session
import google.generativeai as genai
import os
import uuid
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'  # Change this in production

# --- Configuration ---
try:
    genai.configure(api_key="AIzaSyDJxzAo_gP2PMVDDCK2ntHCT5OIatSnUN4")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {e}")
    raise

# --- System Prompt and Model Configuration ---
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

MODEL_NAME = "gemini-2.0-flash"

# Store chat sessions in memory (use database in production)
chat_sessions = {}

def get_or_create_chat_session(session_id):
    """Get existing chat session or create a new one."""
    if session_id not in chat_sessions:
        model = genai.GenerativeModel(
            MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
        )
        chat_sessions[session_id] = {
            'chat': model.start_chat(history=[]),
            'created_at': datetime.now(),
            'message_count': 0
        }
    return chat_sessions[session_id]

@app.route('/')
def index():
    """Main page with chat interface."""
    # Generate or get session ID
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    return render_template('index.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    """Handle user messages and return AI response."""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Get session ID
        session_id = session.get('session_id')
        if not session_id:
            session['session_id'] = str(uuid.uuid4())
            session_id = session['session_id']
        
        # Get or create chat session
        chat_session = get_or_create_chat_session(session_id)
        
        # Send message to AI
        response = chat_session['chat'].send_message(user_message)
        chat_session['message_count'] += 1
        
        return jsonify({
            'response': response.text,
            'message_count': chat_session['message_count']
        })
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return jsonify({
            'error': 'I apologize, but I encountered an issue processing your message. Please try again.'
        }), 500

@app.route('/new_session', methods=['POST'])
def new_session():
    """Start a new therapy session."""
    try:
        # Clear current session
        if 'session_id' in session:
            old_session_id = session['session_id']
            if old_session_id in chat_sessions:
                del chat_sessions[old_session_id]
        
        # Create new session
        session['session_id'] = str(uuid.uuid4())
        
        return jsonify({'status': 'success', 'message': 'New session started'})
        
    except Exception as e:
        logger.error(f"Error starting new session: {e}")
        return jsonify({'error': 'Failed to start new session'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)