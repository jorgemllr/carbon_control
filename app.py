import openai
import mysql.connector
from flask import Flask, request, jsonify, render_template
import os
import bcrypt

openai.api_key = os.environ.get("OPENAI_API_KEY")

DB_CONFIG = {
    "host": os.environ.get("DB_HOST"),
    "user": os.environ.get("DB_USER"),
    "password": os.environ.get("DB_PASSWORD"),
    "database": os.environ.get("DB_NAME"),
    "port": int(os.environ.get("DB_PORT", 3306)),
}

app = Flask(__name__)

def get_database_context():
    """Fetch all data from the MySQL database and return it as a formatted string."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT location, data FROM cc_data")
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        context = ""
        for row in rows:
            context += f"Location: {row['location']}\nData: {row['data']}\n\n"

        return context.strip()
    except mysql.connector.Error as e:
        print(f"Error connecting to MySQL: {e}")
        return "Error: Unable to load data."

def chatbot_response(prompt, context):
    """Generate a chatbot response using OpenAI API."""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": context},
            {"role": "user", "content": prompt}
        ]
    )
    return response['choices'][0]['message']['content']

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    """Handle chatbot queries from the frontend."""
    user_input = request.form['user_input']
    context = get_database_context()
    response = chatbot_response(user_input, context)
    return jsonify({'response': response})

@app.route('/signup', methods=['POST'])
def signup():
    """Registers a new user in the database."""
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        query = "INSERT INTO pford_users (email, password_hash, full_name) VALUES (%s, %s, %s)"
        cursor.execute(query, (email, hashed_password.decode('utf-8'), ""))
        conn.commit()

        cursor.close()
        conn.close()
        return jsonify({"message": "Registration successful"}), 201

    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    
    app.run(host='0.0.0.0', port=5000, debug=True)