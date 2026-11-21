import random
import logging
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import EmailOTP, Notification

logger = logging.getLogger(__name__)

def generate_otp_code(length=6) -> str:
    """Generate a secure 6-digit numeric OTP."""
    return f"{random.randint(100000, 999999)}"

def send_otp_email(email: str, purpose: str = 'login') -> dict:
    """
    Creates an OTP entry valid for 10 minutes and emails it to the user.
    """
    otp = generate_otp_code()
    expires_at = timezone.now() + timedelta(minutes=10)

    # Invalidate previous unused OTPs for the same email and purpose
    EmailOTP.objects.filter(email=email, purpose=purpose, is_used=False).update(is_used=True)

    # Create new OTP record
    EmailOTP.objects.create(
        email=email,
        otp=otp,
        purpose=purpose,
        expires_at=expires_at
    )

    subject_map = {
        'signup': 'JanSahayak AI — Verify Your Email Address',
        'login': 'JanSahayak AI — Your Secure Login OTP',
        'reset_password': 'JanSahayak AI — Password Reset OTP',
    }
    subject = subject_map.get(purpose, 'JanSahayak AI — Verification Code')

    message = (
        f"Namaste / Hello,\n\n"
        f"Your One-Time Password (OTP) for JanSahayak AI ({purpose.replace('_', ' ').title()}) is:\n\n"
        f"    {otp}\n\n"
        f"This code will expire in 10 minutes. Please do not share this OTP with anyone.\n\n"
        f"Warm regards,\n"
        f"JanSahayak AI Team\n"
        f"From Voice to Resolution"
    )

    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px; border: 1px solid #e5e7eb; border-radius: 12px; background-color: #ffffff;">
        <div style="text-align: center; margin-bottom: 20px;">
            <div style="display: inline-block; background-color: #A94D37; color: white; padding: 10px 18px; border-radius: 8px; font-weight: bold; font-size: 20px; letter-spacing: 1px;">
                JanSahayak AI
            </div>
            <p style="color: #6b7280; font-size: 13px; margin-top: 6px;">From Voice to Resolution</p>
        </div>
        <div style="padding: 16px 0; color: #1f2937;">
            <p style="font-size: 15px; line-height: 1.5;">Hello,</p>
            <p style="font-size: 15px; line-height: 1.5;">Here is your verification OTP code for <strong>{purpose.replace('_', ' ').title()}</strong>:</p>
            <div style="text-align: center; margin: 24px 0;">
                <span style="display: inline-block; font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #A94D37; background: #fbf5f4; padding: 12px 28px; border-radius: 8px; border: 1px dashed #A94D37;">
                    {otp}
                </span>
            </div>
            <p style="font-size: 13px; color: #6b7280; text-align: center;">This OTP is valid for <strong>10 minutes</strong>. Do not share this code with anyone.</p>
        </div>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;" />
        <p style="font-size: 11px; color: #9ca3af; text-align: center;">
            This is an automated notification from JanSahayak AI. If you did not request this OTP, please disregard this email.
        </p>
    </div>
    """

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        return {"success": True, "message": "OTP sent successfully to email"}
    except Exception as e:
        logger.error(f"Failed to send OTP to {email}: {e}")
        return {"success": False, "error": str(e)}

def verify_otp_code(email: str, otp: str, purpose: str = 'login') -> bool:
    """Verify if the OTP is correct, unexpired, and unused."""
    try:
        record = EmailOTP.objects.filter(
            email=email,
            otp=otp.strip(),
            purpose=purpose,
            is_used=False
        ).latest('created_at')

        if record.is_valid():
            record.is_used = True
            record.save()
            return True
        return False
    except EmailOTP.DoesNotExist:
        return False

def notify_user_via_email(user, title: str, message: str, complaint=None):
    """
    Creates an in-app Notification record AND dispatches an email via SMTP.
    """
    # 1. Create in-app notification
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        complaint=complaint,
        notification_type='status_update'
    )

    # 2. Dispatch email if user has a valid email
    if user.email:
        try:
            subject = f"JanSahayak AI Alert: {title}"
            body = (
                f"Namaste {user.get_full_name() or user.username},\n\n"
                f"{message}\n\n"
                f"{f'Tracking ID: {complaint.tracking_id}' if complaint else ''}\n\n"
                f"You can view live status updates at your JanSahayak portal.\n\n"
                f"Warm regards,\n"
                f"JanSahayak AI Civic Platform"
            )
            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px; border: 1px solid #e5e7eb; border-radius: 12px; background-color: #ffffff;">
                <div style="text-align: center; margin-bottom: 20px;">
                    <div style="display: inline-block; background-color: #A94D37; color: white; padding: 8px 16px; border-radius: 8px; font-weight: bold; font-size: 18px;">
                        JanSahayak AI
                    </div>
                </div>
                <h2 style="color: #17191D; font-size: 18px; margin-top: 0;">{title}</h2>
                <p style="color: #374151; font-size: 14px; line-height: 1.6;">{message}</p>
                {f'<p style="background: #f3f4f6; padding: 8px 12px; border-radius: 6px; font-family: monospace; font-size: 13px;">Ticket: <strong>{complaint.tracking_id}</strong></p>' if complaint else ''}
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;" />
                <p style="font-size: 11px; color: #9ca3af; text-align: center;">JanSahayak AI — Autonomous Multilingual Complaint Management Platform</p>
            </div>
            """
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_body,
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Error sending email notification to {user.email}: {e}")

    return notification
