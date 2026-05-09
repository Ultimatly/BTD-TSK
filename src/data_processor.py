import os
from pathlib import Path

import numpy as np
import pywt
import wfdb
from scipy.signal import butter, filtfilt, find_peaks, welch
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

EEG_ENGINEERED_FEATURE_DIM = 13
ECG_HRV_FEATURE_DIM_BASE = 5
ECG_HRV_FEATURE_DIM_OPT = 9
ECG_HRV_FEATURE_DIM = ECG_HRV_FEATURE_DIM_BASE
MULTIMODAL_ENGINEERED_FEATURE_DIM = EEG_ENGINEERED_FEATURE_DIM + ECG_HRV_FEATURE_DIM_BASE
MULTIMODAL_ENGINEERED_OPT_FEATURE_DIM = EEG_ENGINEERED_FEATURE_DIM + ECG_HRV_FEATURE_DIM_OPT
ENGINEERED_FEATURE_DIM = EEG_ENGINEERED_FEATURE_DIM
DEFAULT_FEATURE_MODE = 'multisource_engineered_opt'
MULTIMODAL_ENGINEERED_OPT_FEATURE_NAMES_CN = [
    'EEG相对δ波功率',
    'EEG相对θ波功率',
    'EEG相对α波功率',
    'EEG相对β波功率',
    'EEG θ/α功率比',
    'EEG谱边缘频率SEF95',
    'EEG谱熵',
    'EEG均方根值',
    'EEG标准差',
    'EEG Hjorth活动度',
    'EEG Hjorth移动度',
    'EEG Hjorth复杂度',
    'EEG波形长度',
    'ECG平均心率',
    'ECG SDNN',
    'ECG RMSSD',
    'ECG pNN50',
    'ECG RR变异系数',
    'ECG SDSD',
    'ECG RR中位绝对偏差',
    'ECG LF/HF比值',
    'ECG HF归一化功率',
]


def get_multisource_feature_names_cn():
    return list(MULTIMODAL_ENGINEERED_OPT_FEATURE_NAMES_CN)


def butter_bandpass_filter(data, lowcut=0.5, highcut=30.0, fs=250.0, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, data)


def wavelet_denoise(signal, wavelet='db6'):
    level = pywt.dwt_max_level(len(signal), pywt.Wavelet(wavelet).dec_len)
    coeffs = pywt.wavedec(signal, wavelet, mode='per', level=level)

    sigma = np.median(np.abs(coeffs[-1])) / 0.6745
    threshold = sigma * np.sqrt(2 * np.log(len(signal)))

    coeffs_thresholded = [coeffs[0]] + [
        pywt.threshold(component, value=threshold, mode='soft') for component in coeffs[1:]
    ]
    return pywt.waverec(coeffs_thresholded, wavelet, mode='per')


def _find_signal_index(sig_names, keywords):
    for idx, sig_name in enumerate(sig_names):
        sig_upper = sig_name.upper()
        for keyword in keywords:
            if keyword in sig_upper:
                return idx
    return -1


def get_label_mapping():
    return {'W': 0, '1': 1, '2': 2, '3': 3, '4': 3, 'R': 4}


def _normalize_stage_label(aux_note, symbol=None):
    if isinstance(aux_note, str):
        cleaned = aux_note.replace('\x00', '').strip()
        if cleaned:
            return cleaned.split()[0]
    if isinstance(symbol, str):
        return symbol.strip().replace('\x00', '')
    return ''


def _relative_band_power(freqs, psd, low_hz, high_hz):
    total_power = np.sum(psd) + 1e-12
    band_mask = (freqs >= low_hz) & (freqs < high_hz)
    return np.sum(psd[band_mask]) / total_power


def _spectral_edge_frequency(freqs, psd, low_hz=0.5, high_hz=30.0, edge_ratio=0.95):
    band_mask = (freqs >= low_hz) & (freqs <= high_hz)
    band_freqs = freqs[band_mask]
    band_psd = psd[band_mask]
    if len(band_freqs) == 0:
        return 0.0

    cumulative = np.cumsum(band_psd)
    total = cumulative[-1] + 1e-12
    threshold = edge_ratio * total
    idx = np.searchsorted(cumulative, threshold)
    idx = min(idx, len(band_freqs) - 1)
    return band_freqs[idx]


def extract_engineered_eeg_features(epoch_signal, fs):
    freqs, psd = welch(epoch_signal, fs=fs, nperseg=min(1024, len(epoch_signal)))
    psd = np.maximum(psd, 1e-12)

    delta_rel = _relative_band_power(freqs, psd, 0.5, 4.0)
    theta_rel = _relative_band_power(freqs, psd, 4.0, 8.0)
    alpha_rel = _relative_band_power(freqs, psd, 8.0, 13.0)
    beta_rel = _relative_band_power(freqs, psd, 13.0, 30.0)
    theta_alpha_ratio = theta_rel / (alpha_rel + 1e-12)
    spectral_edge_95 = _spectral_edge_frequency(freqs, psd, low_hz=0.5, high_hz=30.0, edge_ratio=0.95)

    psd_prob = psd / np.sum(psd)
    spectral_entropy = -np.sum(psd_prob * np.log(psd_prob + 1e-12)) / np.log(len(psd_prob))

    rms = np.sqrt(np.mean(epoch_signal**2))
    std_val = np.std(epoch_signal)

    activity = np.var(epoch_signal)
    diff_1 = np.diff(epoch_signal)
    diff_2 = np.diff(diff_1) if len(diff_1) > 1 else np.array([0.0])
    var_diff_1 = np.var(diff_1) + 1e-12
    var_diff_2 = np.var(diff_2) + 1e-12
    mobility = np.sqrt(var_diff_1 / (activity + 1e-12))
    complexity = np.sqrt(var_diff_2 / var_diff_1) / (mobility + 1e-12)

    waveform_length = np.sum(np.abs(diff_1))
    
    return np.array(
        [
            delta_rel,
            theta_rel,
            alpha_rel,
            beta_rel,
            theta_alpha_ratio,
            spectral_edge_95,
            spectral_entropy,
            rms,
            std_val,
            activity,
            mobility,
            complexity,
            waveform_length,
        ],
        dtype=float,
    )


def extract_ecg_hrv_features(epoch_ecg, fs):
    ecg_filtered = butter_bandpass_filter(epoch_ecg, lowcut=5.0, highcut=20.0, fs=fs, order=2)
    ecg_norm = (ecg_filtered - np.mean(ecg_filtered)) / (np.std(ecg_filtered) + 1e-12)

    min_peak_distance = max(1, int(0.3 * fs))
    base_height = np.percentile(ecg_norm, 75)
    peaks, _ = find_peaks(ecg_norm, distance=min_peak_distance, height=base_height, prominence=0.3)

    if len(peaks) < 3:
        fallback_height = np.percentile(ecg_norm, 60)
        peaks, _ = find_peaks(ecg_norm, distance=min_peak_distance, height=fallback_height)

    if len(peaks) < 3:
        return np.zeros(ECG_HRV_FEATURE_DIM_BASE, dtype=float)

    rr = np.diff(peaks) / fs
    rr = rr[(rr >= 0.3) & (rr <= 2.0)]
    if len(rr) < 2:
        return np.zeros(ECG_HRV_FEATURE_DIM_BASE, dtype=float)

    mean_rr = np.mean(rr)
    mean_hr = 60.0 / (mean_rr + 1e-12)
    sdnn = np.std(rr)
    diff_rr = np.diff(rr)
    rmssd = np.sqrt(np.mean(diff_rr**2)) if len(diff_rr) > 0 else 0.0
    pnn50 = np.mean(np.abs(diff_rr) > 0.05) if len(diff_rr) > 0 else 0.0
    rr_cv = sdnn / (mean_rr + 1e-12)

    return np.array([mean_hr, sdnn, rmssd, pnn50, rr_cv], dtype=float)


def _robust_ecg_peaks(epoch_ecg, fs):
    ecg_filtered = butter_bandpass_filter(epoch_ecg, lowcut=5.0, highcut=20.0, fs=fs, order=2)
    ecg_diff = np.diff(ecg_filtered, prepend=ecg_filtered[0])
    ecg_energy = ecg_diff**2

    window = max(1, int(0.12 * fs))
    kernel = np.ones(window) / window
    ecg_envelope = np.convolve(ecg_energy, kernel, mode='same')
    ecg_envelope = (ecg_envelope - np.median(ecg_envelope)) / (np.std(ecg_envelope) + 1e-12)

    min_peak_distance = max(1, int(0.25 * fs))
    mad = np.median(np.abs(ecg_envelope - np.median(ecg_envelope))) + 1e-12
    threshold = np.median(ecg_envelope) + 1.5 * mad
    peaks, _ = find_peaks(
        ecg_envelope,
        distance=min_peak_distance,
        height=threshold,
        prominence=0.2,
    )

    if len(peaks) < 3:
        peaks, _ = find_peaks(
            ecg_envelope,
            distance=min_peak_distance,
            height=np.percentile(ecg_envelope, 65),
        )

    return peaks


def _clean_rr_intervals(rr):
    rr = rr[(rr >= 0.3) & (rr <= 2.0)]
    if len(rr) < 3:
        return rr

    q1, q3 = np.percentile(rr, [25, 75])
    iqr = q3 - q1
    low = max(0.3, q1 - 1.5 * iqr)
    high = min(2.0, q3 + 1.5 * iqr)
    return rr[(rr >= low) & (rr <= high)]


def _hrv_frequency_features(rr):
    if len(rr) < 4:
        return 0.0, 0.0

    rr_times = np.cumsum(rr)
    rr_times = rr_times - rr_times[0]
    if rr_times[-1] <= 0:
        return 0.0, 0.0

    fs_interp = 4.0
    t_uniform = np.arange(0, rr_times[-1], 1.0 / fs_interp)
    if len(t_uniform) < 8:
        return 0.0, 0.0

    rr_interp = np.interp(t_uniform, rr_times, rr)
    rr_interp = rr_interp - np.mean(rr_interp)
    freqs, psd = welch(rr_interp, fs=fs_interp, nperseg=min(128, len(rr_interp)))

    lf_mask = (freqs >= 0.04) & (freqs < 0.15)
    hf_mask = (freqs >= 0.15) & (freqs <= 0.4)
    lf_power = np.trapz(psd[lf_mask], freqs[lf_mask]) if np.any(lf_mask) else 0.0
    hf_power = np.trapz(psd[hf_mask], freqs[hf_mask]) if np.any(hf_mask) else 0.0
    total = lf_power + hf_power + 1e-12

    lf_hf_ratio = lf_power / (hf_power + 1e-12)
    hf_norm = hf_power / total
    return lf_hf_ratio, hf_norm


def extract_ecg_hrv_features_optimized(epoch_ecg, fs):
    peaks = _robust_ecg_peaks(epoch_ecg, fs)
    if len(peaks) < 3:
        return np.zeros(ECG_HRV_FEATURE_DIM_OPT, dtype=float)

    rr = np.diff(peaks) / fs
    rr = _clean_rr_intervals(rr)
    if len(rr) < 2:
        return np.zeros(ECG_HRV_FEATURE_DIM_OPT, dtype=float)

    mean_rr = np.mean(rr)
    mean_hr = 60.0 / (mean_rr + 1e-12)
    sdnn = np.std(rr)
    diff_rr = np.diff(rr)
    rmssd = np.sqrt(np.mean(diff_rr**2)) if len(diff_rr) > 0 else 0.0
    pnn50 = np.mean(np.abs(diff_rr) > 0.05) if len(diff_rr) > 0 else 0.0
    rr_cv = sdnn / (mean_rr + 1e-12)
    sdsd = np.std(diff_rr) if len(diff_rr) > 0 else 0.0
    mad_rr = np.median(np.abs(rr - np.median(rr)))
    lf_hf_ratio, hf_norm = _hrv_frequency_features(rr)

    return np.array(
        [mean_hr, sdnn, rmssd, pnn50, rr_cv, sdsd, mad_rr, lf_hf_ratio, hf_norm],
        dtype=float,
    )


def process_record(data_dir, record_name):
    record_path = os.path.join(data_dir, record_name)
    record = wfdb.rdrecord(record_path)
    ann = wfdb.rdann(record_path, 'st')

    eeg_idx = _find_signal_index(record.sig_name, ['EEG'])
    if eeg_idx == -1:
        raise ValueError(f'记录 {record_name} 中未找到 EEG 信号')

    signal = record.p_signal[:, eeg_idx]
    ecg_idx = _find_signal_index(record.sig_name, ['ECG', 'EKG'])
    if ecg_idx == -1:
        print(f'  警告: 记录 {record_name} 未找到 ECG 通道，将使用全零 HRV 特征。')
    ecg_signal = record.p_signal[:, ecg_idx] if ecg_idx != -1 else None

    epoch_len = int(30 * record.fs)
    label_map = get_label_mapping()

    X = []
    y = []
    for idx, sample_idx in enumerate(ann.sample):
        if sample_idx + epoch_len > len(signal):
            break

        symbol = ann.symbol[idx] if hasattr(ann, 'symbol') and len(ann.symbol) > idx else None
        base_label = _normalize_stage_label(ann.aux_note[idx], symbol=symbol)
        if base_label not in label_map:
            continue

        epoch_data = signal[sample_idx:sample_idx + epoch_len]
        epoch_filtered = butter_bandpass_filter(epoch_data, lowcut=0.5, highcut=30.0, fs=record.fs)
        epoch_denoised = wavelet_denoise(epoch_filtered, wavelet='db6')
        eeg_features = extract_engineered_eeg_features(epoch_denoised, record.fs)
        if ecg_signal is None:
            ecg_features = np.zeros(ECG_HRV_FEATURE_DIM_OPT, dtype=float)
        else:
            ecg_epoch = ecg_signal[sample_idx:sample_idx + epoch_len]
            ecg_features = extract_ecg_hrv_features_optimized(ecg_epoch, record.fs)
        X.append(np.concatenate([eeg_features, ecg_features], axis=0))
        y.append(label_map[base_label])

    X_arr = np.array(X)
    y_arr = np.array(y)
    if X_arr.ndim == 1 and len(X_arr) == 0:
        X_arr = np.zeros((0, MULTIMODAL_ENGINEERED_OPT_FEATURE_DIM))
    return X_arr, y_arr


def process_record_with_metadata(data_dir, record_name):
    X_arr, y_arr = process_record(data_dir, record_name)
    metadata = [
        {
            'record_name': record_name,
            'sequence_index': seq_idx,
        }
        for seq_idx in range(len(y_arr))
    ]
    return X_arr, y_arr, metadata


def build_context_windows(X, group_ids=None, radius=1):
    if radius < 1 or len(X) == 0:
        return np.asarray(X, dtype=float).copy()

    if group_ids is None:
        group_ids = np.zeros(len(X), dtype=int)

    group_ids = np.asarray(group_ids)
    context_features = []
    start = 0

    while start < len(X):
        end = start + 1
        while end < len(X) and group_ids[end] == group_ids[start]:
            end += 1

        group_X = np.asarray(X[start:end], dtype=float)
        for idx in range(len(group_X)):
            slices = []
            for offset in range(-radius, radius + 1):
                ref_idx = idx + offset
                if ref_idx < 0:
                    ref_idx = 0
                elif ref_idx >= len(group_X):
                    ref_idx = len(group_X) - 1
                slices.append(group_X[ref_idx])
            context_features.append(np.concatenate(slices, axis=0))
        start = end

    return np.asarray(context_features, dtype=float)


def build_dataset_bundle(data_dir, record_names, test_size=0.25, random_state=42):
    X_all = []
    y_all = []
    metadata_all = []

    print(f'正在加载记录: {record_names}')
    print('类别模式: 固定五分类')
    print(f'特征模式: 固定多源数据工程化优化特征（{DEFAULT_FEATURE_MODE}）')
    for rec in record_names:
        print(f'正在处理 {rec}...')
        try:
            X_rec, y_rec, metadata_rec = process_record_with_metadata(data_dir, rec)
            if len(X_rec) > 0:
                X_all.append(X_rec)
                y_all.append(y_rec)
                metadata_all.extend(metadata_rec)
            else:
                print(f'  警告: {rec} 提取到 0 个样本，已跳过。')
        except Exception as exc:
            print(f'  错误: 处理 {rec} 失败（{exc}），已跳过。')

    if not X_all:
        raise ValueError('没有可用记录可处理。')

    X_all = np.concatenate(X_all, axis=0)
    y_all = np.concatenate(y_all, axis=0)

    print(f'优化后多源数据工程化特征数据形状: {X_all.shape}')

    indices = np.arange(len(y_all))
    train_idx, test_idx = train_test_split(indices, test_size=test_size, random_state=random_state)
    scaler = MinMaxScaler()
    scaler.fit(X_all[train_idx])
    X_scaled = scaler.transform(X_all)
    return {
        'X_all': X_scaled,
        'y_all': y_all,
        'metadata': metadata_all,
        'train_idx': np.asarray(train_idx, dtype=int),
        'test_idx': np.asarray(test_idx, dtype=int),
        'scaler': scaler,
    }


def build_dataset(data_dir, record_names, eeg_weight=1.0, ecg_weight=1.0):
    bundle = build_dataset_bundle(
        data_dir=data_dir,
        record_names=record_names,
        test_size=0.25,
        random_state=42,
    )
    X_all = bundle['X_all']
    y_all = bundle['y_all']
    train_idx = bundle['train_idx']
    test_idx = bundle['test_idx']

    print(
        '已停用人工模态加权，当前仅保留统一 Min-Max 归一化；'
        f'忽略传入权重 EEG={eeg_weight:.3f}, ECG={ecg_weight:.3f}'
    )

    X_train = X_all[train_idx]
    X_test = X_all[test_idx]
    y_train = y_all[train_idx]
    y_test = y_all[test_idx]
    return X_train, X_test, y_train, y_test


if __name__ == '__main__':
    project_root = Path(__file__).resolve().parents[1]
    data_dir = str(project_root / 'data')
    test_records = ['slp01a', 'slp01b']
    X_train, X_test, y_train, y_test = build_dataset(data_dir, test_records)
    print('训练特征形状:', X_train.shape)
    print('测试特征形状:', X_test.shape)
    print('标签集合:', np.unique(np.concatenate([y_train, y_test])))
    print('数据处理测试通过。')
