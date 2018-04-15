from random import shuffle
from decimal import Decimal
import logging
import json

log = logging.getLogger(__name__)

##TODO: Make this an ABC
class SaltyModel:

    def __init__(self):
        self.bet = None # previous bet


class LogRegression(SaltyModel):

    _ALPHA = 0.2
    
    def __init__(self, betas):
        super().__init__()
        self.betas = {}
        for beta in betas:
            if type(betas) == dict:
                self.betas[beta] = Decimal(betas[beta])
            else:
                self.betas[beta] = Decimal(0.0)
        if 'bias' not in self.betas:
            self.betas['bias'] = Decimal(0.0)

    # estimate probability of p2 winning
    # keys in coefficients take precedence over kwargs
    def p(self, coefficients={}):
        coefficients['bias'] = Decimal(1)

        linear = Decimal(0)
        for k in self.betas:
            linear += Decimal(self.betas[k]) * Decimal(coefficients[k])

        logified = Decimal(1) / (Decimal(1) + (linear * Decimal(-1)).exp())
        return logified

    def train(self, training_data, y_key, epochs=10):
        log.info('Betas: ' + str(self.betas))
        for i in range(epochs):
            correct = 0
            shuffle(training_data)
            for fight in training_data:
                prediction = self.p({key: fight[key] for key in fight.keys() if key != y_key})
                if (prediction >= 0.5 and fight[y_key] == 1) or (prediction < 0.5 and fight[y_key] == 0):
                    correct += 1

                for beta in self.betas:
                    if beta == 'bias':
                        self.betas[beta] = self.recalc_beta(self.betas[beta], fight[y_key], prediction, 1) # bias always has coefficient 1
                    else:
                        self.betas[beta] = self.recalc_beta(self.betas[beta], fight[y_key], prediction, fight[beta])

            log.info('Betas: ' + str(self.betas))
            log.info('Correct pct: %s' % (correct / len(training_data) * 100))

    # b: beta val to update
    # y: actual classification
    # prediction: current probability of y=1
    # x: coefficient for beta val to update
    def recalc_beta(self, b, y, prediction, x):
        recalc =  Decimal(b) + Decimal(self._ALPHA) * (Decimal(y) - Decimal(prediction)) * Decimal(x)
        return recalc

    def to_json(self):
        betas = {}
        for k, v in self.betas.items():
            betas[k] = str(v)
        return json.dumps(betas)

    @classmethod
    def from_json(cls, json_obj):
        betas = {}
        for k, v in json.loads(json_obj).items():
            betas[k] = Decimal(v)
        return cls(betas)