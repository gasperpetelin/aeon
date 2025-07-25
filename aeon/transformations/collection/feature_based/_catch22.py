"""Catch22 features.

A transformer for the Catch22 features.
"""

__maintainer__ = []
__all__ = ["Catch22"]

import math
import warnings

import numpy as np
from joblib import Parallel, delayed
from numba import njit

from aeon.transformations.collection.base import BaseCollectionTransformer
from aeon.utils.numba.general import z_normalise_series, z_normalise_series_with_mean
from aeon.utils.numba.stats import mean, numba_max, numba_min
from aeon.utils.validation import check_n_jobs
from aeon.utils.validation._dependencies import _check_soft_dependencies

feature_names = [
    "DN_HistogramMode_5",
    "DN_HistogramMode_10",
    "CO_f1ecac",
    "CO_FirstMin_ac",
    "CO_HistogramAMI_even_2_5",
    "CO_trev_1_num",
    "MD_hrv_classic_pnn40",
    "SB_BinaryStats_mean_longstretch1",
    "SB_TransitionMatrix_3ac_sumdiagcov",
    "PD_PeriodicityWang_th0_01",
    "CO_Embed2_Dist_tau_d_expfit_meandiff",
    "IN_AutoMutualInfoStats_40_gaussian_fmmi",
    "FC_LocalSimple_mean1_tauresrat",
    "DN_OutlierInclude_p_001_mdrmd",
    "DN_OutlierInclude_n_001_mdrmd",
    "SP_Summaries_welch_rect_area_5_1",
    "SB_BinaryStats_diff_longstretch0",
    "SB_MotifThree_quantile_hh",
    "SC_FluctAnal_2_rsrangefit_50_1_logi_prop_r1",
    "SC_FluctAnal_2_dfa_50_1_2_logi_prop_r1",
    "SP_Summaries_welch_rect_centroid",
    "FC_LocalSimple_mean3_stderr",
]

feature_names_short = [
    "mode_5",
    "mode_10",
    "acf_timescale",
    "acf_first_min",
    "ami2",
    "trev",
    "high_fluctuation",
    "stretch_high",
    "transition_matrix",
    "periodicity",
    "embedding_dist",
    "ami_timescale",
    "whiten_timescale",
    "outlier_timing_pos",
    "outlier_timing_neg",
    "centroid_freq",
    "stretch_decreasing",
    "entropy_pairs",
    "rs_range",
    "dfa",
    "low_freq_power",
    "forecast_error",
]


class Catch22(BaseCollectionTransformer):
    """Canonical Time-series Characteristics (Catch22).

    Overview: Input n series with d dimensions of length m.
    Transforms series into the 22 Catch22 [1]_ features extracted from the hctsa [2]_
    toolbox.

    Parameters
    ----------
    features : int/str or List of int/str, default="all"
        The Catch22 features to extract by feature index, feature name as a str or as a
        list of names or indices for multiple features. If "all", all features are
        extracted.
        Valid features are as follows:
            ["DN_HistogramMode_5", "DN_HistogramMode_10", "CO_f1ecac","CO_FirstMin_ac",
            "CO_HistogramAMI_even_2_5", "CO_trev_1_num", "MD_hrv_classic_pnn40",
            "SB_BinaryStats_mean_longstretch1", "SB_TransitionMatrix_3ac_sumdiagcov",
            "PD_PeriodicityWang_th0_01", "CO_Embed2_Dist_tau_d_expfit_meandiff",
            "IN_AutoMutualInfoStats_40_gaussian_fmmi", "FC_LocalSimple_mean1_tauresrat",
            "DN_OutlierInclude_p_001_mdrmd", "DN_OutlierInclude_n_001_mdrmd",
            "SP_Summaries_welch_rect_area_5_1", "SB_BinaryStats_diff_longstretch0",
            "SB_MotifThree_quantile_hh", "SC_FluctAnal_2_rsrangefit_50_1_logi_prop_r1",
            "SC_FluctAnal_2_dfa_50_1_2_logi_prop_r1",
            "SP_Summaries_welch_rect_centroid", "FC_LocalSimple_mean3_stderr"]
        Shortened:
            ["mode_5", "mode_10", "acf_timescale", "acf_first_min",
            "ami2", "trev", "high_fluctuation",
            "stretch_high", "transition_matrix",
            "periodicity", "embedding_dist",
            "ami_timescale", "whiten_timescale",
            "outlier_timing_pos", "outlier_timing_neg",
            "centroid_freq", "stretch_decreasing",
            "entropy_pairs", "rs_range",
            "dfa",
            "low_freq_power", "forecast_error"]

    catch24 : bool, default=False
        Extract the mean and standard deviation as well as the 22 Catch22 features if
        true. If a List of specific features to extract is provided, "Mean" and/or
        "StandardDeviation" must be added to the List to extract these features.
    outlier_norm : bool, optional, default=False
        If True, each time series is normalized during the computation of the two
        outlier Catch22 features, which can take a while to process for large values
        as it depends on the max value in the timseries. Note that this parameter
        did not exist in the original publication/implementation as they used time
        series that were already normalized.
    replace_nans : bool, default=False
        Replace NaN or inf values from the Catch22 transform with 0.
    use_pycatch22 : bool, optional, default=False
        Wraps the C based pycatch22 implementation for aeon.
        (https://github.com/DynamicsAndNeuralSystems/pycatch22). This requires the
        ``pycatch22`` package to be installed if True.
    n_jobs : int, default=1
        The number of jobs to run in parallel for `transform`. Requires multiple input
        cases. ``-1`` means using all processors.
    parallel_backend : str, ParallelBackendBase instance or None, default=None
        Specify the parallelisation backend implementation in joblib, if None a 'prefer'
        value of "threads" is used by default.
        Valid options are "loky", "multiprocessing", "threading" or a custom backend.
        See the joblib Parallel documentation for more details.

    See Also
    --------
    Catch22Classifier

    Notes
    -----
    Original Catch22 package implementations:
    https://github.com/DynamicsAndNeuralSystems/Catch22

    For the Java version, see
    https://github.com/uea-machine-learning/tsml/blob/master/src/main/java
    /tsml/transformers/Catch22.java

    References
    ----------
    .. [1] Lubba, C. H., Sethi, S. S., Knaute, P., Schultz, S. R., Fulcher, B. D., &
    Jones, N. S. (2019). catch22: Canonical time-series characteristics. Data Mining
    and Knowledge Discovery, 33(6), 1821-1852.
    .. [2] Fulcher, B. D., Little, M. A., & Jones, N. S. (2013). Highly comparative
    time-series analysis: the empirical structure of time series and their methods.
    Journal of the Royal Society Interface, 10(83), 20130048.

    Examples
    --------
    >>> from aeon.transformations.collection.feature_based import Catch22
    >>> from aeon.testing.data_generation import make_example_3d_numpy
    >>> X = make_example_3d_numpy(n_cases=4, n_channels=1, n_timepoints=10,
    ...                           random_state=0, return_y=False)
    >>> tnf = Catch22(replace_nans=True)
    >>> tnf.fit(X)
    Catch22(...)
    >>> print(tnf.transform(X)[0])
    [1.15639531e+00 1.31700577e+00 5.66227710e-01 2.00000000e+00
     3.89048349e-01 2.33853577e-01 1.00000000e+00 3.00000000e+00
     8.23045267e-03 0.00000000e+00 1.70859420e-01 2.00000000e+00
     1.00000000e+00 7.00000000e-01 2.00000000e-01 1.10933565e-32
     4.00000000e+00 2.04319187e+00 0.00000000e+00 0.00000000e+00
     1.96349541e+00 5.51667002e-01]
    """

    _tags = {
        "output_data_type": "Tabular",
        "X_inner_type": ["np-list", "numpy3D"],
        "capability:unequal_length": True,
        "capability:multivariate": True,
        "capability:multithreading": True,
        "fit_is_empty": True,
    }

    def __init__(
        self,
        features="all",
        catch24=False,
        outlier_norm=True,
        replace_nans=False,
        use_pycatch22=False,
        n_jobs=1,
        parallel_backend=None,
    ):
        self.features = features
        self.catch24 = catch24
        self.outlier_norm = outlier_norm
        self.replace_nans = replace_nans
        self.use_pycatch22 = use_pycatch22
        self.n_jobs = n_jobs
        self.parallel_backend = parallel_backend

        super().__init__()

        if use_pycatch22:
            self.set_tags(**{"python_dependencies": "pycatch22"})

    def _transform(self, X, y=None):
        """Transform X into the catch22 features.

        Parameters
        ----------
        X : 3D np.ndarray (any number of channels, equal length series)
                of shape (n_cases, n_channels, n_timepoints)
            or list of numpy arrays (any number of channels, unequal length series)
                of shape [n_cases], 2D np.array (n_channels, n_timepoints_i), where
                n_timepoints_i is length of series i

        Returns
        -------
        Xt : array-like, shape = [n_cases, num_features*n_channels]
            The catch22 features for each dimension.
        """
        n_cases = len(X)

        f_idx = _verify_features(self.features, self.catch24)
        n_jobs = check_n_jobs(self.n_jobs)

        features = [
            Catch22._DN_HistogramMode_5,
            Catch22._DN_HistogramMode_10,
            Catch22._CO_f1ecac,
            Catch22._CO_FirstMin_ac,
            Catch22._CO_HistogramAMI_even_2_5,
            Catch22._CO_trev_1_num,
            Catch22._MD_hrv_classic_pnn40,
            Catch22._SB_BinaryStats_mean_longstretch1,
            Catch22._SB_TransitionMatrix_3ac_sumdiagcov,
            Catch22._PD_PeriodicityWang_th0_01,
            Catch22._CO_Embed2_Dist_tau_d_expfit_meandiff,
            Catch22._IN_AutoMutualInfoStats_40_gaussian_fmmi,
            Catch22._FC_LocalSimple_mean1_tauresrat,
            Catch22._DN_OutlierInclude_p_001_mdrmd,
            Catch22._DN_OutlierInclude_n_001_mdrmd,
            Catch22._SP_Summaries_welch_rect_area_5_1,
            Catch22._SB_BinaryStats_diff_longstretch0,
            Catch22._SB_MotifThree_quantile_hh,
            Catch22._SC_FluctAnal_2_rsrangefit_50_1_logi_prop_r1,
            Catch22._SC_FluctAnal_2_dfa_50_1_2_logi_prop_r1,
            Catch22._SP_Summaries_welch_rect_centroid,
            Catch22._FC_LocalSimple_mean3_stderr,
        ]

        use_pycatch22_transform = False
        if self.use_pycatch22:
            if _check_soft_dependencies("pycatch22", severity="none"):
                import pycatch22

                features = [
                    pycatch22.DN_HistogramMode_5,
                    pycatch22.DN_HistogramMode_10,
                    pycatch22.CO_f1ecac,
                    pycatch22.CO_FirstMin_ac,
                    pycatch22.CO_HistogramAMI_even_2_5,
                    pycatch22.CO_trev_1_num,
                    pycatch22.MD_hrv_classic_pnn40,
                    pycatch22.SB_BinaryStats_mean_longstretch1,
                    pycatch22.SB_TransitionMatrix_3ac_sumdiagcov,
                    pycatch22.PD_PeriodicityWang_th0_01,
                    pycatch22.CO_Embed2_Dist_tau_d_expfit_meandiff,
                    pycatch22.IN_AutoMutualInfoStats_40_gaussian_fmmi,
                    pycatch22.FC_LocalSimple_mean1_tauresrat,
                    pycatch22.DN_OutlierInclude_p_001_mdrmd,
                    pycatch22.DN_OutlierInclude_n_001_mdrmd,
                    pycatch22.SP_Summaries_welch_rect_area_5_1,
                    pycatch22.SB_BinaryStats_diff_longstretch0,
                    pycatch22.SB_MotifThree_quantile_hh,
                    pycatch22.SC_FluctAnal_2_rsrangefit_50_1_logi_prop_r1,
                    pycatch22.SC_FluctAnal_2_dfa_50_1_2_logi_prop_r1,
                    pycatch22.SP_Summaries_welch_rect_centroid,
                    pycatch22.FC_LocalSimple_mean3_stderr,
                ]

                use_pycatch22_transform = True
            else:
                warnings.warn(
                    "pycatch22 not installed, but 'self.use_pycatch22' is set to True."
                    "Please install pycatch22. Aeon catch22 will be used.",
                    stacklevel=2,
                )

        c22_list = Parallel(
            n_jobs=n_jobs, backend=self.parallel_backend, prefer="threads"
        )(
            delayed(
                self._transform_case_pycatch22
                if use_pycatch22_transform
                else self._transform_case
            )(
                X[i],
                f_idx,
                features,
            )
            for i in range(n_cases)
        )

        c22_array = np.array(c22_list)
        if self.replace_nans:
            c22_array = np.nan_to_num(c22_array, False, 0, 0, 0)

        return c22_array

    def _transform_case(self, X, f_idx, features):
        c22 = np.zeros(len(f_idx) * len(X))

        if hasattr(self, "_transform_features") and len(
            self._transform_features
        ) == len(c22):
            transform_feature = self._transform_features
        else:
            transform_feature = [True] * len(c22)

        f_count = -1
        for i, series in enumerate(X):
            dim = i * len(f_idx)
            outlier_series = None
            smin = None
            smax = None
            smean = None
            fft = None
            ac = None
            acfz = None

            for n, feature in enumerate(f_idx):
                f_count += 1
                if not transform_feature[f_count]:
                    continue

                args = [series]

                if feature == 0 or feature == 1 or feature == 4:
                    if smin is None:
                        smin = numba_min(series)
                    if smax is None:
                        smax = numba_max(series)
                    args = [series, smin, smax]
                elif feature == 7 or feature == 22:
                    if smean is None:
                        smean = mean(series)
                    args = [series, smean]
                elif feature == 13 or feature == 14:
                    if self.outlier_norm:
                        if smean is None:
                            smean = mean(series)
                        if outlier_series is None:
                            outlier_series = z_normalise_series_with_mean(series, smean)
                        args = [outlier_series]
                    else:
                        args = [series]
                elif feature == 15 or feature == 20:
                    if smean is None:
                        smean = mean(series)
                    if fft is None:
                        nfft = int(
                            np.power(2, np.ceil(np.log(len(series)) / np.log(2)))
                        )
                        fft = np.fft.fft(series - smean, n=nfft)
                    args = [series, fft]
                elif feature == 2 or feature == 3:
                    if ac is None:
                        ac = _compute_autocorrelations(series)
                    args = [ac, len(series)]
                elif feature == 12 or feature == 10 or feature == 8:
                    if ac is None:
                        ac = _compute_autocorrelations(series)
                    if acfz is None:
                        acfz = _ac_first_zero(ac)
                    args = [series, acfz]
                if feature == 22:
                    c22[dim + n] = smean
                elif feature == 23:
                    c22[dim + n] = np.std(series)
                else:
                    c22[dim + n] = features[feature](*args)

        return c22

    def _transform_case_pycatch22(self, X, f_idx, features):
        c22 = np.zeros(len(f_idx) * len(X))

        if hasattr(self, "_transform_features") and len(
            self._transform_features
        ) == len(c22):
            transform_feature = self._transform_features
        else:
            transform_feature = [True] * len(c22)

        f_count = -1
        for i in range(len(X)):
            dim = i * len(f_idx)
            series = list(X[i])

            if self.outlier_norm and (3 in f_idx or 4 in f_idx):
                outlier_series = list(z_normalise_series(X[i]))

            for n, feature in enumerate(f_idx):
                f_count += 1
                if not transform_feature[f_count]:
                    continue

                if self.outlier_norm and feature in [3, 4]:
                    c22[dim + n] = features[feature](outlier_series)
                if feature == 22:
                    c22[dim + n] = np.mean(series)
                elif feature == 23:
                    c22[dim + n] = np.std(series)
                else:
                    c22[dim + n] = features[feature](series)

        return c22

    @property
    def get_features_arguments(self):
        """Return feature names for the estimators features argument."""
        return (
            self.features
            if self.features != "all"
            else (
                feature_names + ["Mean", "StandardDeviation"]
                if self.catch24
                else feature_names
            )
        )

    @staticmethod
    def _DN_HistogramMode_5(X, smin, smax):
        # Mode of z-scored distribution (5-bin histogram).
        return _histogram_mode(X, 5, smin, smax)

    @staticmethod
    def _DN_HistogramMode_10(X, smin, smax):
        # Mode of z-scored distribution (10-bin histogram).
        return _histogram_mode(X, 10, smin, smax)

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _SB_BinaryStats_diff_longstretch0(X):
        # Longest period of successive incremental decreases.
        diff_binary = np.zeros(len(X) - 1)
        for i in range(len(X) - 1):
            if X[i + 1] - X[i] >= 0:
                diff_binary[i] = 1

        return _long_stretch(diff_binary, 0)

    @staticmethod
    def _DN_OutlierInclude_p_001_mdrmd(X):
        # Time intervals between successive extreme events above the mean.
        return _outlier_include(X)

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _DN_OutlierInclude_n_001_mdrmd(X):
        # Time intervals between successive extreme events below the mean.
        return _outlier_include(-X)

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _CO_f1ecac(X_ac, size):
        # Parameter has already been transformed using _autocorr
        # First 1/e crossing of autocorrelation function.
        threshold = 0.36787944117144233  # 1 / np.exp(1)
        for i in range(len(X_ac) - 2):
            if X_ac[i + 1] < threshold:
                m = X_ac[i + 1] - X_ac[i]
                if m == 0:
                    return size
                dy = threshold - X_ac[i]
                dx = dy / m
                out = np.float64(i) + dx
                return out

        return len(X_ac)

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _CO_FirstMin_ac(X_ac, size):
        # First minimum of autocorrelation function.
        for i in range(1, len(X_ac) - 1):
            if X_ac[i] < X_ac[i - 1] and X_ac[i] < X_ac[i + 1]:
                return i
        return size

    @staticmethod
    def _SP_Summaries_welch_rect_area_5_1(X, X_fft):
        # Total power in lowest fifth of frequencies in the Fourier power spectrum.
        return _summaries_welch_rect(X, False, X_fft)

    @staticmethod
    def _SP_Summaries_welch_rect_centroid(X, X_fft):
        # Centroid of the Fourier power spectrum.
        return _summaries_welch_rect(X, True, X_fft)

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _FC_LocalSimple_mean3_stderr(X):
        # Mean error from a rolling 3-sample mean forecasting.
        if len(X) - 3 < 3:
            return 0
        res = _local_simple_mean(X, 3)
        return _stddev(res, len(X) - 3)

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _CO_trev_1_num(X):
        # Time-reversibility statistic, ((x_t+1 − x_t)^3)_t.
        y = np.zeros(len(X) - 1)
        for i in range(len(y)):
            y[i] = np.power(X[i + 1] - X[i], 3)
        return np.mean(y)

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _CO_HistogramAMI_even_2_5(X, smin, smax):
        # Automutual information, m = 2, τ = 5.
        new_min = smin - 0.1
        new_max = smax + 0.1
        bin_width = (new_max - new_min) / 5

        histogram = np.zeros((5, 5))
        sumx = np.zeros(5)
        sumy = np.zeros(5)
        v = 1.0 / (len(X) - 2)
        for i in range(len(X) - 2):
            idx1 = int((X[i] - new_min) / bin_width)
            idx2 = int((X[i + 2] - new_min) / bin_width)

            histogram[idx1][idx2] += v
            sumx[idx1] += v
            sumy[idx2] += v

        nsum = 0
        for i in range(5):
            for n in range(5):
                if histogram[i][n] > 0:
                    nsum += histogram[i][n] * np.log(
                        histogram[i][n] / sumx[i] / sumy[n]
                    )

        return nsum

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _IN_AutoMutualInfoStats_40_gaussian_fmmi(X_ac):
        # First minimum of the automutual information function.
        tau = int(min(40, np.ceil(len(X_ac) / 2)))

        ami = np.zeros(len(X_ac), dtype=np.float64)
        for i in range(tau):

            lag_size = len(X_ac) - (i + 1)
            y = X_ac[i + 1 :]
            nom = 0.0
            denomX = 0.0
            denomY = 0.0
            meanX = 0.0
            for j in range(lag_size):
                meanX += X_ac[j]
            meanX = meanX / lag_size
            meanY = np.mean(y)
            for j in range(lag_size):
                nom += (X_ac[j] - meanX) * (y[j] - meanY)
                denomX += (X_ac[j] - meanX) * (X_ac[j] - meanX)
                denomY += (y[j] - meanY) * (y[j] - meanY)
            divisor = np.sqrt(denomX * denomY)
            if divisor == 0:
                return np.nan
            ac = nom / np.sqrt(denomX * denomY)
            ami[i] = -0.5 * np.log(1 - np.power(ac, 2))

        for i in range(1, tau - 1):
            if ami[i] < ami[i - 1] and ami[i] < ami[i + 1]:
                return i
        return tau

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _MD_hrv_classic_pnn40(X):
        # Proportion of successive differences exceeding 0.04σ (Mietus 2002).
        diffs = np.zeros(len(X) - 1)
        for i in range(len(diffs)):
            diffs[i] = np.abs(X[i + 1] - X[i]) * 1000

        nsum = 0
        for diff in diffs:
            if diff > 40:
                nsum += 1

        return nsum / len(diffs)

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _SB_BinaryStats_mean_longstretch1(X, smean):
        # Longest period of consecutive values above the mean.
        mean_binary = np.zeros(len(X) - 1)
        for i in range(len(mean_binary)):
            if X[i] - smean > 0:
                mean_binary[i] = 1

        return _long_stretch(mean_binary, 1)

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _SB_MotifThree_quantile_hh(X):
        alphabet_size = 3
        yt = np.zeros(len(X), dtype=np.int32)
        _sb_coarsegrain(X, 3, yt)
        r1 = [np.zeros(len(X), np.int32) for i in range(alphabet_size)]
        sizes_r1 = np.zeros(alphabet_size, np.int32)
        for i in range(alphabet_size):
            r_idx = 0
            sizes_r1[i] = 0
            for j in range(len(X)):
                if yt[j] == i + 1:
                    r1[i][r_idx] = j
                    r_idx += 1
                    sizes_r1[i] += 1

        for i in range(alphabet_size):
            if sizes_r1[i] != 0 and r1[i][sizes_r1[i] - 1] == len(X) - 1:
                tmp_ar = np.zeros(sizes_r1[i], np.int32)
                # isn't this doing the same thing?
                for x in range(sizes_r1[i]):
                    tmp_ar[x] = r1[i][x]
                for y in range(sizes_r1[i] - 1):
                    r1[i][y] = tmp_ar[y]
                sizes_r1[i] -= 1

        r2 = [
            [np.zeros(len(X), np.int32) for j in range(alphabet_size)]
            for i in range(alphabet_size)
        ]
        sizes_r2 = [np.zeros(alphabet_size, np.int32) for i in range(alphabet_size)]
        out2 = [np.zeros(alphabet_size, np.float64) for i in range(alphabet_size)]

        for i in range(alphabet_size):
            for j in range(alphabet_size):
                sizes_r2[i][j] = 0
                dynamic_idx = 0
                for k in range(sizes_r1[i]):
                    tmp_idx = yt[r1[i][k] + 1]
                    if tmp_idx == j + 1:
                        r2[i][j][dynamic_idx] = r1[i][k]
                        dynamic_idx += 1
                        sizes_r2[i][j] += 1
                tmp = np.float64(sizes_r2[i][j]) / (np.float64(len(X)) - 1.0)
                out2[i][j] = tmp
        hh = 0.0
        for i in range(alphabet_size):
            f = 0.0
            for j in range(alphabet_size):
                if out2[i][j] > 0:
                    f += out2[i][j] * np.log(out2[i][j])
            hh += -1 * f
        return hh

    @staticmethod
    def _FC_LocalSimple_mean1_tauresrat(X, acfz):
        # Change in correlation length after iterative differencing.
        if len(X) < 2:
            return 0
        res = _local_simple_mean(X, 1)

        ac = _compute_autocorrelations(res)
        return _ac_first_zero(ac) / acfz

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _CO_Embed2_Dist_tau_d_expfit_meandiff(X, acfz):
        # Exponential fit to successive distances in 2-d embedding space.
        tau = acfz
        if tau > len(X) / 10:
            tau = int(len(X) / 10)
        d = np.zeros(len(X) - tau - 1)
        d_mean = 0
        for i in range(len(d)):
            n = np.sqrt(
                np.power(X[i + 1] - X[i], 2) + np.power(X[i + tau] - X[i + tau + 1], 2)
            )
            d[i] = n
            d_mean += n
        d_mean /= len(d)
        smin = np.min(d)
        smax = np.max(d)
        srange = smax - smin
        std = np.std(d)
        if std < 0.001:
            return 0
        num_bins = int(
            np.ceil(
                srange
                / (3.5 * _stddev(d, len(d)) / np.power(len(d), 0.3333333333333333))
            )
        )
        if num_bins == 0:
            return 0
        bin_width = srange / num_bins

        histogram = np.zeros(num_bins, dtype=np.int32)
        binEdges = np.zeros(num_bins + 1, dtype=np.float64)
        for val in d:
            idx = int((val - smin) / bin_width)
            if idx < 0:
                idx = 0
            if idx >= num_bins:
                idx = num_bins - 1
            histogram[idx] += 1

        for i in range(num_bins + 1):
            binEdges[i] = i * bin_width + smin

        histogramNormalise = np.zeros(num_bins, dtype=np.float64)
        for i in range(len(histogramNormalise)):
            histogramNormalise[i] = histogram[i] / len(d)

        d_exp_fit = np.zeros(num_bins, dtype=np.float64)
        for i in range(num_bins):
            expf = np.exp(-(binEdges[i] + binEdges[i + 1]) * 0.5 / d_mean) / d_mean
            if expf < 0:
                expf = 0

            d_exp_fit[i] = np.abs(histogramNormalise[i] - expf)

        return np.mean(d_exp_fit)

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _SC_FluctAnal_2_dfa_50_1_2_logi_prop_r1(X):
        # Proportion of slower timescale fluctuations that scale with DFA (50%
        # sampling).
        cs = np.zeros(int(len(X) / 2))
        cs[0] = X[0]
        for i in range(1, len(cs)):
            cs[i] = cs[i - 1] + X[i * 2]

        return _fluct_prop(cs, len(X), True)

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _SC_FluctAnal_2_rsrangefit_50_1_logi_prop_r1(X):
        # Proportion of slower timescale fluctuations that scale with linearly rescaled
        # range fits.
        cs = np.zeros(len(X))
        cs[0] = X[0]
        for i in range(1, len(X)):
            cs[i] = cs[i - 1] + X[i]

        return _fluct_prop(cs, len(X), False)

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _SB_TransitionMatrix_3ac_sumdiagcov(X, acfz):
        # Trace of covariance of transition matrix between symbols in 3-letter alphabet.
        ds = np.zeros(int(((len(X) - 1) / acfz) + 1), dtype=np.float64)
        for i in range(len(ds)):
            ds[i] = X[i * acfz]
        # swap to alphabet:
        yCG = np.zeros(len(ds), dtype=np.int32)
        _sb_coarsegrain(ds, 3, yCG)
        T = np.zeros((3, 3), dtype=np.float64)
        for i in range(len(ds) - 1):
            T[yCG[i] - 1][yCG[i + 1] - 1] += 1

        for i in range(3):
            for j in range(3):
                if (len(ds) - 1) == 0:
                    T[i][j] = np.nan
                else:
                    T[i][j] /= len(ds) - 1
        column1 = np.zeros(3, dtype=np.float64)
        column2 = np.zeros(3, dtype=np.float64)
        column3 = np.zeros(3, dtype=np.float64)

        for i in range(3):
            column1[i] = T[i][0]
            column2[i] = T[i][1]
            column3[i] = T[i][2]
        columns = np.zeros((3, 3), dtype=np.float64)
        columns[0] = column1
        columns[1] = column2
        columns[2] = column3

        # columns = [column1, column2, column3]
        cov_array = np.zeros((3, 3), dtype=np.float64)
        for i in range(3):
            for j in range(3):
                covTemp = 0
                meanX = np.mean(columns[i])
                meanY = np.mean(columns[j])
                for k in range(3):
                    covTemp += (columns[i][k] - meanX) * (columns[j][k] - meanY)
                covTemp = covTemp / 2
                cov_array[i][j] = covTemp
                cov_array[j][i] = covTemp

        sum_of_diagonal_cov = 0.0
        for i in range(3):
            sum_of_diagonal_cov += cov_array[i][i]

        return sum_of_diagonal_cov

    @staticmethod
    @njit(fastmath=True, cache=True)
    def _PD_PeriodicityWang_th0_01(X):
        # Periodicity measure of (Wang et al. 2007).
        y_spline = _spline_fit(X)

        y_sub = np.zeros(len(X))
        for i in range(len(X)):
            y_sub[i] = X[i] - y_spline[i]

        acmax = int(np.ceil(len(X) / 3.0))
        acf = np.zeros(acmax)
        for tau in range(1, acmax + 1):
            covariance = 0
            for i in range(len(X) - tau):
                covariance += y_sub[i] * y_sub[i + tau]
            acf[tau - 1] = covariance / (len(X) - tau)

        troughs = np.zeros(acmax, dtype=np.int32)
        peaks = np.zeros(acmax, dtype=np.int32)
        n_troughs = 0
        n_peaks = 0
        for i in range(1, acmax - 1):
            slope_in = acf[i] - acf[i - 1]
            slope_out = acf[i + 1] - acf[i]

            if slope_in < 0 and slope_out > 0:
                troughs[n_troughs] = i
                n_troughs += 1
            elif slope_in > 0 and slope_out < 0:
                peaks[n_peaks] = i
                n_peaks += 1

        out = 0
        for i in range(n_peaks):
            j = -1
            while troughs[j + 1] < peaks[i] and j + 1 < n_troughs:
                j += 1

            if j == -1 or acf[peaks[i]] - acf[troughs[j]] < 0.01 or acf[peaks[i]] < 0:
                continue

            out = peaks[i]
            break

        return out


@njit(fastmath=True, cache=True)
def _histogram_mode(X, num_bins, smin, smax):
    srange = smax - smin

    bin_width = srange / num_bins
    if bin_width == 0:
        return np.nan

    histogram = np.zeros(num_bins, dtype=np.int32)
    edges = np.zeros(num_bins + 1, dtype=np.float64)
    for val in X:
        idx = int((val - smin) / bin_width)
        if idx < 0:
            idx = 0
        if idx >= num_bins:
            idx = num_bins - 1
        histogram[idx] += 1

    for i in range(num_bins + 1):
        edges[i] = i * bin_width + smin

    max_count = 0
    num_maxs = 1
    max_sum = 0
    for i in range(num_bins):
        v = (edges[i] + edges[i + 1]) / 2
        if histogram[i] > max_count:
            max_count = histogram[i]
            num_maxs = 1
            max_sum = v
        elif histogram[i] == max_count:
            num_maxs += 1
            max_sum += v
    return max_sum / num_maxs


@njit(fastmath=True, cache=True)
def _long_stretch(X_binary, val):
    # look for the longest consecutive given value in an array
    last_val = 0
    max_stretch = 0
    for i in range(len(X_binary)):
        if X_binary[i] != val or i == len(X_binary) - 1:
            stretch = i - last_val
            if stretch > max_stretch:
                max_stretch = stretch
            last_val = i

    return max_stretch


@njit(fastmath=True, cache=True)
def _outlier_include(X):
    total = 0
    threshold = 0
    for v in X:
        if v >= 0:
            total += 1
            if v > threshold:
                threshold = v

    if threshold < 0.01:
        return 0

    num_thresholds = int(threshold / 0.01) + 1
    means = np.zeros(num_thresholds)
    dists = np.zeros(num_thresholds)
    medians = np.zeros(num_thresholds)
    for i in range(num_thresholds):
        d = i * 0.01

        count = 0
        r = np.zeros(len(X))
        for n in range(len(X)):
            if X[n] >= d:
                r[count] = n + 1
                count += 1

        if count == 0:
            continue

        diff = np.zeros(count - 1)
        for n in range(len(diff)):
            diff[n] = r[n + 1] - r[n]

        means[i] = np.mean(diff) if len(diff) > 0 else 9999999999
        dists[i] = len(diff) * 100 / total
        medians[i] = np.median(r[:count]) / (len(X) / 2) - 1

    mj = 0
    fbi = num_thresholds - 1
    for i in range(num_thresholds):
        if dists[i] > 2:
            mj = i
        if means[i] == 9999999999:
            fbi = num_thresholds - 1 - i

    trim_limit = max(mj, fbi)

    return np.median(medians[: trim_limit + 1])


def _autocorr(X, X_fft):
    ca = np.fft.ifft(_multiply_complex_arr(X_fft))
    return _get_acf(X, ca)


@njit(fastmath=True, cache=True)
def _multiply_complex_arr(X_fft):
    c = np.zeros(len(X_fft), dtype=np.complex128)
    for i, n in enumerate(X_fft):
        c[i] = n * (n.real + 1j * -n.imag)
    return c


@njit(fastmath=True, cache=True)
def _get_acf(X, ca):
    acf = np.zeros(len(X))
    if ca[0].real != 0:
        for i in range(len(X)):
            acf[i] = ca[i].real / ca[0].real
    return acf


@njit(fastmath=True, cache=True)
def _summaries_welch_rect(X, centroid, X_fft):
    new_length = int(len(X_fft) / 2) + 1
    p = np.zeros(new_length)
    pi2 = 2 * math.pi
    p[0] = (np.power(_complex_magnitude(X_fft[0]), 2) / len(X)) / pi2
    for i in range(1, new_length - 1):
        p[i] = ((np.power(_complex_magnitude(X_fft[i]), 2) / len(X)) * 2) / pi2
    p[new_length - 1] = (
        np.power(_complex_magnitude(X_fft[new_length - 1]), 2) / len(X)
    ) / pi2

    w = np.zeros(new_length)
    a = 1.0 / len(X_fft)
    for i in range(0, new_length):
        w[i] = i * a * math.pi * 2

    if centroid:
        cs = np.zeros(new_length)
        cs[0] = p[0]
        for i in range(1, new_length):
            cs[i] = cs[i - 1] + p[i]

        threshold = cs[new_length - 1] / 2
        for i in range(1, new_length):
            if cs[i] > threshold:
                return w[i]
        return np.nan
    else:
        tau = int(np.floor(new_length / 5))
        nsum = 0
        for i in range(tau):
            nsum += p[i]

        return nsum * (w[1] - w[0])


@njit(fastmath=True, cache=True)
def _complex_magnitude(c):
    return np.sqrt(c.real * c.real + c.imag * c.imag)


@njit(fastmath=True, cache=True)
def _local_simple_mean(X, train_length):
    res = np.zeros(len(X) - train_length)
    for i in range(len(res)):
        nsum = 0
        for n in range(train_length):
            nsum += X[i + n]
        res[i] = X[i + train_length] - nsum / train_length
    return res


@njit(fastmath=True, cache=True)
def _ac_first_zero(X_ac):
    for i in range(1, len(X_ac)):
        if X_ac[i] <= 0:
            return i

    return len(X_ac)


@njit(fastmath=True, cache=True)
def _fluct_prop(X, og_length, dfa):
    a = np.zeros(50, dtype=np.int_)
    a[0] = 5
    n_tau = 1
    smin = 1.6094379124341003  # Math.log(5);
    smax = np.log(og_length / 2)
    inc = (smax - smin) / 49
    for i in range(1, 50):
        val = int(np.round(np.exp(smin + inc * i) + 0.000000000001))
        if val != a[n_tau - 1]:
            a[n_tau] = val
            n_tau += 1

    if n_tau < 12:
        return np.nan

    f = np.zeros(n_tau)
    for i in range(n_tau):
        tau = a[i]
        buff_size = int(len(X) / tau)
        lag = 0
        if buff_size == 0:
            buff_size = 1
            lag = 1

        buffer = np.zeros((buff_size, tau))
        count = 0
        for n in range(buff_size):
            for j in range(tau - lag):
                buffer[n][j] = X[count]
                count += 1

        d = np.zeros(tau)
        for n in range(tau):
            d[n] = n + 1

        for n in range(buff_size):
            c1, c2 = _linear_regression(d, buffer[n], tau, 0)

            for j in range(tau):
                buffer[n][j] = buffer[n][j] - (c1 * (j + 1) + c2)

            if dfa:
                for j in range(tau):
                    f[i] += buffer[n][j] * buffer[n][j]
            else:
                f[i] += np.power(np.max(buffer[n]) - np.min(buffer[n]), 2)

        if dfa:
            f[i] = np.sqrt(f[i] / (buff_size * tau))
        else:
            f[i] = np.sqrt(f[i] / buff_size)

    log_a = np.zeros(n_tau)
    log_f = np.zeros(n_tau)
    for i in range(n_tau):
        log_a[i] = np.log(a[i])
        log_f[i] = np.log(f[i])

    sserr = np.zeros(n_tau - 11)
    for i in range(6, n_tau - 5):
        c1_1, c1_2 = _linear_regression(log_a, log_f, i, 0)
        c2_1, c2_2 = _linear_regression(log_a, log_f, n_tau - i + 1, i - 1)

        sum1 = 0
        for n in range(i):
            sum1 += np.power(log_a[n] * c1_1 + c1_2 - log_f[n], 2)
        sserr[i - 6] += np.sqrt(sum1)

        sum2 = 0
        for n in range(n_tau - i + 1):
            sum2 += np.power(log_a[n + i - 1] * c2_1 + c2_2 - log_f[n + i - 1], 2)
        sserr[i - 6] += np.sqrt(sum2)

    return (np.argmin(sserr) + 6) / n_tau


@njit(fastmath=True, cache=True)
def _linear_regression(X, y, n, lag):
    sumx = 0
    sumx2 = 0
    sumxy = 0
    sumy = 0
    for i in range(lag, n + lag):
        sumx += X[i]
        sumx2 += X[i] * X[i]
        sumxy += X[i] * y[i]
        sumy += y[i]

    denom = n * sumx2 - sumx * sumx
    if denom == 0:
        return 0, 0

    return (n * sumxy - sumx * sumy) / denom, (sumy * sumx2 - sumx * sumxy) / denom


@njit(fastmath=True, cache=True)
def _spline_fit(X):
    breaks = np.array([0, len(X) / 2 - 1, len(X) - 1])
    h0 = np.array([breaks[1] - breaks[0], breaks[2] - breaks[1]])
    h_copy = np.array([h0[0], h0[1], h0[0], h0[1]])
    hl = np.array([h_copy[3], h_copy[2], h_copy[1]])
    hr = np.array([h_copy[0], h_copy[1], h_copy[2]])

    hlCS = np.zeros(3)
    hlCS[0] = hl[0]
    for i in range(1, 3):
        hlCS[i] = hlCS[i - 1] + hl[i]

    bl = np.zeros(3)
    for i in range(3):
        bl[i] = breaks[0] - hlCS[i]

    hrCS = np.zeros(3)
    hrCS[0] = hr[0]
    for i in range(1, 3):
        hrCS[i] = hrCS[i - 1] + hr[i]

    br = np.zeros(3)
    for i in range(3):
        br[i] = breaks[2] - hrCS[i]

    breaksExt = np.zeros(9)
    for i in range(3):
        breaksExt[i] = bl[2 - i]
        breaksExt[i + 3] = breaks[i]
        breaksExt[i + 6] = br[i]

    hExt = np.zeros(8)
    for i in range(8):
        hExt[i] = breaksExt[i + 1] - breaksExt[i]

    coeffs = np.zeros((32, 4))
    for i in range(0, 32, 4):
        coeffs[i][0] = 1

    ii = np.zeros((4, 8), dtype=np.int32)
    for i in range(8):
        ii[0][i] = i
        ii[1][i] = min(1 + i, 7)
        ii[2][i] = min(2 + i, 7)
        ii[3][i] = min(3 + i, 7)

    H = np.zeros(32)
    for i in range(32):
        H[i] = hExt[ii[i % 4][int(i / 4)]]

    for k in range(1, 4):
        for j in range(k):
            for u in range(32):
                coeffs[u][j] *= H[u] / (k - j)

        Q = np.zeros((4, 8))
        for u in range(32):
            for m in range(4):
                Q[u % 4][int(u / 4)] += coeffs[u][m]

        for u in range(8):
            for m in range(1, 4):
                Q[m][u] += Q[m - 1][u]

        for u in range(32):
            if u % 4 > 0:
                coeffs[u][k] = Q[u % 4 - 1][int(u / 4)]

        fmax = np.zeros(32)
        for i in range(8):
            for j in range(4):
                fmax[i * 4 + j] = Q[3][i]

        for j in range(k + 1):
            for u in range(32):
                coeffs[u][j] /= fmax[u]

        for i in range(29):
            for j in range(k + 1):
                coeffs[i][j] -= coeffs[3 + i][j]

        for i in range(0, 32, 4):
            coeffs[i][k] = 0

    scale = np.ones(32)
    for k in range(3):
        for i in range(32):
            scale[i] /= H[i]

        for i in range(32):
            coeffs[i][3 - (k + 1)] *= scale[i]

    jj = np.zeros((4, 2), dtype=np.int32)
    for i in range(4):
        for j in range(2):
            if i == 0:
                jj[i][j] = 4 * (1 + j)
            else:
                jj[i][j] = 3

    for i in range(1, 4):
        for j in range(2):
            jj[i][j] += jj[i - 1][j]

    coeffs_out = np.zeros((8, 4))
    for i in range(8):
        coeffs_out[i] = coeffs[jj[i % 4][int(i / 4)] - 1]

    xsB = np.zeros(len(X) * 4)
    indexB = np.zeros(len(xsB), dtype=np.int32)
    breakInd = 1
    for i in range(len(X)):
        if i >= breaks[1] and breakInd < 2:
            breakInd += 1

        for j in range(4):
            xsB[i * 4 + j] = i - breaks[breakInd - 1]
            indexB[i * 4 + j] = j + (breakInd - 1) * 4

    vB = np.zeros(len(xsB))
    for i in range(len(xsB)):
        vB[i] = coeffs_out[indexB[i]][0]

    for i in range(1, 4):
        for j in range(len(xsB)):
            vB[j] = vB[j] * xsB[j] + coeffs_out[indexB[j]][i]

    A = np.zeros(len(X) * 5)
    breakInd = 0
    for i in range(len(xsB)):
        if i / 4 >= breaks[1]:
            breakInd = 1
        A[i % 4 + breakInd + int(i / 4) * 5] = vB[i]

    AT = np.zeros(len(A))
    ATA = np.zeros(25)
    ATb = np.zeros(5)
    for i in range(len(X)):
        for j in range(5):
            AT[j * len(X) + i] = A[i * 5 + j]

    for i in range(5):
        for j in range(5):
            for k in range(len(X)):
                ATA[i * 5 + j] += AT[i * len(X) + k] * A[k * 5 + j]

    for i in range(5):
        for k in range(len(X)):
            ATb[i] += AT[i * len(X) + k] * X[k]

    AElim = np.zeros((5, 5))
    for i in range(5):
        n = i * 5
        AElim[i] = ATA[n : n + 5]

    for i in range(5):
        for j in range(i + 1, 5):
            factor = AElim[j][i] / AElim[i][i]
            ATb[j] = ATb[j] - factor * ATb[i]

            for k in range(i, 5):
                AElim[j][k] = AElim[j][k] - factor * AElim[i][k]

    x = np.zeros(5)
    for i in range(4, -1, -1):
        bMinusATemp = ATb[i]
        for j in range(i + 1, 5):
            bMinusATemp -= x[j] * AElim[i][j]

        x[i] = bMinusATemp / AElim[i][i]

    C = np.zeros((5, 8))
    for i in range(32):
        C[int(i % 4 + int(i / 4) % 2)][int(i / 4)] = coeffs_out[i % 8][int(i / 8)]

    coeffs_spline = np.zeros((2, 4))
    for j in range(8):
        coefc = int(j / 2)
        coefr = j % 2
        for i in range(5):
            coeffs_spline[coefr][coefc] += C[i][j] * x[i]

    y_out = np.zeros(len(X))
    for i in range(len(X)):
        second_half = 0 if i < breaks[1] else 1
        y_out[i] = coeffs_spline[second_half][0]

    for i in range(1, 4):
        for j in range(len(X)):
            second_half = 0 if j < breaks[1] else 1
            y_out[j] = (
                y_out[j] * (j - breaks[1] * second_half) + coeffs_spline[second_half][i]
            )

    return y_out


def _verify_features(features, catch24):
    if isinstance(features, str):
        if features == "all":
            f_idx = [i for i in range(22)]
            if catch24:
                f_idx += [22, 23]
        elif features in feature_names_short:
            f_idx = [feature_names_short.index(features)]
        elif features in feature_names:
            f_idx = [feature_names.index(features)]
        elif catch24 and features == "Mean":
            f_idx = [22]
        elif catch24 and features == "StandardDeviation":
            f_idx = [23]
        else:
            raise ValueError("Invalid feature selection.")
    elif isinstance(features, int):
        if features >= 0 and features < 22:
            f_idx = [features]
        elif catch24 and features == 22:
            f_idx = [22]
        elif catch24 and features == 23:
            f_idx = [23]
        else:
            raise ValueError("Invalid feature selection.")
    elif isinstance(features, (list, tuple)):
        if len(features) > 0:
            f_idx = []
            for f in features:
                if isinstance(f, str):
                    if f in feature_names_short:
                        f_idx.append(feature_names_short.index(f))
                    elif f in feature_names:
                        f_idx.append(feature_names.index(f))
                    elif catch24 and f == "Mean":
                        f_idx.append(22)
                    elif catch24 and f == "StandardDeviation":
                        f_idx.append(23)
                    else:
                        raise ValueError("Invalid feature selection.")
                elif isinstance(f, int):
                    if f >= 0 and f < 22:
                        f_idx.append(f)
                    elif catch24 and f == 22:
                        f_idx.append(22)
                    elif catch24 and f == 23:
                        f_idx.append(23)
                    else:
                        raise ValueError("Invalid feature selection.")
                else:
                    raise ValueError("Invalid feature selection.")
        else:
            raise ValueError("Invalid feature selection.")
    else:
        raise ValueError("Invalid feature selection.")

    return f_idx


@njit(fastmath=True, cache=True)
def _compute_autocorrelations(X):
    mean = np.mean(X)
    nFFT = int(np.log2(len(X)))
    if 2**nFFT == len(X):
        nFFT = len(X) * 2
    else:
        nFFT = (2 ** (nFFT + 1)) * 2
    F = np.zeros(nFFT * 2, dtype=np.complex128)
    for i in range(len(X)):
        F[i] = complex(X[i] - mean, 0.0)
    for i in range(len(X), nFFT):
        F[i] = complex(0.0, 0.0)
    tw = np.zeros(nFFT * 2, dtype=np.complex128)
    # twiddles
    PI = np.pi
    for i in range(nFFT):
        tmp = 0.0 - PI * i / nFFT * 1j
        tw[i] = np.exp(tmp)
    F = _fft(F, tw)
    # dot multiply
    F = np.multiply(F, np.conj(F))
    F = _fft(F, tw)
    divisor = F[0]
    if np.real(divisor) == 0 and np.imag(divisor) == 0:
        return np.zeros(nFFT * 2, dtype=np.float64)
    F = F / divisor
    out = np.real(F)
    return out


@njit(fastmath=True, cache=True)
def _fft(a, tw):
    n = a.shape[0]
    log_n = int(np.log2(n))
    out = np.empty_like(a)

    # Bit-reversed addressing permutation
    for i in range(n):
        j = 0
        for k in range(log_n):
            j = (j << 1) | ((i >> k) & 1)
        out[j] = a[i]

    # Iterative FFT computation
    step = 1
    while step < n:
        halfstep = step
        step = 2 * step
        for i in range(0, n, step):
            for j in range(halfstep):
                t = tw[j * (n // step)] * out[i + j + halfstep]
                u = out[i + j]
                out[i + j] = u + t
                out[i + j + halfstep] = u - t

    return out


@njit(fastmath=True, cache=True)
def _stddev(a, size):
    m = np.mean(a[:size])
    sd = np.sqrt(np.sum((a[:size] - m) ** 2) / (size - 1))
    return sd


@njit(fastmath=True, cache=True)
def _sb_coarsegrain(y, num_groups, labels):
    th = np.zeros((num_groups + 1), dtype=np.float64)
    ls = np.zeros((num_groups + 1), dtype=np.float64)
    # linspace
    step_size = 1 / (num_groups)
    start = 0
    for i in range(num_groups + 1):
        ls[i] = start
        start += step_size
    for i in range(num_groups + 1):
        th[i] = _quantile(y, ls[i])
    th[0] -= 1
    for i in range(num_groups):
        for j in range(len(y)):
            if y[j] > th[i] and y[j] <= th[i + 1]:
                labels[j] = i + 1


@njit(fastmath=True, cache=True)
def _quantile(X, quant):
    tmp = np.sort(X)
    q = 0.5 / len(X)
    if quant < q:
        value = tmp[0]
        return value
    elif quant > (1 - q):
        value = tmp[len(X) - 1]
        return value

    quant_idx = len(X) * quant - 0.5
    idx_left = int(np.floor(quant_idx))
    idx_right = int(np.ceil(quant_idx))
    value = tmp[idx_left] + (quant_idx - idx_left) * (
        tmp[idx_right] - tmp[idx_left]
    ) / (idx_right - idx_left)
    return value
