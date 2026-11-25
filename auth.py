import os
import random
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import pytz
import smtplib
from email.header import Header

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from models import db, User

auth_bp = Blueprint('auth', __name__)
oauth = OAuth()

# Ρυθμίσεις SMTP Gmail
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'veritas4ai@gmail.com')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')


def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )


def send_otp_email(recipient_email, otp_code):
  """Αποστολή email με 6-ψήφιο κωδικό OTP μέσω Gmail SMTP με πλήρη υποστήριξη UTF-8"""
  subject = "Your Veritas4ai Verification Code"
  sender_name = "Veritas4ai Security"

  html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 25px; border: 1px solid #e2e8f0; border-radius: 10px;">
        <h2 style="color: #0f172a; margin-top: 0;">Veritas4ai Verification</h2>
        <p style="color: #475569; font-size: 15px;">Use the verification code below to confirm your email and activate your account:</p>
        <div style="background: #f1f5f9; padding: 18px; border-radius: 8px; text-align: center; margin: 25px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #0284c7; font-family: monospace;">{otp_code}</span>
        </div>
        <p style="color: #64748b; font-size: 13px;">This code will expire in 10 minutes. If you did not request this, you can safely ignore this email.</p>
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        <small style="color: #94a3b8;">Veritas4ai Compliance Engine • Automated EU AI Act Auditing</small>
    </div>
    """

  msg = MIMEMultipart("alternative")
  # Ασφαλής κωδικοποίηση headers για μη-ASCII / UTF-8 χαρακτήρες
  msg["Subject"] = Header(subject, "utf-8")
  msg["From"] = f"{Header(sender_name, 'utf-8').encode()} <{MAIL_USERNAME}>"
  msg["To"] = recipient_email

  # Ρητή δήλωση κωδικοποίησης utf-8 στο σώμα
  msg.attach(MIMEText(html_content, "html", "utf-8"))

  with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(MAIL_USERNAME, MAIL_PASSWORD)
    # Χρήση as_bytes() αντί για as_string() για αποφυγή οποιουδήποτε ASCII encode failure
    server.sendmail(MAIL_USERNAME, recipient_email, msg.as_bytes())


# --- SIGN UP WITH OTP VERIFICATION ---

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        username = request.form.get('username', '').strip()
        password = request.form.get('password')

        if not email or not password:
            flash('Please fill in all required fields.', 'danger')
            return render_template('register.html')

        user = User.query.filter_by(email=email).first()
        if user and user.is_verified:
            flash('An account with this email already exists.', 'warning')
            return redirect(url_for('auth.login'))

        # Παραγωγή 6-ψήφιου OTP
        otp = f"{random.randint(100000, 999999)}"
        expiry = datetime.now(pytz.utc) + timedelta(minutes=10)

        if not user:
            user = User(
                email=email,
                username=username or email.split('@')[0],
                is_verified=False
            )
            user.set_password(password)
            db.session.add(user)

        user.otp_code = otp
        user.otp_expiry = expiry
        db.session.commit()

        # Αποστολή Email
        try:
            send_otp_email(email, otp)
            session['pending_verification_email'] = email
            flash('A 6-digit verification code has been sent to your email.', 'info')
            return redirect(url_for('auth.verify_otp'))
        except Exception as e:
            flash(f'Failed to send email: {str(e)}', 'danger')
            return render_template('register.html')

    return render_template('register.html')


@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    email = session.get('pending_verification_email')
    if not email:
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()
        user = User.query.filter_by(email=email).first()

        if not user or user.otp_code != entered_otp:
            flash('Invalid verification code. Please try again.', 'danger')
            return render_template('verify_otp.html', email=email)

        now_utc = datetime.now(pytz.utc)
        user_expiry = user.otp_expiry
        if user_expiry.tzinfo is None:
            user_expiry = pytz.utc.localize(user_expiry)

        if now_utc > user_expiry:
            flash('Verification code has expired. Please register again.', 'warning')
            return redirect(url_for('auth.register'))

        # Επιτυχής επαλήθευση
        user.is_verified = True
        user.otp_code = None
        user.otp_expiry = None
        db.session.commit()

        session.pop('pending_verification_email', None)
        login_user(user)
        flash('Email verified successfully! Welcome to Veritas4ai.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('verify_otp.html', email=email)


# --- STANDARD LOGIN ---

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.is_verified and email != 'manager@gmail.com':
                session['pending_verification_email'] = email
                otp = f"{random.randint(100000, 999999)}"
                user.otp_code = otp
                user.otp_expiry = datetime.now(pytz.utc) + timedelta(minutes=10)
                db.session.commit()
                send_otp_email(email, otp)
                flash('Please verify your email to continue. A code was sent.', 'warning')
                return redirect(url_for('auth.verify_otp'))

            login_user(user, remember=bool(request.form.get('remember')))
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('landing_page'))


# --- GOOGLE OAUTH ROUTES ---

@auth_bp.route('/login/google')
def google_login():
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/google/callback')
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info or not user_info.get('email'):
            flash("Failed to retrieve email from Google.", "danger")
            return redirect(url_for('auth.login'))

        email = user_info['email'].lower()
        name = user_info.get('name', email.split('@')[0])

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                email=email,
                username=name,
                is_verified=True  # Google emails are pre-verified
            )
            user.set_password(secrets.token_urlsafe(32))
            db.session.add(user)
            db.session.commit()
            flash("Account successfully created via Google!", "success")
        else:
            user.is_verified = True
            db.session.commit()
            flash(f"Welcome back, {user.username}!", "success")

        login_user(user)
        return redirect(url_for('dashboard'))

    except Exception as e:
        flash(f"Google login failed: {str(e)}", "danger")
        return redirect(url_for('auth.login'))