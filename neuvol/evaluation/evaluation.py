# Copyright 2018 Timur Sokhin.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import time

import keras.backend as K
from keras.callbacks import EarlyStopping
import numpy as np
from sklearn.metrics import auc, roc_curve
from sklearn.metrics import (f1_score)
from sklearn.model_selection import StratifiedKFold
import tensorflow as tf

from ..data import Data
from ..data import DataGenerator


class Evaluator():
    """
    Train network and evaluate
    All these parameters - metaparameters of training
    Set it before you start if you want
    """

    def __init__(self, x, y, kfold_number=5, device='cpu', generator=False):
        """
        device available value:
            - gpu
            - cpu
        """
        self._x = np.array(x)
        self._y = np.array(y)
        self._kfold_number = kfold_number

        if device == 'cpu':
            self._device = '/device:CPU:0'
        elif device == 'gpu':
            self._device = '/device:GPU:0'
        else:
            raise ValueError("Incorrect \"device\" argument."
                             "Available values: \"gpu\", \"cpu\"")
        self._generator = generator
        self._create_tokens = True

        self._use_multiprocessing = True
        self._workers = 2
        self._early_stopping = {
            'min_delta': 0.005,
            'patience': 5}
        self._verbose = 0
        self._fitness_measure = 'AUC'

    @property
    def early_stopping_min_delta(self):
        return self._early_stopping['min_delta']

    @property
    def early_stopping_patience(self):
        return self._early_stopping['patience']

    @property
    def create_tokens(self):
        return self._create_tokens

    @property
    def verbose(self):
        return self._verbose

    @property
    def fitness_measure(self):
        return self._fitness_measure

    @property
    def device(self):
        return self._device

    @early_stopping_min_delta.setter
    def early_stopping_min_delta(self, min_delta):
        """
        Set early stopping parameters for training
        Please, be careful
        """
        self._early_stopping['min_delta'] = min_delta

    @early_stopping_patience.setter
    def early_stopping_patience(self, patience):
        """
        Set early stopping parameters for training
        Please, be careful
        """
        self._early_stopping['patience'] = patience

    @create_tokens.setter
    def create_tokens(self, create_tokens):
        """
        Set create tokens False or True,
        if False, prepare data in form of sequences of numeric values
        """
        self._create_tokens = create_tokens

    @verbose.setter
    def verbose(self, verbose):
        """
        Set verbose level, dont touch it, with large amount of individs the number
        of info messages will be too large
        """
        self._verbose = verbose

    @fitness_measure.setter
    def fitness_measure(self, fitness_measure):
        """
        Set fitness measure - This parameter determines the criterion
        for the effectiveness of the model
        measure available values:
            - AUC
            - f1
        """
        self._fitness_measure = fitness_measure

    @device.setter
    def device(self, device):
        """
        Manualy device management
        device: str cpu or gpu
        """
        self._device = device

        if device == 'cpu':
            self._device = '/device:CPU:0'
        elif device == 'gpu':
            self._device = '/device:GPU:0'
        else:
            raise ValueError("Incorrect \"device\" argument."
                             "Available values: \"gpu\", \"cpu\"")

    def set_DataGenerator_multiproc(self, use_multiprocessing=True, workers=2):
        """
        Set multiprocessing parameters for data generator
        """
        self._use_multiprocessing = use_multiprocessing
        self._workers = workers

    def fit(self, network):
        """
        Training function. N steps of cross-validation
        """
        training_time = time.time()
        predicted_out = []
        real_out = []

        data = Data(
            self._x,
            self._y,
            data_type=network.data_type,
            task_type=network.task_type,
            data_processing=network.data_processing,
            create_tokens=self._create_tokens)

        x, y = data.process_data()

        if self._kfold_number != 1:
            kfold = StratifiedKFold(n_splits=self._kfold_number)
            kfold_generator = kfold.split(np.zeros(self._x.shape), y.argmax(-1))
        else:
            # create list of indexes
            # to work without cross-validation and avoid code duplication
            # we imitate kfold behaviour and return two lists of indexes
            kfold_generator = [[list(range(self._x.shape[0]))] * 2]

        for train, test in kfold_generator:
            # work only with this device
            with tf.device(self._device):
                try:
                    nn, optimizer, loss = network.init_tf_graph()
                    nn.compile(optimizer=optimizer, loss=loss, metrics=['accuracy'])

                    early_stopping = EarlyStopping(
                        monitor='val_loss',
                        min_delta=self._early_stopping['min_delta'],
                        patience=self._early_stopping['patience'],
                        mode='auto',
                        verbose=self._verbose)
                    callbacks = [early_stopping]
                    nn.fit(
                        x[train], y[train],
                        batch_size=network.training_parameters['batchs'],
                        epochs=network.training_parameters['epochs'],
                        validation_data=(x[test], y[test]),
                        callbacks=callbacks,
                        shuffle=True,
                        verbose=self._verbose)

                    predicted = nn.predict(x[test])
                    real = y[test]

                    predicted_out.extend(predicted)
                    real_out.extend(real)
                except Exception:
                    if self._verbose == 1:
                        print('Tensor could not be compiled')
                    raise ArithmeticError('Tensor could not be compiled')

            tf.reset_default_graph()

            K.clear_session()

        training_time -= time.time()

        if network.task_type == 'classification':
            result = self.test_classification(predicted_out, real_out, network.options['classes'])

        return result

    def fit_generator(self, network):
        """
        Training function with generators. N steps of cross-validation
        """
        training_time = time.time()
        predicted_out = []
        real_out = []

        if self._kfold_number != 1:
            kfold = StratifiedKFold(n_splits=self._kfold_number)
            kfold_generator = kfold.split(np.zeros(len(self._x)), np.zeros(len(self._y)))
        else:
            # create list of indexes
            # to work without cross-validation and avoid code duplication
            # we imitate kfold behaviour and return two lists of indexes
            kfold_generator = [[list(range(self._x.shape[0]))] * 2]

        for train, test in kfold_generator:
            train_generator = DataGenerator(
                self._x[train],
                self._y[train],
                data_type=network.data_type,
                task_type=network.task_type,
                data_processing=network.data_processing,
                create_tokens=self._create_tokens)

            test_generator = DataGenerator(
                self._x[test],
                self._y[test],
                data_type=network.data_type,
                task_type=network.task_type,
                data_processing=network.data_processing,
                create_tokens=self._create_tokens)

            # work only with this device
            with tf.device(self._device):
                nn, optimizer, loss = network.init_tf_graph()
                nn.compile(optimizer=optimizer, loss=loss, metrics=['accuracy'])

                early_stopping = EarlyStopping(
                    monitor='val_loss',
                    min_delta=self._early_stopping['min_delta'],
                    patience=self._early_stopping['patience'],
                    mode='auto',
                    verbose=False)
                callbacks = [early_stopping]

                nn.fit_generator(
                    generator=train_generator,
                    epochs=network.training_parameters['epochs'],
                    verbose=self._verbose,
                    callbacks=callbacks,
                    validation_data=test_generator,
                    workers=self._workers,
                    use_multiprocessing=self._use_multiprocessing)

                predicted = nn.predict_generator(
                    test_generator,
                    workers=self._workers,
                    use_multiprocessing=self._use_multiprocessing)

                # TODO: Generator should work with pointers to files,
                # TODO: so, self._y and self._x will be a list of file names in future
                real = self._y[test]

                predicted_out.extend(predicted)
                real_out.extend(real)

            tf.reset_default_graph()

            K.clear_session()

        training_time -= time.time()

        if network.task_type == 'classification':
            result = self.test_classification(predicted_out, real_out, network.options['classes'])

        return result

    def test_classification(self, predicted_out, real_out, classes):
        """
        Return fitness results
        """
        if self._fitness_measure == 'f1':
            predicted = np.array(predicted_out).argmax(-1)
            real = np.array(real_out).argmax(-1)

            f1 = f1_score(real, predicted, average=None)
            # precision = precision_score(real, predicted, average=None)
            # recall = recall_score(real, predicted, average=None)
            # accuracy = accuracy_score(real, predicted)
            return np.sum(f1)

        elif self._fitness_measure == 'AUC':
            fpr = dict()
            tpr = dict()
            roc_auc = []
            # real_out[np.isnan(real_out)] = 0
            # predicted_out[np.isnan(predicted_out)] = 0

            # real_out[np.isinf(real_out)] = 0
            # predicted_out[np.isinf(predicted_out)] = 0

            for i in range(classes):
                try:
                    fpr[i], tpr[i], _ = roc_curve(np.array(real_out)[:, i], np.array(predicted_out)[:, i])
                except Exception as e:
                    print('AUC error', e)
                    fpr[i], tpr[i] = np.zeros(len(real_out)), np.zeros(len(predicted_out))
                roc_auc.append(auc(fpr[i], tpr[i]))

            return np.sum(roc_auc)

        else:
            raise TypeError('Unrecognized fitness measure')
