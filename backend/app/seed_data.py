from __future__ import annotations

from datetime import datetime


def now_text() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


PATIENT_SEED = [
    {
        'patient_code': 'P-001',
        'name': '张晨曦',
        'gender': '女',
        'age': 28,
        'status': '已分析',
        'current_risk': '低风险',
        'modalities': ['EEG', 'ECG'],
    },
    {
        'patient_code': 'P-002',
        'name': '李子昂',
        'gender': '男',
        'age': 35,
        'status': '已分析',
        'current_risk': '中风险',
        'modalities': ['EEG', 'ECG'],
    },
    {
        'patient_code': 'P-003',
        'name': '周若宁',
        'gender': '女',
        'age': 42,
        'status': '待分析',
        'current_risk': '待评估',
        'modalities': ['EEG'],
    },
    {
        'patient_code': 'P-004',
        'name': '王景行',
        'gender': '男',
        'age': 31,
        'status': '已分析',
        'current_risk': '高风险',
        'modalities': ['EEG', 'ECG'],
    },
]


SEEDED_HISTORY = [
    {
        'run_code': 'history-001',
        'patient_code': 'P-002',
        'model_code': 'btd_tsk_student_Data-A',
        'created_at': '2026-03-30 10:30:00',
        'finished_at': '2026-03-30 10:36:00',
        'status': 'done',
        'risk_level': '中风险',
        'dominant_stage': 'N2',
        'focus_class': 'R',
        'conclusion': 'REM 阶段占比偏高，提示存在轻度睡眠结构波动。',
        'summary': 'REM 阶段占比偏高，建议继续随访观察。',
        'advice': '建议结合临床表现持续观察 REM 相关变化，并定期复查。',
        'stage_stats': {'W': 12, 'N1': 9, 'N2': 46, 'N3': 18, 'R': 15},
        'rule_refs': [(1, 1), (1, 2), (1, 3)],
    },
    {
        'run_code': 'history-002',
        'patient_code': 'P-001',
        'model_code': 'btd_tsk_student_Data-B',
        'created_at': '2026-03-28 16:12:00',
        'finished_at': '2026-03-28 16:18:00',
        'status': 'done',
        'risk_level': '低风险',
        'dominant_stage': 'N2',
        'focus_class': 'N2',
        'conclusion': '整体睡眠结构较稳定，未见明显异常阶段分布。',
        'summary': '当前睡眠结构整体稳定，建议常规随访。',
        'advice': '建议维持当前作息习惯，并结合后续记录持续观察。',
        'stage_stats': {'W': 11, 'N1': 8, 'N2': 49, 'N3': 17, 'R': 15},
        'rule_refs': [(1, 1), (1, 4), (1, 6)],
    },
    {
        'run_code': 'history-003',
        'patient_code': 'P-004',
        'model_code': 'btd_tsk_student_Data-A',
        'created_at': '2026-03-29 20:18:00',
        'finished_at': '2026-03-29 20:25:00',
        'status': 'done',
        'risk_level': '高风险',
        'dominant_stage': 'N2',
        'focus_class': 'N3',
        'conclusion': '深睡阶段占比不足，提示夜间恢复质量偏弱。',
        'summary': '深睡阶段占比偏低，建议重点关注睡眠恢复情况。',
        'advice': '建议进一步评估深睡不足原因，并结合症状进行综合判断。',
        'stage_stats': {'W': 16, 'N1': 13, 'N2': 44, 'N3': 9, 'R': 18},
        'rule_refs': [(1, 2), (1, 5), (1, 7)],
    },
]
