
import logging
import sys
import numpy as np
from keras.models import Model
from keras.layers import Input, Activation, add, Dense, Flatten, Dropout
from keras.layers.convolutional import Conv2D, AveragePooling2D
from keras.layers.normalization import BatchNormalization
from keras.regularizers import l2
from keras import backend as K
from tensorflow.keras.models import Sequential 

sys.setrecursionlimit(2 ** 20)
np.random.seed(2 ** 10)


class NeuralNetwork:
    def __init__(self, areaOfImage, height=16, k=8):
        self._height = height
        self._k = k
        self._dropout_probability = 0
        self._weight_decay = 0.0005
        self._use_bias = False
        self._weight_init = "normal"
                                           
        if K.image_data_format() == "th":
            logging.debug("image_dim_ordering = 'th'")
            self.lineOfChannel = 1
            self.inputSides = (3, areaOfImage, areaOfImage)
        else:
            logging.debug("image_dim_ordering = 'tf'")
            self.lineOfChannel = -1
            self.inputSides = (areaOfImage, areaOfImage, 3)

    # Wide residual network 
    def _wide_basic(self, areaOfInput, areaOfOutput, stride):
        def f(net):

            conv_params = [[3, 3, stride, "same"],
                           [3, 3, (1, 1), "same"]]

            n_bottleneck_plane = areaOfOutput

            # Residual block
            for i, v in enumerate(conv_params):
                if i == 0:
                    if areaOfInput != areaOfOutput:
                        net = BatchNormalization(axis=self.lineOfChannel)(net)
                        net = Activation("relu")(net)
                        convs = net
                    else:
                        convs = BatchNormalization(axis=self.lineOfChannel)(net)
                        convs = Activation("relu")(convs)

                    convs = Conv2D(n_bottleneck_plane, kernel_size=(v[0], v[1]),
                                          strides=v[2],
                                          padding=v[3],
                                          kernel_initializer=self._weight_init,
                                          kernel_regularizer=l2(self._weight_decay),
                                          use_bias=self._use_bias)(convs)
                else:
                    convs = BatchNormalization(axis=self.lineOfChannel)(convs)
                    convs = Activation("relu")(convs)
                    if self._dropout_probability > 0:
                        convs = Dropout(self._dropout_probability)(convs)
                    convs = Conv2D(n_bottleneck_plane, kernel_size=(v[0], v[1]),
                                          strides=v[2],
                                          padding=v[3],
                                          kernel_initializer=self._weight_init,
                                          kernel_regularizer=l2(self._weight_decay),
                                          use_bias=self._use_bias)(convs)

            if areaOfInput != areaOfOutput:
                shortcut = Conv2D(areaOfOutput, kernel_size=(1, 1),
                                         strides=stride,
                                         padding="same",
                                         kernel_initializer=self._weight_init,
                                         kernel_regularizer=l2(self._weight_decay),
                                         use_bias=self._use_bias)(net)
            else:
                shortcut = net

            return add([convs, shortcut])

        return f


    # Stacking Residual Units 
    def _layer(self, block, areaOfInput, areaOfOutput, count, stride):
        def f(net):
            net = block(areaOfInput, areaOfOutput, stride)(net)
            for i in range(2, int(count + 1)):
                net = block(areaOfOutput, areaOfOutput, stride=(1, 1))(net)
            return net

        return f


    def __call__(self):
        logging.debug("Creating model...")

        assert ((self._height - 4) % 6 == 0)
        n = (self._height - 4) / 6

        inputs = Input(shape=self.inputSides)

        n_stages = [16, 16 * self._k, 32 * self._k, 64 * self._k]

        conv1 = Conv2D(filters=n_stages[0], kernel_size=(3, 3),
                              strides=(1, 1),
                              padding="same",
                              kernel_initializer=self._weight_init,
                              kernel_regularizer=l2(self._weight_decay),
                              use_bias=self._use_bias)(inputs)  
        # Adding  wide residual blocks
        block_fn = self._wide_basic
        conv2 = self._layer(block_fn, areaOfInput=n_stages[0], areaOfOutput=n_stages[1], count=n, stride=(1, 1))(conv1)
        conv3 = self._layer(block_fn, areaOfInput=n_stages[1], areaOfOutput=n_stages[2], count=n, stride=(2, 2))(conv2)
        conv4 = self._layer(block_fn, areaOfInput=n_stages[2], areaOfOutput=n_stages[3], count=n, stride=(2, 2))(conv3)
        batch_norm = BatchNormalization(axis=self.lineOfChannel)(conv4)
        relu = Activation("relu")(batch_norm)

        # Code for Classifier block
        pool = AveragePooling2D(pool_size=(8, 8), strides=(1, 1), padding="same")(relu)
        flatten = Flatten()(pool)
        predictions_g = Dense(units=2, kernel_initializer=self._weight_init, use_bias=self._use_bias,
                              kernel_regularizer=l2(self._weight_decay), activation="softmax")(flatten)
        predictions_a = Dense(units=101, kernel_initializer=self._weight_init, use_bias=self._use_bias,
                              kernel_regularizer=l2(self._weight_decay), activation="softmax")(flatten)

        model = Model(inputs=inputs, outputs=[predictions_g, predictions_a])

        return model

