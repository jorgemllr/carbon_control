import openai
import mysql.connector
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import os
import bcrypt
import time
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename

# Configuración de OpenAI
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Configuración de la base de datos
DB_CONFIG = {
    "host": os.environ.get("DB_HOST"),
    "user": os.environ.get("DB_USER"),
    "password": os.environ.get("DB_PASSWORD"),
    "database": os.environ.get("DB_NAME"),
    "port": int(os.environ.get("DB_PORT", 3306)),
}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or 'tu_clave_secreta_aleatoria_aqui'

# Configuración para guardar imágenes
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Decorador para rutas protegidas
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

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
@login_required
def ask():
    """Handle chatbot queries from the frontend."""
    user_input = request.form['user_input']
    context = get_database_context()
    response = chatbot_response(user_input, context)
    
    # Actualizar créditos del usuario (restar 1 por pregunta)
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("UPDATE pford_users SET credits = credits - 1 WHERE id = %s", (session['user_id'],))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Actualizar sesión
        session['user_credits'] -= 1
    except Exception as e:
        print(f"Error updating credits: {e}")
    
    return jsonify({'response': response})

@app.route('/signup', methods=['POST'])
def signup():
    """Registers a new user in the database."""
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Todos los campos son requeridos"}), 400

    # Verificar si el correo termina en @soyunaq.mx
    if not email.endswith('@soyunaq.mx'):
        return jsonify({"error": "Solo se permiten correos institucionales @soyunaq.mx"}), 400

    # Validar longitud de contraseña
    if len(password) < 8:
        return jsonify({"error": "La contraseña debe tener al menos 8 caracteres"}), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Verificar si el correo ya existe
        cursor.execute("SELECT * FROM pford_users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"error": "Este correo ya está registrado"}), 400

        query = "INSERT INTO pford_users (email, password_hash, credits) VALUES (%s, %s, %s)"
        cursor.execute(query, (email, hashed_password.decode('utf-8'), 10))  # 10 créditos iniciales
        conn.commit()

        # Obtener el usuario recién creado
        cursor.execute("SELECT * FROM pford_users WHERE email = %s", (email,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        # Iniciar sesión
        session['user_id'] = user['id']
        session['user_email'] = user['email']
        session['user_credits'] = user['credits']
        
        return jsonify({
            "message": "Registro exitoso",
            "user": {
                "id": user['id'],
                "email": user['email'],
                "credits": user['credits']
            }
        }), 201

    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    """Handle user login."""
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email y contraseña requeridos"}), 400

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM pford_users WHERE email = %s", (email,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if not user:
            return jsonify({"error": "Credenciales inválidas"}), 401

        if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            # Iniciar sesión
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_credits'] = user['credits']
            
            return jsonify({
                "message": "Inicio de sesión exitoso",
                "user": {
                    "id": user['id'],
                    "email": user['email'],
                    "credits": user['credits']
                }
            }), 200
        else:
            return jsonify({"error": "Credenciales inválidas"}), 401

    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 500

@app.route('/logout')
def logout():
    """Handle user logout."""
    session.clear()
    return jsonify({"message": "Sesión cerrada exitosamente"}), 200

@app.route('/profile')
def profile():
    """User profile page."""
    if 'user_id' not in session:
        return jsonify({"error": "No autenticado"}), 401
    
    return jsonify({
        'user': {
            'id': session['user_id'],
            'email': session['user_email'],
            'credits': session['user_credits']
        }
    })

@app.route('/check_session')
def check_session():
    """Check if user is logged in."""
    if 'user_id' in session:
        return jsonify({
            'logged_in': True,
            'user': {
                'id': session['user_id'],
                'email': session['user_email'],
                'credits': session['user_credits']
            }
        })
    return jsonify({'logged_in': False})

@app.route('/redeem_action', methods=['POST'])
@login_required
def redeem_action():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No se subió ninguna imagen'}), 400
            
        image_file = request.files['image']
        description = request.form.get('description', '')
        
        if image_file.filename == '':
            return jsonify({'error': 'Nombre de archivo no válido'}), 400
        
        if not allowed_file(image_file.filename):
            return jsonify({'error': 'Tipo de archivo no permitido'}), 400
            
        # Obtener información del usuario
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT email FROM pford_users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # Guardar imagen
        filename = secure_filename(f"{session['user_id']}_{int(time.time())}_{image_file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(filepath)
        
        # Guardar en base de datos
        cursor.execute(
            "INSERT INTO eco_actions (user_id, user_email, description, image_path) VALUES (%s, %s, %s, %s)",
            (session['user_id'], user['email'], description, filename)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/report_action', methods=['POST'])
@login_required
def report_action():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No se subió ninguna imagen'}), 400
            
        image_file = request.files['image']
        description = request.form.get('description', '')
        
        if image_file.filename == '':
            return jsonify({'error': 'Nombre de archivo no válido'}), 400
        
        if not allowed_file(image_file.filename):
            return jsonify({'error': 'Tipo de archivo no permitido'}), 400
            
        # Obtener información del usuario
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT email FROM pford_users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # Guardar imagen
        filename = secure_filename(f"report_{session['user_id']}_{int(time.time())}_{image_file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(filepath)
        
        # Guardar en base de datos (tabla reported_actions)
        cursor.execute(
            "INSERT INTO reported_actions (user_id, user_email, description, image_path) VALUES (%s, %s, %s, %s)",
            (session['user_id'], user['email'], description, filename)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Acción reportada con éxito. Se verificará pronto.'
        })
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Error de base de datos: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500
    
@app.route('/admin/actions')
@login_required  # Puedes agregar un decorador adicional para verificar si es admin
def admin_actions():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT ea.*, u.credits 
            FROM eco_actions ea
            JOIN pford_users u ON ea.user_id = u.id
            ORDER BY ea.created_at DESC
        """)
        actions = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return render_template('admin_actions.html', actions=actions)
        
    except Exception as e:
        return str(e), 500

@app.route('/update_credits', methods=['POST'])
@login_required
def update_credits():
    """Update user credits."""
    data = request.json
    amount = data.get('amount', 0)
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # Actualizar créditos en la base de datos
        cursor.execute(
            "UPDATE pford_users SET credits = credits + %s WHERE id = %s",
            (amount, session['user_id'])
        )
        conn.commit()
        
        # Obtener nuevos créditos
        cursor.execute(
            "SELECT credits FROM pford_users WHERE id = %s",
            (session['user_id'],)
        )
        new_credits = cursor.fetchone()['credits']
        
        cursor.close()
        conn.close()
        
        # Actualizar sesión
        session['user_credits'] = new_credits
        
        return jsonify({
            'success': True,
            'new_credits': new_credits
        })
    except mysql.connector.Error as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
