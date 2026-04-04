import os

import numpy as np
import pywt
import wfdb
from scipy.signal import butter, filtfilt, welch
from sklearn.decomposition import KernelPCA
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

HANDCRAFTED_FEATURE_DIM = 13


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


def get_label_mapping(class_mode='six_class'):
    if class_mode == 'five_class':
        return {'W': 0, '1': 1, '2': 2, '3': 3, '4': 3, 'R': 4}
    if class_mode == 'six_class':
        return {'W': 0, '1': 1, '2': 2, '3': 3, '4': 4, 'R': 5}
    raise ValueError(f'Unsupported class_mode: {class_mode}')


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


def extract_handcrafted_features(epoch_signal, fs):
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

    rms = np.sqrt(np.mean(epoch_signal ** 2))
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


def process_record(data_dir, record_name, class_mode='six_class', feature_mode='handcrafted'):
    record_path = os.path.join(data_dir, record_name)
    record = wfdb.rdrecord(record_path)
    ann = wfdb.rdann(record_path, 'st')

    eeg_idx = -1
    for idx, sig_name in enumerate(record.sig_name):
        if 'EEG' in sig_name:
            eeg_idx = idx
            break

    if eeg_idx == -1:
        raise ValueError(f'No EEG signal found in {record_name}')

    signal = record.p_signal[:, eeg_idx]
    epoch_len = int(30 * record.fs)
    label_map = get_label_mapping(class_mode)

    X = []
    y = []
    for idx, sample_idx in enumerate(ann.sample):
        if sample_idx + epoch_len > len(signal):
            break

        base_label = ann.aux_note[idx].split()[0]
        if base_label not in label_map:
            continue

        epoch_data = signal[sample_idx:sample_idx + epoch_len]
        epoch_filtered = butter_bandpass_filter(epoch_data, lowcut=0.5, highcut=30.0, fs=record.fs)
        epoch_denoised = wavelet_denoise(epoch_filtered, wavelet='db6')
        if feature_mode == 'handcrafted':
            X.append(extract_handcrafted_features(epoch_denoised, record.fs))
        elif feature_mode == 'kpca':
            X.append(epoch_denoised)
        else:
            raise ValueError(f'Unsupported feature_mode: {feature_mode}')
        y.append(label_map[base_label])

    X_arr = np.array(X)
    y_arr = np.array(y)
    if X_arr.ndim == 1 and len(X_arr) == 0:
        if feature_mode == 'handcrafted':
            X_arr = np.zeros((0, HANDCRAFTED_FEATURE_DIM))
        else:
            X_arr = np.zeros((0, epoch_len))
    return X_arr, y_arr


def build_dataset(
    data_dir,
    record_names,
    n_components=10,
    class_mode='six_class',
    feature_mode='handcrafted',
):
    X_all = []
    y_all = []

    print(f'Loading records: {record_names}')
    print(f'Class mode: {class_mode}')
    print(f'Feature mode: {feature_mode}')
    for rec in record_names:
        print(f'Processing {rec}...')
        try:
            X_rec, y_rec = process_record(
                data_dir, rec, class_mode=class_mode, feature_mode=feature_mode
            )
            if len(X_rec) > 0:
                X_all.append(X_rec)
                y_all.append(y_rec)
            else:
                print(f'  Warning: {rec} resulted in 0 samples. Skipping.')
        except Exception as exc:
            print(f'  Error processing {rec}: {exc}. Skipping.')

    if not X_all:
        raise ValueError('No valid records to process.')

    X_all = np.concatenate(X_all, axis=0)
    y_all = np.concatenate(y_all, axis=0)

    if feature_mode == 'kpca':
        print(f'Dataset shape before KPCA: {X_all.shape}')
        kpca = KernelPCA(n_components=n_components, kernel='rbf', fit_inverse_transform=False, n_jobs=1)
        X_processed = kpca.fit_transform(X_all)
        print(f'Dataset shape after KPCA: {X_processed.shape}')
    elif feature_mode == 'handcrafted':
        X_processed = X_all
        print(f'Dataset shape of handcrafted features: {X_processed.shape}')
    else:
        raise ValueError(f'Unsupported feature_mode: {feature_mode}')

    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X_processed)

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y_all, test_size=0.25, random_state=42
    )
    return X_train, X_test, y_train, y_test


if __name__ == '__main__':
    data_dir = r'f:\sleep\data'
    test_records = ['slp01a', 'slp01b']
    X_train, X_test, y_train, y_test = build_dataset(
        data_dir,
        test_records,
        n_components=10,
        class_mode='five_class',
        feature_mode='handcrafted',
    )
    print('Train features shape:', X_train.shape)
    print('Test features shape:', X_test.shape)
    print('Unique labels:', np.unique(np.concatenate([y_train, y_test])))
    print('Data processing test passed!')
