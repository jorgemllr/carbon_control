import openai
import mysql.connector
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_from_directory
import os
import bcrypt
import time
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename
import boto3

# Configuración de OpenAI
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Configuración de la base de datos
DB_CONFIG = {
    "host": "roundhouse.proxy.rlwy.net",
    "user": "root",
    "password": "PftmussYrgKSEkMxNpktZlPpoVICGEDv",
    "database": "meslatt_data",
    "port": 50455
}

# Configuración de AWS S3
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or 'tu_clave_secreta_aleatoria_aqui'

# Configuración para guardar imágenes
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Función para subir a S3
def upload_to_s3(file, filename):
    try:
        s3.upload_fileobj(
            file,
            os.getenv('S3_BUCKET_NAME'),
            f"uploads/{filename}",
            ExtraArgs={
                'ACL': 'private',
                'ContentType': file.content_type
            }
        )
        return f"https://{os.getenv('S3_BUCKET_NAME')}.s3.amazonaws.com/uploads/{filename}"
    except Exception as e:
        print(f"Error S3: {str(e)}")
        return None

# Decorador para admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
            
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT is_admin FROM pford_users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user or not user.get('is_admin'):
            return jsonify({'error': 'Admin access required'}), 403
            
        return f(*args, **kwargs)
    return decorated_function

# Helper functions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_database_context():
    """Obtiene contexto de la base de datos"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT location, data FROM cc_data")
        return "\n".join([f"Location: {row['location']}\nData: {row['data']}" for row in cursor.fetchall()])
    except mysql.connector.Error as e:
        print(f"Error MySQL: {e}")
        return "Error: No se pudo cargar datos"
    finally:
        cursor.close()
        conn.close()

# Luego usa @admin_required en lugar de @login_required para las rutas de admin

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
    name = data.get("name")  # Nuevo campo

    if not email or not password or not name:  # Validar que el nombre no esté vacío
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

        # Modificar la query para incluir el nombre
        query = "INSERT INTO pford_users (email, password_hash, credits, name) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (email, hashed_password.decode('utf-8'), 10, name))  # 10 créditos iniciales
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
                "name": name.split()[0],  # Solo primer nombre
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
                    "name": user.get('name', ''),  # Incluir el nombre
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
            cursor.close()
            conn.close()
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # 1. Subir imagen a S3
        filename = secure_filename(f"redeem_{session['user_id']}_{int(time.time())}_{image_file.filename}")
        s3_url = upload_to_s3(image_file, filename)
        
        if not s3_url:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Error al subir la imagen a S3'}), 500
        
        # 2. Guardar en base de datos (con URL de S3)
        cursor.execute(
            "INSERT INTO eco_actions (user_id, user_email, description, image_path) VALUES (%s, %s, %s, %s)",
            (session['user_id'], user['email'], description, s3_url)  # Guardamos la URL completa de S3
        )
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Acción canjeada con éxito',
            'image_url': s3_url  # Opcional: devolver la URL para el frontend
        })
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Error de base de datos: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()
    
@app.route('/report_action', methods=['POST'])
@login_required
def report_action():
    try:
        # Validación de campos
        if 'image' not in request.files:
            return jsonify({'error': 'No se subió ninguna imagen'}), 400
            
        image_file = request.files['image']
        action_type = request.form.get('action_type')
        description = request.form.get('description')
        
        if not action_type:
            return jsonify({'error': 'Tipo de acción requerido'}), 400
            
        if image_file.filename == '':
            return jsonify({'error': 'Nombre de archivo no válido'}), 400
        
        if not allowed_file(image_file.filename):
            return jsonify({'error': 'Tipo de archivo no permitido'}), 400
            
        # Obtener información del usuario
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT name, email FROM pford_users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # 1. Subir imagen a S3
        filename = secure_filename(f"report_{session['user_id']}_{int(time.time())}_{image_file.filename}")
        s3_url = upload_to_s3(image_file, filename)  # Usamos la función que creamos
        
        if not s3_url:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Error al subir la imagen'}), 500
        
        # 2. Guardar en base de datos (con todos los campos)
        cursor.execute(
            """INSERT INTO reported_actions 
            (user_id, name, user_email, description, image_path, status) 
            VALUES (%s, %s, %s, %s, %s, 'pending')""",
            (
                session['user_id'],
                user['name'],
                user['email'],
                f"{action_type}: {description}",
                s3_url  # Guardamos la URL completa de S3
            )
        )
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Acción reportada con éxito. Se verificará pronto.',
            'image_url': s3_url  # Opcional: devolver la URL para el frontend
        })
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Error de base de datos: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()
    
@app.route('/get_image/<filename>')
def get_image(filename):
    url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': os.getenv('S3_BUCKET_NAME'),
               'Key': f"uploads/{filename}"},
        ExpiresIn=3600  # URL válida por 1 hora
    )
    return redirect(url)
    
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
    
@app.route('/ZxK8pY2W/reported_actions')
@login_required
def admin_reported_actions():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # Obtener todas las acciones reportadas
        cursor.execute("""
            SELECT * FROM reported_actions 
            ORDER BY created_at DESC
        """)
        actions = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('reported-actions.html', actions=actions)
        
    except Exception as e:
        return str(e), 500

@app.route('/admin/update_action_status', methods=['POST'])
@login_required
def update_action_status():
    try:
        data = request.json
        action_id = data.get('action_id')
        new_status = data.get('status')
        
        if not action_id or not new_status:
            return jsonify({'error': 'Missing parameters'}), 400
            
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # 1. Actualizar el estado de la acción
        cursor.execute("""
            UPDATE reported_actions 
            SET status = %s 
            WHERE id = %s
        """, (new_status, action_id))
        
        # 2. Si se aprueba, agregar créditos al usuario
        if new_status == 'approved':
            # Primero obtenemos el user_id y determinamos los créditos
            cursor.execute("""
                SELECT user_id, description 
                FROM reported_actions 
                WHERE id = %s
            """, (action_id,))
            action = cursor.fetchone()
            
            # Determinar créditos basados en la descripción (ajusta esta lógica según tus necesidades)
            credits = 10  # Valor por defecto
            if "reciclaje" in action['description'].lower():
                credits = 10
            elif "limpieza" in action['description'].lower():
                credits = 15
            # Agrega más condiciones según tus categorías
            
            # Actualizar créditos del usuario
            cursor.execute("""
                UPDATE pford_users 
                SET credits = credits + %s 
                WHERE id = %s
            """, (credits, action['user_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Status updated to {new_status}'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
