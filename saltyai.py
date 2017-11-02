from math import exp
from random import shuffle
import logging

log = logging.getLogger(__name__)

##TODO: can we generalize this to just take a table of training data and which column is Y?
class LogRegression:

    _ALPHA = 0.2
    
    def __init__(self, b_bias=0.0, b_p1elo=0.0, b_p2elo=0.0, b_p1winsvp2=0.0, b_p2winsvp1=0.0, b_p1winpct=0.0, b_p2winpct=0.0):
        self.b_bias = b_bias
        self.b_p1elo = b_p1elo
        self.b_p2elo = b_p2elo
        self.b_p1winsvp2 = b_p1winsvp2
        self.b_p2winsvp1 = b_p2winsvp1
        self.b_p1winpct = b_p1winpct
        self.b_p2winpct = b_p2winpct

    # estimate probability of p2 winning
    def p(self, p1elo, p2elo, p1winsvp2, p2winsvp1, p1winpct, p2winpct):
        linear = self.b_bias + self.b_p1elo*p1elo + self.b_p2elo*p2elo + self.b_p1winsvp2*p1winsvp2 + self.b_p2winsvp1*p2winsvp1
        linear += self.b_p1winpct*p1winpct + self.b_p2winpct*p2winpct
        try:
            logified = 1.0 / (1.0 + exp(-linear))
        except OverflowError as e: # good enough
            if linear > 0:
                logified = 1
            elif linear < 0:
                logified = 0
        return logified

    def train(self, training_data, epochs=10):
        self.log_betas()
        for i in range(epochs):
            correct = 0
            for fight in training_data:
                prediction = self.p(fight['p1elo'], fight['p2elo'], fight['p1winsvp2'], fight['p2winsvp1'], fight['p1winpct'], fight['p2winpct'])
                if (prediction >= 0.5 and fight['winner'] == 1) or (prediction < 0.5 and fight['winner'] == 0):
                    correct += 1
                self.b_bias = self.recalc_beta(self.b_bias, fight['winner'], prediction, 1) # bias always has coefficient 1
                self.b_p1elo = self.recalc_beta(self.b_p1elo, fight['winner'], prediction, fight['p1elo'])
                self.b_p2elo = self.recalc_beta(self.b_p2elo, fight['winner'], prediction, fight['p2elo'])
                self.b_p1winsvp2 = self.recalc_beta(self.b_p1winsvp2, fight['winner'], prediction, fight['p1winsvp2'])
                self.b_p2winsvp1 = self.recalc_beta(self.b_p2winsvp1, fight['winner'], prediction, fight['p2winsvp1'])
                self.b_p1winpct = self.recalc_beta(self.b_p1winpct, fight['winner'], prediction, fight['p1winpct'])
                self.b_p2winpct = self.recalc_beta(self.b_p2winpct, fight['winner'], prediction, fight['p2winpct'])
            shuffle(training_data)
            self.log_betas()
            log.info('Correct pct: %s' % (correct / len(training_data) * 100))

    # b: beta val to update
    # y: actual classification
    # prediction: current probability of y=1
    # x: coefficient for beta val to update
    def recalc_beta(self, b, y, prediction, x):
        recalc =  b + self._ALPHA * (y-prediction) * x
        return recalc
   
    def log_betas(self):
        log.info('betas: bias: {bias}, p1elo: {p1elo}, p2elo: {p2elo}, p1winsvp2: {p1winsvp2}, p2winsvp1: {p2winsvp1}, p1winpct: {p1winpct}, p2winpct: {p2winpct}'.format(
            bias = self.b_bias,
            p1elo = self.b_p1elo,
            p2elo = self.b_p2elo,
            p1winsvp2 = self.b_p1winsvp2,
            p2winsvp1 = self.b_p2winsvp1,
            p1winpct = self.b_p1winpct,
            p2winpct = self.b_p2winpct
        ))
