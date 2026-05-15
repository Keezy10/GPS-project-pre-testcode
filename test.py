import paramiko
import time
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import threading
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 백그라운드 구동 시 그래프 팝업 창 에러 방지 설정
import matplotlib
matplotlib.use('Agg')

# =========================================================================
# [사용자 설정 영역] 본인의 서버 및 계정 정보에 맞게 수정해 주세요.
# =========================================================================
GNSS_SERVER = {'ip': '10.231.164.212', 'user': 'lgeadmin', 'pw': 'lge123!!'}
PING_SERVER = {'ip': '10.231.165.47', 'user': 'appserver', 'pw': 'lge123!!'}
TARGET_IP = '10.218.224.61'  # PING_SERVER에서 핑을 날릴 목적지

SMTP_SERVER = "gmail.com"
SMTP_PORT = 465
SENDER_EMAIL = "gps.signal.monitoring@gmail.com"
SENDER_PASSWORD = "wwbvkontourorttu"

#알람받을 사용자 메일주소
RECEIVER_EMAIL = "philjin.kang@lge.com"  

# 💡 [시험용 설정] 30초 간격 점검 세팅
INTERVAL_SECONDS = 30 
# =========================================================================

def send_alert_email_ssl(subject, body):
    """465 SSL 암호화 방식으로 백그라운드 비동기 경고 이메일을 발송합니다."""
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print(f"📧 알람 메일 발송 완료: {subject}")
    except Exception as e:
        print(f"❌ 알람 메일 발송 실패: {e}")

def get_gnss_data():
    """순차 구조로 안전하게 4초간 파일 저장 후 인출하며 첫 행 위성 진짜 시간을 기준으로 타임라인을 생성합니다."""
    records = []
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(GNSS_SERVER['ip'], username=GNSS_SERVER['user'], password=GNSS_SERVER['pw'])
        
        cmd = 'sudo -S timeout 4 cat /dev/gnss0 > /tmp/gnss_tmp.log 2>/dev/null && echo "DONE"'
        stdin, stdout, _ = ssh.exec_command(cmd)
        stdin.write(GNSS_SERVER['pw'] + '\n')
        stdin.flush()
        stdout.read() 
        
        _, stdout_read, _ = ssh.exec_command('cat /tmp/gnss_tmp.log && rm -f /tmp/gnss_tmp.log')
        raw_output = stdout_read.read().decode('utf-8', errors='ignore')
        
        base_time_obj = None
        row_counter = 0
        
        for line in raw_output.split('\n'):
            if '$GNGGA' in line:
                parts = line.split(',')
                if len(parts) > 7:
                    if base_time_obj is None:
                        raw_time = parts
                        if len(raw_time) >= 6:
                            hh = (int(raw_time[0:2]) + 9) % 24
                            mm = int(raw_time[2:4])
                            ss = int(raw_time[4:6])
                            base_time_obj = datetime.strptime(f"{hh:02d}:{mm:02d}:{ss:02d}", "%H:%M:%S")
                        else:
                            base_time_obj = datetime.now()
                    
                    current_time_obj = base_time_obj + timedelta(seconds=row_counter)
                    formatted_time = current_time_obj.strftime('%H:%M:%S')
                    row_counter += 1

                    fix_status = parts[6].strip()
                    sat_string = parts[7].strip()
                    sat_count = int(sat_string) if sat_string.isdigit() else 0
                    
                    records.append({'Time': formatted_time, 'Sat_Count': sat_count, 'Fix': fix_status})
    except Exception as e:
        print(f"❌ GNSS 통신 장애 에러: {e}")
    finally:
        ssh.close()
    return records

def get_ping_data():
    """독립 세션으로 핑을 정확히 3회 수행하여 레이턴시와 상태 수집"""
    records = []
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(PING_SERVER['ip'], username=PING_SERVER['user'], password=PING_SERVER['pw'])
        for _ in range(3):
            cmd = f"ping -c 1 {TARGET_IP} | grep 'time='"
            _, stdout, _ = ssh.exec_command(cmd)
            res = stdout.read().decode('utf-8')
            match = re.search(r"time=([\d.]+)\s*ms", res)
            
            if match:
                latency = float(match.group(1))
                status = "OK"
            else:
                latency = 0.0
                status = "Fail"
            
            records.append({'UE connection status': status, 'Latency_ms': latency})
            time.sleep(0.8)
    except Exception as e:
        print(f"❌ PING 통신 장애 에러: {e}")
    finally:
        ssh.close()
    return records

def classify_status(row):
    """실시간 수집된 단일 데이터 기반 2진 분류(0 or 1) 판단 조건식"""
    fix = str(row['Fix']).strip()
    sat = int(row['Sat_Count'])
    latency = float(row['Latency_ms'])
    
    if sat <= 4:
        return 0
    if fix != '0' and fix != '' and sat >= 6:
        return 1
    if fix != '0' and fix != '' and sat == 5:
        if latency >= 100.0:
            return 0
        else:
            return 1
            
    return 0

def save_and_generate_graph(current_df):
    """매월 데이터 파일을 자동 분리하여 적재하고 이중 Y축 추이 그래프를 갱신합니다."""
    current_month = datetime.now().strftime('%Y-%m')
    log_file = f'gnss_monitor_log_{current_month}.xlsx'
    graph_file = f'gnss_monitor_graph_{current_month}.png'
    
    try:
        with pd.ExcelWriter(log_file, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
            current_df.to_excel(writer, index=False, header=False, startrow=writer.sheets['Sheet1'].max_row)
    except (FileNotFoundError, KeyError):
        current_df.to_excel(log_file, index=False)
    
    try:
        full_df = pd.read_excel(log_file)
        full_df['Latency_ms'] = pd.to_numeric(full_df['Latency_ms'], errors='coerce').fillna(0.0)
        full_df['Sat_Count'] = pd.to_numeric(full_df['Sat_Count'], errors='coerce').fillna(0)
        full_df['Binary_Status'] = pd.to_numeric(full_df['Binary_Status'], errors='coerce').fillna(0)
        
        # 💡 [조건 4] 이진상태 결과값이 5연속 0점인지 판별
        if len(full_df) >= 5:
            last_5_status = full_df['Binary_Status'].tail(5).tolist()
            if last_5_status == [0, 0, 0, 0, 0]:
                current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                threading.Thread(target=send_alert_email_ssl, args=(
                    f"[임계치 경고] GPS 환경 점검 필요 ({current_timestamp})",
                    "현재 GPS 수신기의 환경 및 장비 점검이 필요할 것으로 보입니다"
                )).start()
                
        # 💡 [조건 5] 이번 달 누적 이진상태 결과값의 평균값이 0.2 이하인지 판별
        if len(full_df) >= 10: 
            monthly_average = full_df['Binary_Status'].mean()
            if monthly_average <= 0.2:
                current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                threading.Thread(target=send_alert_email_ssl, args=(
                    f"[월간 품질 경고] GPS 종합 평균 저하 ({current_timestamp})",
                    "현재 GPS 수신기의 환경 및 장비 점검이 필요할 것으로 보입니다"
                )).start()

        plot_df = full_df.tail(120)  
        fig, ax1 = plt.subplots(figsize=(14, 6))
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Satellite Count', color='tab:blue')
        ax1.plot(plot_df['Time'].astype(str), plot_df['Sat_Count'], color='tab:blue', marker='o', linestyle='-', label='Satellites')
        ax1.tick_params(axis='y', labelcolor='tab:blue')
        
        ax2 = ax1.twinx()
        ax2.set_ylabel('Latency (ms)', color='tab:red')
        ax2.plot(plot_df['Time'].astype(str), plot_df['Latency_ms'], color='tab:red', marker='x', linestyle='--', label='Latency')
        ax2.tick_params(axis='y', labelcolor='tab:red')
        
        plt.title(f'GNSS Status Dashboard ({current_month})')
        ax1.set_xticks(ax1.get_xticks()[::max(1, len(plot_df)//10)]) 
        fig.autofmt_xdate(rotation=45)
        fig.tight_layout()
        
        plt.savefig(graph_file)
        plt.close(fig)
        print(f"📊 월별 그래프 이미지 최신화 완료: {graph_file}")
    except Exception as e:
        print(f"⚠️ 그래프 생성 및 예외 통계 처리 중 에러: {e}")

def monitor_interval():
    print("🔗 양쪽 서버 안전 순차적 수집 기동...")
    now_time = datetime.now().strftime('%H:%M:%S')
    
    gnss_res = get_gnss_data()
    ping_res = get_ping_data()
    
    if not gnss_res or not ping_res:
        print("⚠️ 이번 주기 데이터 획득 부족으로 수집을 스킵합니다.")
        return
        
    df_gnss = pd.DataFrame(gnss_res)
    df_ping = pd.DataFrame(ping_res)
    
    final_df = pd.merge(df_gnss, df_ping, left_index=True, right_index=True)
    final_df = final_df.head(3) 
    
    final_df = final_df[['Time', 'Sat_Count', 'Fix', 'UE connection status', 'Latency_ms']]
    
    if len(final_df) < 3:
        print(f"⚠️ 데이터 개수가 부족합니다. (확보 수: {len(final_df)}개)")
        return
        
    # 💡 [신규 행] 이진상태 결과값 판별 처리 
    final_df['Binary_Status'] = final_df.apply(classify_status, axis=1)
    
    print(f"✅ 동기화 정렬 성공 (추출 데이터 수: {len(final_df)}개)")
    print(final_df.to_string(index=False))
    
    threading.Thread(target=save_and_generate_graph, args=(final_df,)).start()
    
    # 💡 [조건 6] 위성 Fix 안됨 시 가동되는 홀도버 예고 경고 메일링
    has_loss_alert = (final_df['Fix'].astype(str) == '0').any() or (final_df['Fix'].astype(str) == '').any()
    
    current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if has_loss_alert:
        alert_body = (
            "현재 장비에서 위성 Fix가 해제(Loss)되었습니다.\n"
            "즉각적인 상태 확인이 필요합니다.\n"
            "네트워크망은 WO로 Holdover로 자동 동작할 것입니다"
        )
        threading.Thread(target=send_alert_email_ssl, args=(
            f"[위급 경고] GNSS 위성 Loss 및 Holdover 전환 예고 ({current_timestamp})", 
            alert_body
        )).start()

def main_execution():
    print("⏳ [10분 테스트 배포본] 30초 간격 정밀 모니터링 시험 구동을 개시합니다.")
    
    # 💡 타이머 기록 시작
    start_time = time.time()
    # 💡 10분을 초 단위로 연산 (10분 = 600초)
    ten_minutes_in_seconds = 10 * 60 
    round_counter = 1
    
    try:
        while True:
            elapsed_time = time.time() - start_time
            # 💡 10분이 지나면 스스로 안전하게 루프 탈출
            if elapsed_time >= ten_minutes_in_seconds:
                print("\n⏰ [안내] 기획된 10분간의 정밀 모니터링 시험이 무사히 만료되었습니다.")
                break
                
            print(f"\n🔄 정기 점검 수행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (제 {round_counter}회차)")
            monitor_interval()
            round_counter += 1
            
            print(f"😴 점검 완료. {INTERVAL_SECONDS}초 동안 대기(자원 완전 개방)합니다...")
            time.sleep(INTERVAL_SECONDS)
            
        print("\n🏁 모든 시험 시나리오가 성공적으로 자동 종료되었습니다.")
    except KeyboardInterrupt:
        print("\n🛑 프로그램이 사용자에 의해 안전하게 완전 종료되었습니다.")

if __name__ == "__main__":
    main_execution()
