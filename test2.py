import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 1. 데이터 정의 (원본 데이터 유지)
data = {
    'Time': [
        '09:00:00', '09:00:01', '09:00:02', '09:10:00', '09:10:01', '09:10:02',
        '09:20:00', '09:20:01', '09:20:02', '09:30:00', '09:30:01', '09:30:02',
        '09:40:00', '09:40:01', '09:40:02', '09:50:00', '09:50:01', '09:50:02',
        '10:00:00', '10:00:01', '10:00:02', '10:10:00', '10:10:01', '10:10:02',
        '10:20:00', '10:20:01', '10:20:02', '10:30:00', '10:30:01', '10:30:02',
        '10:40:00', '10:40:01', '10:40:02', '10:50:00', '10:50:01', '10:50:02',
        '11:00:00', '11:00:01', '11:00:02', '11:10:00', '11:10:01', '11:10:02',
        '11:20:00', '11:20:01', '11:20:02', '11:30:00', '11:30:01', '11:30:02'
    ],
    'Sat_Count': [
        11, 9, 10, 10, 10, 9, 9, 11, 9, 10, 9, 9, 9, 10, 9, 10, 9, 9,
        4, 2, 0, 10, 10, 9, 11, 11, 10, 9, 11, 11, 10, 9, 11,
        10, 10, 9, 
        10, 10, 9, 10, 9, 9, 9, 9, 11, 10, 11, 9
    ],
    'Latency_ms': [
        10.36, 8.32, 8.86, 9.32, 11.93, 9.54, 12.06, 10.4, 10.31, 9.96, 8.66, 8.64,
        8.52, 12.71, 10.61, 12.2, 10.6, 10.56, 345.2, 358.9, np.nan, 11.44, 10.76, 11.76,
        13.19, 12.41, 11.15, 10.52, 12.51, 12.51, 9.14, 8.38, 10.07,
        np.nan, np.nan, np.nan, 
        11.75, 12.48, 10.73, 11.83, 13.15, 12.42, 11.01, 12.13, 13.45, 9.38, 13.12, 9.31
    ]
}

df = pd.DataFrame(data)

# 2. 결측치 제외 및 수신 지연 시간 상위 데이터(이상치 영역) 추출
df_clean = df.dropna(subset=['Latency_ms']).copy()

# 시각적 트렌드 매칭을 위해 지연 시간이 가장 높은 상위 6개 시점 선택 및 시간순 정렬
outliers = df_clean.nlargest(6, 'Latency_ms').sort_values('Time').reset_index(drop=True)

# X축 레이블 텍스트 생성 (예시 이미지와 동일한 스타일)
outliers['X_Label'] = outliers['Time'] + '\n(Outlier)'

# 3. 이중 Y축 그래프 시각화 (등간격 선 그래프)
fig, ax1 = plt.subplots(figsize=(11, 5))

# --- 좌측 Y축: 위성 수 (파란색 점선 + 원 마커) ---
color_sat = '#1f77b4'
ax1.set_ylabel('Satellite Count', color=color_sat, fontweight='bold')
ax1.plot(
    outliers['X_Label'], outliers['Sat_Count'], 
    color=color_sat, linestyle='--', marker='o', markersize=6, label='Sat Count'
)
ax1.tick_params(axis='y', labelcolor=color_sat)
ax1.set_ylim(-0.5, 4.5)  # 예시 이미지의 Y축 범위 반영

# --- 우측 Y축: 지연 시간 (빨간색 실선 + 엑스 마커) ---
ax2 = ax1.twinx()
color_lat = '#d62728'
ax2.set_ylabel('Latency (ms)', color=color_lat, fontweight='bold')
ax2.plot(
    outliers['X_Label'], outliers['Latency_ms'], 
    color=color_lat, linestyle='-', marker='x', markersize=7, linewidth=1.5, label='Latency'
)
ax2.tick_params(axis='y', labelcolor=color_lat)
ax2.set_ylim(100, 400)  # 예시 이미지의 Y축 범위 반영

# 그래프 스타일링
ax1.grid(True, linestyle=':', alpha=0.4)

fig.tight_layout()
plt.show()
