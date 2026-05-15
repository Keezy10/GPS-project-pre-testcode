import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- ⚠️ [필수 입력] 설정 확인 ---
SMTP_SERVER = "smtp.gmail.com"  # 1. 'gmail.com'이 아니라 'smtp.gmail.com'이어야 합니다.
SMTP_PORT = 465                 # 2. 포트를 465(SSL 전용)로 변경하여 테스트합니다.
SENDER_EMAIL = "gps.signal.monitoring@gmail.com"
SENDER_PASSWORD = "wwbvkontourorttu"
RECEIVER_EMAIL = "philjin.kang@lge.com"

def test_email_with_debug():
    print("📬 구글 SMTP 서버 연결을 시도합니다...")
    
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = "[테스트] 465 포트 메일 연동 시험"
        msg.attach(MIMEText("465 SSL 포트를 통해 발송에 성공했습니다!", 'plain'))
        
        # SMTP_SSL을 사용하여 465 포트로 바로 보안 연결을 수립합니다.
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10)
        
        # 서버와 주고받는 모든 메시지를 터미널에 강제로 출력합니다.
        server.set_debuglevel(1) 
        
        print("🔑 구글 서버 로그인 중...")
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        print("🚀 메일 전송 중...")
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        
        print("\n✅ [성공] 메일이 정상 발송되었습니다!")
        
    except Exception as e:
        print(f"\n❌ [실패] 에러 발생 -> {e}")

if __name__ == "__main__":
    test_email_with_debug()
