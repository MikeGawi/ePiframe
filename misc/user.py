from flask_login import UserMixin

class user(UserMixin):

	id = None
	username = None
	password = None

	def __init__(self, id, username, password):
		self.id = id
		self.username = username
		self.password = password
	
	#overridden
	def get_id(self):
		return str(self.username)