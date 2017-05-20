"""
A collection of models we'll use to attempt to classify videos.
"""
from keras.layers import Dense, Flatten, Dropout, Reshape, Input, ZeroPadding3D
from keras.layers.recurrent import LSTM
from keras.models import Sequential, load_model, model_from_json
from keras.optimizers import Adam, RMSprop
from keras.layers.wrappers import TimeDistributed
from keras.layers.convolutional import (Conv2D, MaxPooling3D, Conv3D,
    MaxPooling2D)
from collections import deque
import sys

class ResearchModels():
    def __init__(self, nb_classes, model, seq_length,
                 saved_model=None, features_length=2048):
        """
        `model` = one of:
            lstm
            lcrn
            mlp
            conv_3d
        `nb_classes` = the number of classes to predict
        `seq_length` = the length of our video sequences
        `saved_model` = the path to a saved Keras model to load
        """

        # Set defaults.
        self.seq_length = seq_length
        self.load_model = load_model
        self.saved_model = saved_model
        self.nb_classes = nb_classes
        self.feature_queue = deque()

        # Set the metrics. Only use top k if there's a need.
        metrics = ['accuracy']
        if self.nb_classes >= 10:
            metrics.append('top_k_categorical_accuracy')

        # Get the appropriate model.
        if self.saved_model is not None:
            print("Loading model %s" % self.saved_model)
            self.model = load_model(self.saved_model)
        elif model == 'lstm':
            print("Loading LSTM model.")
            self.input_shape = (seq_length, features_length)
            self.model = self.lstm()
        elif model == 'lrcn':
            print("Loading CNN-LSTM model.")
            self.input_shape = (seq_length, 150, 150, 3)
            self.model = self.lrcn()
        elif model == 'mlp':
            print("Loading simple MLP.")
            self.input_shape = features_length * seq_length
            self.model = self.mlp()
        elif model == 'conv_3d':
            print("Loading Conv3D")
            self.input_shape = (seq_length, 112, 112, 3)
            self.model = self.conv_3d()
        elif model == 'stateful_lrcn':
            print("Loading stateful LRCN")
            self.input_shape = (150, 150, 3)
            self.model = self.stateful_lrcn()
        else:
            print("Unknown network.")
            sys.exit()

        # Now compile the network.
        optimizer = Adam(decay=1e-6)
        self.model.compile(loss='categorical_crossentropy', optimizer=optimizer,
                           metrics=metrics)

        print(self.model.summary())

    def lrcn(self):
        """Build a CNN into RNN.
        Starting version from:
            https://github.com/udacity/self-driving-car/blob/master/
                steering-models/community-models/chauffeur/models.py

        Heavily influenced by VGG-16:
            https://arxiv.org/abs/1409.1556

        Also known as an LRCN:
            https://arxiv.org/pdf/1411.4389.pdf
        """
        model = Sequential()

        model.add(TimeDistributed(Conv2D(32, (7, 7), strides=(2, 2),
            activation='relu', padding='same'), input_shape=self.input_shape))
        model.add(TimeDistributed(Conv2D(32, (3,3),
            kernel_initializer="he_normal", activation='relu')))
        model.add(TimeDistributed(MaxPooling2D((2, 2), strides=(2, 2))))

        model.add(TimeDistributed(Conv2D(64, (3,3),
            padding='same', activation='relu')))
        model.add(TimeDistributed(Conv2D(64, (3,3),
            padding='same', activation='relu')))
        model.add(TimeDistributed(MaxPooling2D((2, 2), strides=(2, 2))))

        model.add(TimeDistributed(Conv2D(128, (3,3),
            padding='same', activation='relu')))
        model.add(TimeDistributed(Conv2D(128, (3,3),
            padding='same', activation='relu')))
        model.add(TimeDistributed(MaxPooling2D((2, 2), strides=(2, 2))))

        model.add(TimeDistributed(Conv2D(256, (3,3),
            padding='same', activation='relu')))
        model.add(TimeDistributed(Conv2D(256, (3,3),
            padding='same', activation='relu')))
        model.add(TimeDistributed(MaxPooling2D((2, 2), strides=(2, 2))))
        
        model.add(TimeDistributed(Conv2D(512, (3,3),
            padding='same', activation='relu')))
        model.add(TimeDistributed(Conv2D(512, (3,3),
            padding='same', activation='relu')))
        model.add(TimeDistributed(MaxPooling2D((2, 2), strides=(2, 2))))

        model.add(TimeDistributed(Flatten()))

        model.add(Dropout(0.9))
        model.add(LSTM(256, return_sequences=False, dropout=0.9))
        model.add(Dense(self.nb_classes, activation='softmax'))

        return model

    def conv_3d(self):
        """
        Build a 3D convolutional network, aka C3D.
            https://arxiv.org/pdf/1412.0767.pdf

        With thanks:
            https://gist.github.com/albertomontesg/d8b21a179c1e6cca0480ebdf292c34d2
        """

        model = Sequential()
        # 1st layer group
        model.add(Conv3D(64, 3, 3, 3, activation='relu', 
                                border_mode='same', name='conv1',
                                subsample=(1, 1, 1), 
                                input_shape=self.input_shape))
        model.add(MaxPooling3D(pool_size=(1, 2, 2), strides=(1, 2, 2), 
                               border_mode='valid', name='pool1'))
        # 2nd layer group
        model.add(Conv3D(128, 3, 3, 3, activation='relu', 
                                border_mode='same', name='conv2',
                                subsample=(1, 1, 1)))
        model.add(MaxPooling3D(pool_size=(2, 2, 2), strides=(2, 2, 2), 
                               border_mode='valid', name='pool2'))
        # 3rd layer group
        model.add(Conv3D(256, 3, 3, 3, activation='relu', 
                                border_mode='same', name='conv3a',
                                subsample=(1, 1, 1)))
        model.add(Conv3D(256, 3, 3, 3, activation='relu', 
                                border_mode='same', name='conv3b',
                                subsample=(1, 1, 1)))
        model.add(MaxPooling3D(pool_size=(2, 2, 2), strides=(2, 2, 2), 
                               border_mode='valid', name='pool3'))
        # 4th layer group
        model.add(Conv3D(512, 3, 3, 3, activation='relu', 
                                border_mode='same', name='conv4a',
                                subsample=(1, 1, 1)))
        model.add(Conv3D(512, 3, 3, 3, activation='relu', 
                                border_mode='same', name='conv4b',
                                subsample=(1, 1, 1)))
        model.add(MaxPooling3D(pool_size=(2, 2, 2), strides=(2, 2, 2), 
                               border_mode='valid', name='pool4'))
        # 5th layer group
        model.add(Conv3D(512, 3, 3, 3, activation='relu', 
                                border_mode='same', name='conv5a',
                                subsample=(1, 1, 1)))
        model.add(Conv3D(512, 3, 3, 3, activation='relu', 
                                border_mode='same', name='conv5b',
                                subsample=(1, 1, 1)))
        model.add(ZeroPadding3D(padding=(0, 1, 1)))
        model.add(MaxPooling3D(pool_size=(2, 2, 2), strides=(2, 2, 2), 
                               border_mode='valid', name='pool5'))
        model.add(Flatten())

        # FC layers group
        model.add(Dense(4096, activation='relu', name='fc6'))
        model.add(Dropout(.5))
        model.add(Dense(4096, activation='relu', name='fc7'))
        model.add(Dropout(.5))
        model.add(Dense(self.nb_classes, activation='softmax'))

        # Load weights by name. We use by name to only load weights for
        # layers that match. For layers we don't want to load weights for,
        # we rename the layers above.
        print("Loading weights from sports1M.")
        model.load_weights('data/c3d/models/sports1M_weights_tf.h5', by_name=True)

        return model

    def stateful_lrcn(self):
        """Build a CNN into RNN using single frames and a stateful RNN.

        This will require we use a sequence size of 1 and manage the state
        manually. The goal of this setup is to allow us to use a much larger
        CNN (like VGG16) and pretrained weights. We do this instead of
        Time Distributed in an effort to combat our major GPU memory
        constraints.

        Uses VGG-16:
            https://arxiv.org/abs/1409.1556

        This architecture is also known as an LRCN:
            https://arxiv.org/pdf/1411.4389.pdf
        """
        from keras.applications.vgg16 import VGG16
        from keras.models import Model

        base_model = VGG16(weights='imagenet', include_top=False,
                           input_shape=self.input_shape)
        x = base_model.output

        # Maybe?
        # x = GlobalAveragePooling2D()(x)

        x = Flatten()(x)

        # Turn the CNN output into a "sequence" of length 1
        x = Reshape((1, -1))(x)  

        # Add the LSTM.
        x = LSTM(256, batch_input_shape=(1, 1, -1), stateful=True, dropout=0.9)(x)

        predictions = Dense(self.nb_classes, activation='softmax')(x)

        model = Model(inputs=base_model.input, outputs=predictions)

        return model

