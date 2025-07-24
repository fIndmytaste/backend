# email_service.py

import threading
from typing import Dict, List, Optional, Union
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


class EmailService:
    """
    A service class for sending different types of emails based on templates.
    Handles template rendering, email construction, and asynchronous sending.
    """

    def __init__(self, default_from_email=None):
        """Initialize the email service with optional default sender email"""
        self.default_from_email = default_from_email or settings.DEFAULT_FROM_EMAIL

    def _send_email(
        self,
        subject: str,
        body: str,
        to_emails: Union[str, List[str]],
        html_content: Optional[str] = None,
        from_email: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[List[str]] = None,
        attachments: Optional[List[Dict]] = None,
    ) -> bool:
        """
        Internal method to send an email

        Args:
            subject: Email subject
            body: Plain text content
            to_emails: Single email address or list of email addresses
            html_content: Optional HTML content
            from_email: Sender email address
            cc: List of CC email addresses
            bcc: List of BCC email addresses
            reply_to: List of Reply-To email addresses
            attachments: List of attachment dictionaries with {filename, content, mimetype}

        Returns:
            bool: True if sent successfully
        """
        # Convert single email to list
        if isinstance(to_emails, str):
            to_emails = [to_emails]

        # Use default from_email if not specified
        from_email = from_email or self.default_from_email

        # Create email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_email,
            to=to_emails,
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
        )

        # Add HTML content if provided
        if html_content:
            email.attach_alternative(html_content, "text/html")

        # Add attachments if provided
        if attachments:
            for attachment in attachments:
                email.attach(
                    attachment["filename"],
                    attachment["content"],
                    attachment.get("mimetype"),
                )

        # Send the email
        try:
            email.send(fail_silently=False)
            return True
        except Exception as e:
            # In a production app, you would log this error
            print(f"Failed to send email: {str(e)}")
            return False

    def send_email_with_template(
        self,
        email: Union[str, List[str]],
        template_name: str,
        template_data: Dict,
        subject: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[List[str]] = None,
        from_email: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
        async_send: bool = True,
    ) -> bool:
        """
        Send an email using a template

        Args:
            email: Recipient email address(es)
            template_name: Path to the HTML template
            template_data: Context data for the template
            subject: Email subject
            cc: List of CC email addresses
            bcc: List of BCC email addresses
            reply_to: List of Reply-To email addresses
            from_email: Sender email address
            attachments: List of attachment dictionaries
            async_send: Whether to send the email asynchronously

        Returns:
            bool: True if the email was sent (or scheduled to be sent) successfully
        """
        from_email = 'support@findmytaste.com.ng'
        # Render HTML template
        html_content = render_to_string(template_name, template_data)
        
        # Create plain text version
        plain_text = strip_tags(html_content)

        # Send email synchronously or asynchronously
        if async_send:
            thread = threading.Thread(
                target=self._send_email,
                kwargs={
                    "subject": subject,
                    "body": plain_text,
                    "to_emails": email,
                    "html_content": html_content,
                    "from_email": from_email,
                    "cc": cc,
                    "bcc": bcc,
                    "reply_to": reply_to,
                    "attachments": attachments,
                },
            )
            thread.daemon = True  # Allows the program to exit without waiting for the thread
            thread.start()
            return True
        else:
            return self._send_email(
                subject=subject,
                body=plain_text,
                to_emails=email,
                html_content=html_content,
                from_email=from_email,
                cc=cc,
                bcc=bcc,
                reply_to=reply_to,
                attachments=attachments,
            )

    # Specialized methods for common email types

    def send_welcome_email(self, user_email, user_name):
        """Send a welcome email to a new user"""
        return self.send_email_with_template(
            email=user_email,
            template_name="emails/account_login.html",
            template_data={"user_name": user_name},
            subject="Welcome to Our Platform",
        )

    def send_password_reset_email(self, user_email, reset_link, user_name=None):
        """Send a password reset email"""
        return self.send_email_with_template(
            email=user_email,
            template_name="emails/password_reset.html",
            template_data={
                "reset_link": reset_link,
                "user_name": user_name,
            },
            subject="Password Reset Request",
        )

    def send_order_confirmation(self, user_email, order_details, user_name=None):
        """Send an order confirmation email"""
        return self.send_email_with_template(
            email=user_email,
            template_name="emails/order_confirmation.html",
            template_data={
                "user_name": user_name,
                "order_details": order_details,
            },
            subject="Your Order Confirmation",
        )
    

    def send_verification_code(self, user_email, user_name, verification_code):
        """Send account activation code to a user"""
        return self.send_email_with_template(
            email=user_email,
            template_name="emails/account_activation.html",
            template_data={
                "user_name": user_name,
                "verification_code": verification_code,
                "expiry_time": "24 hours", 
                "app_name": settings.APP_NAME if hasattr(settings, 'APP_NAME') else "Our App",
            },
            subject="Verify Your Account",
        )


    def send_login_verification_code(self, user_email, user_name, verification_code):
        """Send account activation code to a user"""
        return self.send_email_with_template(
            email=user_email,
            template_name="emails/account_login.html",
            template_data={
                "user_name": user_name,
                "otp_code": verification_code,
                "expiry_time": "24 hours", 
                "app_name": settings.APP_NAME if hasattr(settings, 'APP_NAME') else "Our App",
            },
            subject="Verify Your Account",
        )


emailService = EmailService()
# emailService.send_welcome_email(
#     user_email="olakaycoder1@gmail.com",
#     user_name="John Doe",
# )





