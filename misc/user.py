from flask_login import UserMixin

class user(UserMixin):

	id = None
	username = None
	password = None
	api = None

	def __init__(self, id, username, password, api):
		self.id = id
		self.username = username
		self.password = password
		self.api = api
	
	#overridden
	def get_id(self):
		return str(self.username)