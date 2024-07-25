import streamlit as st
import google.generativeai as genai
import hashlib
import mysql.connector
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

# Configure the API key
api_key = os.getenv('API_KEY')
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-pro')

# Initialize session state for chat history and authentication
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'email' not in st.session_state:
    st.session_state.email = ""

# Set default theme to dark mode with contrasting text colors
st.markdown(
    """
    <style>
    body {
        background-color: #303030;
        color: #f1f1f1;
    }
    .message-user, .message-ai {
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .message-user {
        background-color: #333333;
        color: #ffffff;
        text-align: right;
    }
    .message-ai {
        background-color: #444444;
        color: #ffffff;
        text-align: left;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Function to create a MySQL connection
def create_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),    # Replace with your MySQL host
        user=os.getenv('DB_USER'),    # Replace with your MySQL username
        password=os.getenv('DB_PASSWORD'),  # Replace with your MySQL password
        database=os.getenv('DB_NAME')   # Replace with your MySQL database name
    )

# Function to initialize the MySQL database
def init_db():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                      username VARCHAR(255) PRIMARY KEY,
                      password VARCHAR(255),
                      email VARCHAR(255) UNIQUE,
                      reset_token VARCHAR(255),
                      token_expiration INTEGER)''')
    conn.commit()
    cursor.close()
    conn.close()

# Function to add chat to history
def add_to_chat_history(user_input, response):
    st.session_state.chat_history.append({
        "user_input": user_input,
        "response": response
    })

# Function to check for rule violations
def check_for_violations(user_input):
    # Example rule: no offensive language (simple example)
    offensive_words = ['offensive_word1', 'offensive_word2']  # Add more as needed
    for word in offensive_words:
        if word in user_input.lower():
            return True
    return False

# Function to generate a response from the model with context
def generate_response_with_context(user_input):
    # Create a context string from the chat history
    context = "\n".join([f"User: {chat['user_input']}\nAI: {chat['response']}" for chat in st.session_state.chat_history])
    if context:
        context += f"\nUser: {user_input}\nAI:"
    else:
        context = f"User: {user_input}\nAI:"

    # Generate response using the model with context
    try:
        response = model.generate_content(context)
        response_text = response.text
    except Exception as e:
        response_text = "The AI is unable to answer your question. Please ask another question."
    
    return response_text

# Display chat history
def display_chat_history():
    if st.session_state.chat_history:
        st.write("## Chat History")
        for chat in st.session_state.chat_history:
            st.markdown(f"<div class='message-user'><strong>You:</strong> {chat['user_input']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='message-ai'><strong>AI:</strong> {chat['response']}</div>", unsafe_allow_html=True)

# Function to send email
def send_email(to_email, subject, body):
    from_email = os.getenv('EMAIL_USER')
    from_password = os.getenv('EMAIL_PASSWORD') # Use an app password or OAuth2 token

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, from_password)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

# Function for the login page
def login_page():
    st.title("Login")
    with st.form(key='login_form'):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.form_submit_button(label="Login")

        if login_button:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, hashed_password))
            if cursor.fetchone():
                st.session_state.authenticated = True
                st.session_state.username = username
                st.experimental_rerun()
            else:
                st.error("Invalid username or password")
            cursor.close()
            conn.close()

    # Forgot Password link
    if st.button("Forgot Password"):
        st.session_state.page = "Forgot Password"
        st.experimental_rerun()

    # Forgot Username link
    if st.button("Forgot Username"):
        st.session_state.page = "Forgot Username"
        st.experimental_rerun()

# Function for the registration page
def registration_page():
    st.title("Register")
    with st.form(key='registration_form'):
        email = st.text_input("Enter your Email")
        username = st.text_input("Choose a Username")
        password = st.text_input("Choose a Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        register_button = st.form_submit_button(label="Register")

        if register_button:
            if password != confirm_password:
                st.error("Passwords do not match")
            else:
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                conn = create_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute('INSERT INTO users (email, username, password) VALUES (%s, %s, %s)', (email, username, hashed_password))
                    conn.commit()
                    st.success("Registration successful! Please log in.")
                except mysql.connector.Error as err:
                    if "Duplicate entry" in str(err):
                        st.error("Email or Username already exists")
                cursor.close()
                conn.close()

# Function for the forgot password page
def forgot_password_page():
    st.title("Forgot Password")
    with st.form(key='forgot_password_form'):
        email = st.text_input("Enter your registered Email")
        submit_button = st.form_submit_button(label="Submit")

        if submit_button:
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT email FROM users WHERE email = %s', (email,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()

            if result:
                st.session_state.page = "Reset Password"
                st.session_state.email = email
                st.experimental_rerun()
            else:
                st.error("Email not found in the database.")

# Function for the forgot username page
def forgot_username_page():
    st.title("Forgot Username")
    with st.form(key='forgot_username_form'):
        email = st.text_input("Enter your registered Email")
        submit_button = st.form_submit_button(label="Submit")

        if submit_button:
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT username FROM users WHERE email = %s', (email,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()

            if result:
                username = result[0]
                subject = "Your Username"
                body = f"Hi,\n\nYour username is: {username}"
                if send_email(email, subject, body):
                    st.success("Your username has been sent to your email.")
                else:
                    st.error("Failed to send email. Please try again later.")
            else:
                st.error("Email not found in the database.")

# Function for the reset password page
def reset_password_page():
    email = st.session_state.email if 'email' in st.session_state else None

    if not email:
        st.error("Invalid request. Please request a password reset again.")
        return

    with st.form(key='reset_password_form'):
        new_password = st.text_input("Enter new password", type="password")
        confirm_password = st.text_input("Confirm new password", type="password")
        submit_button = st.form_submit_button(label="Reset Password")

        if submit_button:
            if new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
                conn = create_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET password = %s WHERE email = %s', (hashed_password, email))
                conn.commit()
                cursor.close()
                conn.close()
                st.success("Password reset successfully. You can now log in with your new password.")
                st.session_state.page = "Login"
                st.experimental_rerun()

# Function for the chatbot page
def chatbot_page():
    st.title(f"Welcome, {st.session_state.username}")
    st.title("MY Generative AI")

    # Display chat history
    display_chat_history()

    st.write("## New Chat")

    # Form to input and submit user question
    with st.form(key='input_form', clear_on_submit=True):
        user_input = st.text_input("Enter your question:", key="user_input")
        submit_button = st.form_submit_button(label="Submit")

        if submit_button and user_input:
            # Check for rule violations
            if check_for_violations(user_input):
                st.error("Your input violates the rules. Please try again with appropriate content.")
            else:
                # Generate content with context
                response_text = generate_response_with_context(user_input)

                # Add to chat history
                add_to_chat_history(user_input, response_text)

                # Rerun to update the chat history
                st.experimental_rerun()

    # Option to start a new chat
    if st.button("New Chat"):
        st.session_state.chat_history = []
        st.experimental_rerun()

    # Logout button
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.session_state.email = ""
        st.experimental_rerun()

# Initialize the database
init_db()

# Main app logic
if st.session_state.authenticated:
    chatbot_page()
else:
    if 'page' not in st.session_state:
        st.session_state.page = "Login"

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Login", "Register", "Forgot Password", "Forgot Username", "Reset Password"], index=["Login", "Register", "Forgot Password", "Forgot Username", "Reset Password"].index(st.session_state.page))

    if page == "Login":
        login_page()
    elif page == "Register":
        registration_page()
    elif page == "Forgot Password":
        forgot_password_page()
    elif page == "Forgot Username":
        forgot_username_page()
    elif page == "Reset Password":
        reset_password_page()
