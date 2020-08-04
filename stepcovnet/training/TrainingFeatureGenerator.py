from collections import defaultdict

import numpy as np

from stepcovnet.common.utils import apply_scalers
from stepcovnet.common.utils import get_ngram


class TrainingFeatureGenerator(object):
    def __init__(self, dataset, batch_size, indexes, num_samples, lookback=1, scalers=None):
        self.dataset = dataset
        self.train_indexes = indexes
        self.num_samples = num_samples
        self.scalers = scalers
        self.lookback = lookback
        self.batch_size = batch_size

    def __len__(self):
        return int(np.ceil(len(self.num_samples) / self.batch_size))

    def __call__(self, *args, **kwargs):
        with self.dataset as dataset:
            while True:
                features = defaultdict(np.array)
                y_batch = np.array([])
                sample_weights_batch = np.array([])
                for song_index in self.train_indexes:
                    song_start_index, song_end_index = dataset.song_index_ranges[song_index]
                    start_index = song_start_index
                    while start_index < song_end_index:
                        end_index = min(start_index + self.batch_size, song_end_index)
                        arrow_features, arrow_mask = self.get_samples_ngram_with_mask(dataset.label_encoded_arrows,
                                                                                      start_index, end_index)
                        audio_features, _ = self.get_samples_ngram_with_mask(dataset.features,
                                                                             start_index, end_index, squeeze=False)
                        # Lookback data from ngram returns empty value in index 0. Also, arrow features should only 
                        # contain previously seen features. Therefore, removing last element and last lookback from 
                        # arrows features and first element from audio features.
                        features["arrow_features"] = np.append(features["arrow_features"],
                                                               arrow_features[:-1, 1:], axis=0)
                        features["arrow_mask"] = np.append(features["arrow_mask"], arrow_mask[:-1, 1:], axis=0)
                        features["audio_features"] = np.append(features["audio_features"], audio_features[1:], axis=0)
                        y_batch = np.append(y_batch, dataset.binary_encoded_arrows[start_index: end_index])
                        sample_weights_batch = np.append(sample_weights_batch,
                                                         dataset.sample_weights[start_index: end_index])
                        if len(y_batch) >= self.batch_size:
                            scaled_audio_features = apply_scalers(features=features["audio_features"],
                                                                  scalers=self.scalers)
                            x_batch = [features["arrow_features"], features["arrow_mask"], scaled_audio_features]
                            yield x_batch, y_batch, sample_weights_batch
                            features.clear()
                            y_batch = np.array([])
                            sample_weights_batch = np.array([])
                        start_index = end_index

    def get_samples_ngram_with_mask(self, dataset, start_index, end_index, squeeze=True):
        samples = dataset[start_index:start_index + end_index]

        ngram_samples = get_ngram(samples.reshape(-1, 1), self.lookback)
        mask = np.zeros((samples.shape[0], 1), dtype=int)
        ngram_mask = get_ngram(mask, self.lookback, padding_value=1)

        if squeeze:
            ngram_samples = np.squeeze(ngram_samples)
        ngram_mask = np.squeeze(ngram_mask)

        return ngram_samples, ngram_mask
