'''
funkcija za RNN  model:
stavljaju se nekolko stacked RNN layera



'''
# osnovne biblioteke
import numpy as np
import pandas as pd
import math


# set to run on CPU


# Early stopping
from keras.callbacks import EarlyStopping
from keras import layers

# Evaluation
from sklearn import metrics

# import funkcije za evaluaciju modela
from utilities.LSTMEvaluateEucledian import *

# iz load data za scaling
from utilities.load_dataset import *

import warnings

import os


class LSTMFunction:

    def __init__(self, trainGenerator, testGenerator, y_test, y_test_denorm, D, no_inputs, no_targets, lags, intParams, bounds,
                 early_stop=False, target=None, scaler=None, norm_metrics=True,valGenerator=None):
        # vremenske serije, TimeSeries generator sa train,val i test data
        self.trainGenerator = trainGenerator
        self.valGenerator = valGenerator
        self.testGenerator = testGenerator

        # potreban je i test dasta u obicnoj formi za evaluaciju, ovo je normalizovani test
        self.y_test = y_test

        # ovo je denormalizovani test ako hocemo denormalizovane metrike
        self.y_test_denorm = y_test_denorm

        # broj prametara resenja
        self.D = D

        # ovo je za scaler ako hocemo metrike kao denormalizovane kasnije
        # medjutim, scaler se ucitava iz load_datasetmulti i nema potrebe, pa je zato
        # u konstruktoru None
        self.scaler = scaler

        # da li zelimo da vratimo normalizovane metrike ili denormalizovane
        self.norm_metrics = norm_metrics

        # ovo je broj input features
        self.no_inputs = no_inputs

        #ovo je broj target features

        self.no_targets = no_targets

        # broj lagova, koliko imamo lagova, kod univariate, input mreze je
        # shape-a  [broj_lagova,1], npr. [6,1]
        self.lags = lags



        # lista sa pozicijama parametara metaheuristike, gde su parametri int
        self.intParams = intParams

        # dictionary sa granicama vrednosti parametara

        self.bounds = bounds

        # inicijalizujemo early_stop

        self.early_stop = early_stop

        # postavjanje niza sa granicama vrednosti parametara
        # D je ukupna duzina niza i prosledjuje se iz glavnog koda

        self.ub = [None] * self.D
        self.lb = [None] * self.D
        self.name = "RNN Function"

        # imamo samo jedan parametar za pocetak, a to je broj neurona u sloju

        '''
        parametri:
        ideja je da prvi idu real parametri, pa posle integer, da bi bilo lakse za razumevanje
        [0] - learning rate 
        [1] - dropout rate za dropout layer koji ide na kraju 
        [2]  - number of training epochs
        [3] - number of layers
        [4] - number of neurons in layers
        [5] - isto kao number of neurons in layers 
        [6] - isto kao number of neurons in layers 
        [7] - ... ovde zavisi koliko ima parametara odmax number of layers. ako je max number of layers=n, onda svi od [4] pa nadalje su isti boundaries
              na primer ako je max number of layers=2, onda imamo osim prva 4 parametara ([0]-[3]) jos 4 parametara (po jedan za broj neurona u svakom layeru).
        '''


        self.lb[0] = bounds['lb_lr']  # lower bound za learning rate, float
        self.ub[0] = bounds['ub_lr']  # lower bound za learning rate, float

        self.lb[1] = bounds['lb_dropout']  # lower bound za dropout
        self.ub[1] = bounds['ub_dropout']  # upper bound za dropout

        self.lb[2] = bounds['lb_epochs']  # lower bound za number of epochs, int
        self.ub[2] = bounds['ub_epochs']  # upper bound za number of epochs, int

        self.lb[3] = bounds['lb_layers']  # lower bound za broj slojeva, int
        self.ub[3] = bounds['ub_layers']  # upper bound za broj slojeva, int

        # sada sve do kraja ovog niza postavljamo vrednost za donju i gornju granicu broja neurona po svim slojevima, ukljucujuci i attention layer
        # pa zato ide do kraja, a duzina D zavisi od ub_layers, pa ako je ub_layers npr. 2, onda je duzina niza D=4 (osnovna 4 parametra) + 2*2 = 8

        for i in range(4, D):
            self.lb[i] = bounds['lb_nn']  # lower bound za broj neurona po slojevima, int
            self.ub[i] = bounds['ub_nn']  # upper bound za broj neurona po slojevima, int, poslednji je za attention layer

        # ostalo su za pocetak fiksni parametri
        self.loss = 'mse'
        self.metrics = ['mean_absolute_error']
        self.epochs = 200
        self.droput = 0.01
        self.recurrent_droput = 0.01
        self.activation = 'relu'
        self.loss = 'mean_squared_error'
        self.learning_rate = 0.001

        # warnings.warn = self.warn

        # ovo je za target columnb za multivariate
        #self.target = target


    # funkcija za evaluaciju
    def function(self, x):
        # list asa brojem neurona
        # swarm jedinka je vec lista i onda ne treba nista menjati
        # uzecemo samo prvi element liste u slucaju da imamo vise parametara
        # print(type(x))
        # print(x)
        # konvertujemo ponovo u listu, jer sa vise hiperparametara se komplikuje

        learning_rate = x[0]
        dropout = x[1]  # ovo je za dropout layer
        epochs = int(x[2])  # epoch je isto integer
        layers_lstm = int(x[3])   #broj layera
         # sad pravimo listu neurona, za svaki LSTM layer po jedan neuron plus jedan na kraju broj neurona za attention layer
        # idemo od 4-tog ideksa pa do kraja koliko imamo layers za LSTM, ali preskacemo poslednji, posto je poslednji za attention
        nn_list = x[4:(layers_lstm +4)]
        #konvertujemo sve u int
        nn_list = [int(x) for x in nn_list]



        print('NN list:',nn_list)




        # kreiranje LSTM modela, treniranje i predikcija
        LSTMModel = self.createRNNModel(self.no_inputs, self.no_targets, self.lags, nn_list,learning_rate=learning_rate)
        # self.trainLSTM(LSTMModel,self.epochs,self.trainData,self.valData)
        self.trainLSTM(LSTMModel, epochs, self.trainGenerator, self.valGenerator, earlyStop=self.early_stop)
        predictions = self.predictLSTM(LSTMModel, self.testGenerator)

        # ovo je specijalni korak ako hocemo da radimo sa denormalizovanim metrikama
        denorm_predictions = scaler_targets.inverse_transform(predictions)





        # ako je self.norm_metrics=False, onda su glavni denormalizovani i oni se vracaju kao primarni

        if self.norm_metrics:  # gledamo da li hocemo normalizovane ili denormalizovane metrike da vratimo
            allResults = evaluateModel(self.y_test,predictions)

            #allResults = allResults + (distanceEvaluatior(predictions, self.y_test))

            # ovde sada cuvamo overall rezultate, prosecne sve metrike za sve korake
            #ovo je iz starog frameworka, overall results i all results su isti!
            overallResults = evaluateModel(self.y_test,predictions)

            #overallResults = overallResults + (distanceEvaluatior(predictions, self.y_test))

            allResults1 = evaluateModel(self.y_test_denorm,denorm_predictions)



            # print("ALL:",allResults)
            # ovde sada cuvamo overall rezultate, prosecne sve metrike za sve korake
            overallResults1 = evaluateModel(self.y_test_denorm,denorm_predictions)

            #overallResults1 = overallResults1 + (distanceEvaluatior(denorm_predictions, self.y_test_denorm))

            #allResults1 = allResults1 + (distanceEvaluatior(denorm_predictions, self.y_test_denorm))

            objective = overallResults[2]
            #objective = distanceEvaluatior(predictions,self.y_test)

            print(overallResults)
            print(overallResults1)
            print(objective)

        else:
            allResults1 = evaluateModel(self.y_test, predictions)

            #allResults1 = allResults1 + (distanceEvaluatior(predictions, self.y_test))
            # ovde sada cuvamo overall rezultate, prosecne sve metrike za sve korake
            # ovo je iz starog frameworka, overall results i all results su isti!
            overallResults1 = evaluateModel(self.y_test, predictions)

            #overallResults1 = overallResults1 + (distanceEvaluatior(predictions,self.y_test))

            allResults = evaluateModel(self.y_test_denorm, denorm_predictions)

            #allResults = allResults + (distanceEvaluatior(denorm_predictions, self.y_test_denorm))

            # print("ALL:",allResults)
            # ovde sada cuvamo overall rezultate, prosecne sve metrike za sve korake
            overallResults = evaluateModel(self.y_test_denorm, denorm_predictions)

            #overallResults = overallResults + (distanceEvaluatior(denorm_predictions,self.y_test_denorm))


            objective = overallResults[2]





        # funkcija vraca sledece:
        # dakle, vracamo dve tipove metrika, normalizovane i denormalizovane, a koje ce biti primarne zavisi od flaga self.normResults
        # objective, overall_results, all_results, overall_results1, all_results1, results, x (ovo su parametri resenja) i na kraju model

        # prvo definisemo objective, neka objective bude prosecan mse (r2 treba da bude veci i zato ne moze kao objective, kada radimo probleme minimizacije)
        # objective = 1-overallResults[0]
        #objective = overallResults[2]  # mse
        # objective = overallResults[2]
        #print(list(overallResults))
        #print(list(allResults))
        # ovde dakle vracamo i normalizovane i denormalizovane metrike, a glavni su overallResults i allResults i po njima se rade racunanja
        return objective, list(overallResults), list(allResults), list(overallResults1), list(
            allResults1), predictions, LSTMModel

    # Pomocna funkcija za kreiranje LSTM modela - LSTMModel Creation
    def createRNNModel(self, no_inputs, no_targets, lags, nn_list, dropout=0.01,
                                 recurrent_dropout=0.01,
                                 loss='mean_squared_error', optimizer='adam', activation='relu', metrics=["mse", "mae", "mape"],
                                 learning_rate=0.001, batch_size=32):
        '''

        :param inputs:  broj input features
        :param no_targets:  broj target features, broj neurona u poslednjem sloju
        :param lags: broj lagova
        :param nn_list: lista sa brojem neurona po slojevima (zavisi od odabrane vrednosti za max broj slojeva), duzina koliko imamo lstm layera
        :param dropout: dropout probability za dropout layer
        :param recurrent_dropout: recurrent dropout parametar
        :param loss: loss funkcija
        :param optimizer: optimizer
        :param activation: aktivaciona funkcija
        :param metrics: metrike za loss funkciju
        :param learning_rate: learning rate
        :param batch_size: batch size za treniranje

        '''

        optimizer = keras.optimizers.Adam(learning_rate=learning_rate)
        # optimzer = 'adam'

        LSTMModel = keras.models.Sequential()
        LSTMModel.add(keras.Input(shape=(lags, no_inputs)))  # Input_Size, sequence_length

        # sada idemo kroz listu neurona
        for i in range(len(nn_list)):
            #poslednji sloj nema return_sequences, svi ostali imaju
            #u prvom sloju samo dajemo batch size, u ostalim ne dajemo


            if i==0 and len(nn_list)>1:
            #samo ako je prvi lstm sloj i ako imamo vise od jednog sloja, onda stavljamo batchsize i return sequences=true
                LSTMModel.add(layers.LSTM(nn_list[i], activation=activation,return_sequences=True))
            #ako je prvi lstm sloj i ako imamo samo jedan sloj, onda stavljamo batch_size, ali bez return_sequences
            elif i==0 and len(nn_list)==1:
                LSTMModel.add(layers.LSTM(nn_list[i],  activation=activation))

            #ako je poslednji lstm sloj, onda return_sequences=False
            elif i==len(nn_list)-1:
                LSTMModel.add(layers.LSTM(nn_list[i], activation=activation))
            else:
                LSTMModel.add(layers.LSTM(nn_list[i], activation=activation, return_sequences=True))


        LSTMModel.add(layers.Dropout(dropout))
        LSTMModel.add(layers.Dense(no_targets))
        LSTMModel.compile(loss=loss, optimizer=optimizer, metrics=metrics)

        return LSTMModel

    def trainLSTM(self, model, epochs, trainData, valData=None, earlyStop=False):
        if (earlyStop):
            es = EarlyStopping(monitor='val_loss', mode='min', verbose=False, patience=epochs / 3)
            model.fit(trainData, epochs=epochs, verbose=False, validation_data=valData, callbacks=[es])
        else:
            if valData is None:
                model.fit(trainData, epochs=epochs, verbose=False)
            else:
                model.fit(trainData, epochs=epochs, verbose=False, validation_data=valData)

    def predictLSTM(self, model, testGenerator):
        predictions = model.predict(testGenerator)
        return predictions

    # ignore warnings
    def warn(*args, **kwargs):
        pass

    '''
    #primer kreiranja LSTM modela preko liste
    def createLSTMAttentionModel1(self,feature_size, inputs, outputs, nn_list,dropout=0.01, recurrent_dropout=0.01,
                                 loss = 'mean_squared_error', optimizer='adam', activation='relu', metrics=['accuracy'],batch_size=32,learning_rate=0.001):

        # self.createLSTMAttentionModel(self.features,self.lags,self.steps,nn,nn1,layers_lstm,dropout=dropout,learning_rate=learning_rate)
        optimizer = keras.optimizers.Adam(learning_rate=learning_rate)

        #layers_lstm pokazuje koliko ima lstm slojeva

        l = [];
        l.append(keras.Input(shape=(inputs, feature_size)))

        for i in nn_list:
            l.append(layers.LSTM(i[0], activation=activation, batch_size=batch_size, return_sequences=True)(l[-1]))
            l.append(Attention(units=i[1])(l[-1]))



        l.append(layers.Dropout(dropout)(l[-1]))
        l.append(layers.Dense(outputs)(l[-1]))

        model = keras.models.Model(l[0], l[-1])
        model.compile(loss=loss, optimizer=optimizer, metrics=metrics)

        return model
'''
