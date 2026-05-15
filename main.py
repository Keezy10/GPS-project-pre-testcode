import paramiko
import time
from datetime import datetime
import threading
import re

# --- [설정] 서버 정보 입력 ---
GNSS_SERVER = {'ip': '10.231.164.212', 'user': 'lgeadmin', 'pw': 'lge123!!'}
PING_SERVER = {'ip': '10.231.165.47', 'user': 'appserver', 'pw': 'lge123!!'}
TARGET_IP = '10.218.225.144'  # PING_SERVER에서 핑을 날릴 목적지

# 공유 데이터 객체 및 제어 플래그
shared_data = {'sat_count': 0, 'fix': '0', 'latency': 0.0}
stop_event = threading.Event()

def get_gnss_worker():
    """[스레드 1] GNSS 서버에서 실시간 스트리밍 데이터를 읽어와 변수 갱신"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"📡 [GNSS 서버] {GNSS_SERVER['ip']} 접속 시도...")
        ssh.connect(GNSS_SERVER['ip'], username=GNSS_SERVER['user'], password=GNSS_SERVER['pw'])
        print("📡 [GNSS 서버] 접속 성공!")
        
        stdin, stdout, stderr = ssh.exec_command('sudo -S cat /dev/gnss0')
        stdin.write(GNSS_SERVER['pw'] + '\n')
        stdin.flush()

        while not stop_event.is_set():
            line = stdout.readline()
            if not line:
                break
            if '$GNGGA' in line:
                parts = line.split(',')
                if len(parts) > 7:
                    shared_data['fix'] = parts[6]
                    shared_data['sat_count'] = int(parts[7]) if parts[7].isdigit() else 0
    except Exception as e:
        print(f"❌ GNSS 스레드 에러: {e}")
    finally:
        ssh.close()
        print("📡 [GNSS 서버] 연결 종료")

def monitor_sync_test(duration=5):
    """[스레드 2] PING 서버에 접속하여 5초간 화면에 데이터를 매칭하여 출력"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"💻 [PING 서버] {PING_SERVER['ip']} 접속 시도...")
        ssh.connect(PING_SERVER['ip'], username=PING_SERVER['user'], password=PING_SERVER['pw'])
        print("💻 [PING 서버] 접속 성공!")
        
        start_time = time.time()
        print("\n--- 🔍 5초간 싱크 테스트 모니터링 시작 ---")
        
        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time >= duration:
                break
                
            # PING 지연시간 측정
            cmd = f"ping -c 1 {TARGET_IP} | grep 'time='"
            _, stdout, _ = ssh.exec_command(cmd)
            res = stdout.read().decode('utf-8')
            match = re.search(r"time=([\d.]+)\s*ms", res)
            latency = float(match.group(1)) if match else 0.0
            
            now = datetime.now().strftime('%H:%M:%S')
            current_fix = shared_data['fix']
            current_sat = shared_data['sat_count']
            
            # 처음 2초간 싱크가 안 맞아서 0이 찍히는지 눈으로 확인하는 화면 출력
            if elapsed_time < 2:
                print(f"[{now}] ⏳ 초반 2초 대기구간 -> 위성: {current_sat}개, Fix: {current_fix}, 지연: {latency}ms")
            else:
                print(f"[{now}] ✅ 데이터 매칭 성공 -> 위성: {current_sat}개, Fix: {current_fix}, 지연: {latency}ms")
                
            time.sleep(1)
            
        print("--- 🔍 싱크 테스트 모니터링 종료 ---\n")
    except Exception as e:
        print(f"❌ PING 스레드 에러: {e}")
    finally:
        ssh.close()
        print("💻 [PING 서버] 연결 종료")

if __name__ == "__main__":
    # 두 스레드 병렬 실행
    gnss_thread = threading.Thread(target=get_gnss_worker, daemon=True)
    gnss_thread.start()
    
    # GNSS 세션이 먼저 열리도록 2초 여유를 둡니다.
    time.sleep(2)
    
    # 5초 동안 화면에 데이터가 어떻게 합쳐지는지 출력 테스트
    monitor_sync_test(duration=5)
    
    # 테스트 종료 후 GNSS 스레드 정지
    stop_event.set()
