from math import exp
from random import shuffle
from pprint import pformat
from decimal import Decimal
import logging

log = logging.getLogger(__name__)

class LogRegression:

    _ALPHA = 0.2
    
    def __init__(self, betas):
        # should check other types
        if type(betas) in [list, set]:
            self.betas = {}
            for beta in betas:
                self.betas[beta] = 0.0
            self.betas['bias'] = 0.0
        elif type(betas) == dict:
            self.betas = betas
            if 'bias' not in self.betas:
                self.betas['bias'] = 0.0
        else:
            raise TypeError('Betas should be a dict or list-like type')

    # estimate probability of p2 winning
    # keys in coefficients take precedence over kwargs
    def p(self, coefficients={}, **kwargs):
        coefficients['bias'] = 1
        kwargs.update(coefficients)

        linear = Decimal(0)
        for k in self.betas:
            linear += Decimal(self.betas[k]) * Decimal(kwargs[k])

        logified = Decimal(1) / (Decimal(1) + (linear * Decimal(-1)).exp())
        return logified

    def train(self, training_data, y_key, epochs=10):
        log.info('Betas: ' + str(self.betas))
        for i in range(epochs):
            correct = 0
            for fight in training_data:
                prediction = self.p({key: fight[key] for key in fight.keys() if key != y_key})
                if (prediction >= 0.5 and fight[y_key] == 1) or (prediction < 0.5 and fight[y_key] == 0):
                    correct += 1

                for beta in self.betas:
                    if beta == 'bias':
                        self.betas[beta] = self.recalc_beta(self.betas[beta], fight[y_key], prediction, 1) # bias always has coefficient 1
                    else:
                        self.betas[beta] = self.recalc_beta(self.betas[beta], fight[y_key], prediction, fight[beta])

            shuffle(training_data)
            log.info('Betas: ' + str(self.betas))
            log.info('Correct pct: %s' % (correct / len(training_data) * 100))

    # b: beta val to update
    # y: actual classification
    # prediction: current probability of y=1
    # x: coefficient for beta val to update
    def recalc_beta(self, b, y, prediction, x):
        recalc =  Decimal(b) + Decimal(self._ALPHA) * (Decimal(y) - Decimal(prediction)) * Decimal(x)
        return recalc
