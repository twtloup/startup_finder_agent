"""
Email Sender for Venture Funding Monitor
Generates and sends HTML email digests via Gmail SMTP.
"""

import logging
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict
from jinja2 import Template, Environment, FileSystemLoader

from src import config

# Set up logging
logger = logging.getLogger(__name__)


class EmailSender:
    """
    Generates and sends email digests with funding announcements.

    Uses:
    - Jinja2 for HTML templating
    - smtplib for Gmail SMTP
    - MIME multipart for HTML + plain text emails

    Why Gmail SMTP?
    - Free and reliable
    - Easy to set up with app passwords
    - Works with standard SMTP protocol
    """

    def __init__(self, template_dir: str = 'templates'):
        """
        Initialize email sender with template configuration.

        Args:
            template_dir: Directory containing email templates
        """
        self.template_dir = template_dir

        # Set up Jinja2 template environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True  # Prevent XSS in email content
        )

        # Verify email configuration
        if not config.GMAIL_ADDRESS or not config.GMAIL_APP_PASSWORD:
            logger.error("Email credentials not configured. Check .env file.")
            raise ValueError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set in .env")

    def send_digest(
        self,
        announcements: List[Dict],
        digest_type: str = 'daily'
    ) -> bool:
        """
        Generate and send an email digest with funding announcements.

        Args:
            announcements: List of funding announcement dictionaries
            digest_type: 'daily' or 'weekly'

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Generate email content
            subject = self._generate_subject(len(announcements), digest_type)
            html_content = self._generate_html(announcements, digest_type)
            plain_content = self._generate_plain_text(announcements, digest_type)

            # Send email
            success = self._send_email(subject, html_content, plain_content)

            if success:
                logger.info(f"Successfully sent {digest_type} digest with {len(announcements)} announcements")
            else:
                logger.error(f"Failed to send {digest_type} digest")

            return success

        except Exception as e:
            logger.error(f"Error sending digest: {e}")
            # Save backup in case of failure
            self._save_backup(html_content, digest_type)
            return False

    def _generate_subject(self, count: int, digest_type: str) -> str:
        """
        Generate email subject line.

        Args:
            count: Number of funding announcements
            digest_type: 'daily' or 'weekly'

        Returns:
            Subject line string
        """
        date_str = datetime.now().strftime('%Y-%m-%d')

        if digest_type == 'weekly':
            return config.EMAIL_SUBJECT_WEEKLY.format(count=count, date=date_str)
        else:
            return config.EMAIL_SUBJECT_DAILY.format(count=count, date=date_str)

    def _generate_html(
        self,
        announcements: List[Dict],
        digest_type: str
    ) -> str:
        """
        Generate HTML email content from template.

        Args:
            announcements: List of funding announcement dictionaries
            digest_type: 'daily' or 'weekly'

        Returns:
            HTML string
        """
        # Load template
        template = self.jinja_env.get_template('email_digest.html')

        # Prepare template variables
        days = 7 if digest_type == 'weekly' else 1
        date_str = datetime.now().strftime('%B %d, %Y')
        generation_time = datetime.now().strftime('%Y-%m-%d %H:%M UTC')

        # Render template
        html_content = template.render(
            announcements=announcements,
            total_companies=len(announcements),
            days=days,
            date=date_str,
            generation_time=generation_time,
            feed_count=len(config.RSS_FEEDS)
        )

        return html_content

    def _generate_plain_text(
        self,
        announcements: List[Dict],
        digest_type: str
    ) -> str:
        """
        Generate plain text email content as fallback.

        Some email clients don't support HTML, so we provide
        a plain text version as well.

        Args:
            announcements: List of funding announcement dictionaries
            digest_type: 'daily' or 'weekly'

        Returns:
            Plain text string
        """
        days = 7 if digest_type == 'weekly' else 1
        date_str = datetime.now().strftime('%B %d, %Y')

        lines = [
            f"Venture Funding Digest - {date_str}",
            "=" * 60,
            "",
            f"{len(announcements)} new funding announcement(s) in the last {days} day(s)",
            "Geographic Focus: UK, Europe & Middle East",
            "Stages: Seed to Series C | Priority: Fintech & SaaS",
            "",
            "=" * 60,
            ""
        ]

        if announcements:
            for i, announcement in enumerate(announcements, 1):
                lines.extend([
                    f"{i}. {announcement['company_name']}",
                    f"   Stage: {announcement['funding_stage']}",
                    f"   Amount: {announcement['funding_amount']}",
                    f"   Location: {announcement['location']}",
                    f"   Industry: {announcement['industry']}",
                    f"   Description: {announcement['description'][:200]}...",
                    f"   Read more: {announcement['url']}",
                    ""
                ])
        else:
            lines.append("No new funding announcements matching your criteria were found in this period.")
            lines.append("")

        lines.extend([
            "=" * 60,
            "Generated automatically by your Venture Funding Monitor",
            "Sources: TechCrunch, Sifted, VentureBeat, Crunchbase News",
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
        ])

        return "\n".join(lines)

    def _send_email(
        self,
        subject: str,
        html_content: str,
        plain_content: str
    ) -> bool:
        """
        Send email via Gmail SMTP.

        Args:
            subject: Email subject line
            html_content: HTML email body
            plain_content: Plain text email body

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create multipart message (supports both HTML and plain text)
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = config.GMAIL_ADDRESS
            message['To'] = config.RECIPIENT_EMAIL

            # Attach plain text and HTML parts
            # Email clients will try to render HTML first, fall back to plain text
            plain_part = MIMEText(plain_content, 'plain')
            html_part = MIMEText(html_content, 'html')

            message.attach(plain_part)
            message.attach(html_part)

            # Connect to Gmail SMTP server
            logger.info(f"Connecting to Gmail SMTP: {config.SMTP_SERVER}:{config.SMTP_PORT}")

            with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
                # Enable TLS encryption
                server.starttls()

                # Login with app password
                server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)

                # Send email
                server.send_message(message)

            logger.info(f"Email sent successfully to {config.RECIPIENT_EMAIL}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            logger.error("Check your Gmail address and app password in .env file")
            return False

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False

    def _save_backup(self, html_content: str, digest_type: str):
        """
        Save email HTML to backup file in case of sending failure.

        This allows manual recovery if email sending fails.

        Args:
            html_content: HTML email content
            digest_type: 'daily' or 'weekly'
        """
        try:
            # Create backup directory
            backup_dir = 'backup_digests'
            os.makedirs(backup_dir, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            filename = f"{digest_type}_digest_{timestamp}.html"
            filepath = os.path.join(backup_dir, filename)

            # Write HTML to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(f"Saved backup digest to {filepath}")

        except Exception as e:
            logger.error(f"Failed to save backup: {e}")


# Example usage and testing
if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test email sender with sample data
    sender = EmailSender()

    # Sample funding announcements
    sample_announcements = [
        {
            'company_name': 'Acme Fintech',
            'funding_stage': 'Series A',
            'funding_amount': '$10M',
            'location': 'London',
            'industry': 'Fintech',
            'description': 'Acme Fintech, a London-based digital banking startup, has raised $10 million in Series A funding to expand its services across Europe.',
            'url': 'https://example.com/article1',
            'title': 'Acme Fintech raises $10M Series A',
            'source': 'TechCrunch'
        },
        {
            'company_name': 'TechCorp SaaS',
            'funding_stage': 'Series B',
            'funding_amount': '$25M',
            'location': 'Dubai',
            'industry': 'SaaS',
            'description': 'TechCorp SaaS, a Dubai-based B2B software company, has closed a $25 million Series B round to fuel its growth in the Middle East market.',
            'url': 'https://example.com/article2',
            'title': 'TechCorp SaaS secures $25M Series B',
            'source': 'VentureBeat'
        }
    ]

    # Generate HTML preview (don't send)
    html_content = sender._generate_html(sample_announcements, 'daily')
    print("HTML Email Preview:")
    print("=" * 60)
    print(html_content[:500])
    print("...")
    print("=" * 60)

    # Note: To actually send the email, you would call:
    # success = sender.send_digest(sample_announcements, 'daily')
    # But this requires valid .env configuration

    print("\nTo send actual emails, configure your .env file with:")
    print("- GMAIL_ADDRESS")
    print("- GMAIL_APP_PASSWORD")
    print("- RECIPIENT_EMAIL")
