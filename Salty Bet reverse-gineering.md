


# Salty Bet
Important javascript: http://www.saltybet.com/j/www-cdn-jtvnw-x.js

##Auth
- Not sure.... maybe done in jQuery validate somehow?
- login url: http://saltybet.com/authenticate?signin=1
- python: https://github.com/nawns/python-saltybet
	- use http://docs.python-requests.org/en/latest/
	> def login(self):
	        payload = {}
	        payload['email'] = self.email
	        payload['pword'] = self.password
	        payload['authenticate'] = 'signin'
	        session = requests.Session()
	        session.post(loginurl, data=payload)
	        self.session = session
        
- golang: http://stackoverflow.com/questions/11361431/authenticated-http-client-requests-from-golang
	- http://www.gorillatoolkit.org/pkg/sessions#Session

##State
 - http://saltybet.com/state.json
	 - if betstate is "open", check alert: 
		 - tournament -> balance: http://www.saltybet.com/ajax_tournament_start.php
		 - else -> balance: http://www.saltybet.com/ajax_tournament_end.php
 - check state after recieving message from socket.io: http://www-cdn-twitch.saltybet.com:8000
	 - http://learn-gevent-socketio.readthedocs.org/en/latest/socketio.html
	 - https://pypi.python.org/pypi/socketIO-client
	 - Can't figure out how to recieve message in golang... it looks like the messages are empty anyway.

## Making bets
- $("form").serialize() -> http://saltybet.com/ajax_place_bet.php
	- "selectedplayer=player1&wager=10" -> http://saltybet.com/ajax_place_bet.php
	- post

##Tracking stats
- check status periodically, if open, bet
- Keep track of who you bet on and how much money you had when you bet
- when match changes, check to see if you made or lost money