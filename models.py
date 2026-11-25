# models.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    # OTP & Email Verification Fields
    is_verified = db.Column(db.Boolean, default=False)
    otp_code = db.Column(db.String(6), nullable=True)
    otp_expiry = db.Column(db.DateTime, nullable=True)

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Free plan: 1 για κάθε μέγεθος (Short, Standard, Long)
    free_short_used = db.Column(db.Boolean, default=False)
    free_standard_used = db.Column(db.Boolean, default=False)
    free_long_used = db.Column(db.Boolean, default=False)

    # Συνδρομή ή πληρωμένα credits
    is_subscribed = db.Column(db.Boolean, default=False)
    paid_credits = db.Column(db.Integer, default=0)

    assessments = db.relationship('AssessmentHistory', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def can_run_report(self, report_type):
        """Ελέγχει αν ο χρήστης δικαιούται να εκτελέσει το συγκεκριμένο μέγεθος report."""
        if self.is_subscribed:
            return True, "Subscribed active plan"
        if self.paid_credits > 0:
            return True, f"Paid credits remaining: {self.paid_credits}"

        rep = (report_type or "short").lower()
        if rep == "short" and not self.free_short_used:
            return True, "Free Short Assessment available"
        elif rep == "standard" and not self.free_standard_used:
            return True, "Free Standard Assessment available"
        elif rep == "long" and not self.free_long_used:
            return True, "Free Long Assessment available"

        return False, f"Έχετε ήδη εξαντλήσει το δωρεάν {rep.capitalize()} Assessment. Απαιτείται αναβάθμιση ή αγορά credits."

    def use_report_credit(self, report_type):
        """Χρεώνει το free quota ή αφαιρεί ένα credit."""
        if self.is_subscribed:
            return
        rep = (report_type or "short").lower()
        if rep == "short" and not self.free_short_used:
            self.free_short_used = True
        elif rep == "standard" and not self.free_standard_used:
            self.free_standard_used = True
        elif rep == "long" and not self.free_long_used:
            self.free_long_used = True
        elif self.paid_credits > 0:
            self.paid_credits -= 1
        db.session.commit()


class AssessmentHistory(db.Model):
    __tablename__ = 'assessment_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    job_id = db.Column(db.String(100), index=True, nullable=False)
    system_name = db.Column(db.String(200), default="AI System")
    report_type = db.Column(db.String(50), default="short")
    download_name = db.Column(db.String(250), nullable=True)
    pdf_path = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)