import os
from datetime import datetime, timedelta
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@hospital.com")


async def send_email(recipient: str, subject: str, html_content: str) -> bool:
    """Send email via SMTP."""
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured, skipping email send")
        return False

    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = SMTP_FROM_EMAIL
        message["To"] = recipient

        html_part = MIMEText(html_content, "html")
        message.attach(html_part)

        async with aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT) as smtp:
            await smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            await smtp.sendmail(SMTP_FROM_EMAIL, recipient, message.as_string())

        logger.info(f"Email sent to {recipient}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {recipient}: {str(e)}")
        return False


async def send_verification_email(email: str, verification_token: str, frontend_url: str = None) -> bool:
    """Send email verification link."""
    if frontend_url is None:
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

    verification_link = f"{frontend_url}/verify-email/{verification_token}"

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h2 style="color: #2563eb;">Verify Your Email</h2>
                <p style="color: #666; font-size: 16px;">Welcome to Smart Hospital! Please verify your email address to complete your registration.</p>

                <a href="{verification_link}" style="display: inline-block; margin-top: 20px; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 6px; font-weight: bold;">
                    Verify Email
                </a>

                <p style="color: #999; font-size: 14px; margin-top: 20px;">Or copy and paste this link in your browser:</p>
                <p style="color: #2563eb; word-break: break-all; font-size: 12px;">{verification_link}</p>

                <p style="color: #999; font-size: 12px; margin-top: 20px;">This link will expire in 24 hours.</p>
                <p style="color: #999; font-size: 12px;">If you didn't create this account, please ignore this email.</p>
            </div>
        </body>
    </html>
    """

    return await send_email(email, "Verify Your Email - Smart Hospital", html_content)


async def send_password_reset_email(email: str, reset_token: str, frontend_url: str = None) -> bool:
    """Send password reset link."""
    if frontend_url is None:
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

    reset_link = f"{frontend_url}/reset-password/{reset_token}"

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h2 style="color: #2563eb;">Reset Your Password</h2>
                <p style="color: #666; font-size: 16px;">We received a request to reset your password. Click the link below to proceed:</p>

                <a href="{reset_link}" style="display: inline-block; margin-top: 20px; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 6px; font-weight: bold;">
                    Reset Password
                </a>

                <p style="color: #999; font-size: 14px; margin-top: 20px;">Or copy and paste this link in your browser:</p>
                <p style="color: #2563eb; word-break: break-all; font-size: 12px;">{reset_link}</p>

                <p style="color: #999; font-size: 12px; margin-top: 20px;">This link will expire in 30 minutes.</p>
                <p style="color: #999; font-size: 12px;">If you didn't request a password reset, please ignore this email or contact support.</p>
            </div>
        </body>
    </html>
    """

    return await send_email(email, "Reset Your Password - Smart Hospital", html_content)
