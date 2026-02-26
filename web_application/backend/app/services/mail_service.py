import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from ..core.config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, 
    EMAIL_FROM, FRONTEND_URL, PROJECT_NAME
)

logger = logging.getLogger("app.services.mail_service")

class MailService:
    @staticmethod
    def send_verification_email(email: str, token: str):
        verification_link = f"{FRONTEND_URL}/verify-email?token={token}"
        
        subject = f"Verify your email for {PROJECT_NAME}"
        body = f"""
        <html>
            <body>
                <h2>Welcome to {PROJECT_NAME}!</h2>
                <p>Please click the link below to verify your email address:</p>
                <p><a href="{verification_link}">{verification_link}</a></p>
                <p>This link will expire in 24 hours.</p>
                <p>If you did not create an account, please ignore this email.</p>
            </body>
        </html>
        """
        
        # If SMTP is not configured, just log it
        if not SMTP_HOST:
            logger.info("=" * 50)
            logger.info(f"EMAIL VERIFICATION TO: {email}")
            logger.info(f"SUBJECT: {subject}")
            logger.info(f"VERIFICATION LINK: {verification_link}")
            logger.info("=" * 50)
            return True

        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_FROM
            msg['To'] = email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html'))
            
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Sent verification email to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {email}: {str(e)}")
            return False

mail_service = MailService()
