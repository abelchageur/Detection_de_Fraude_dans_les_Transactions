import smtplib

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "mabelchaguer@gmail.com"
EMAIL_PASS = "xgoo%20lpbi%20dboi%20tuqa"  # Your Google App Password

try:
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(EMAIL_USER, EMAIL_PASS)
    print("✅ SMTP authentication successful!")
    server.quit()
except Exception as e:
    print("❌ SMTP authentication failed:", e)

