from misc.constants import constants
from misc.user import user
import crypt
import hashlib
from getpass import getpass

class usersmanager:
	
	__ADD_ERROR = 'There was a problem during user insertion to DB'
	__IN_ERROR = 'User already exists!'
	__NO_USER_ERROR = "User doesn't exist!"
	__PASSWORD_ERROR = 'Wrong password!'
	
	def __init__ (self, databasemanager):
		self.__databasemanager = databasemanager
		self.__schema = databasemanager.get_schema(constants.USERS_TABLE_NAME)
		
		#populate api key for old users
		users = self.get()
		if users and len(users):
			for i in [u.id for u in users if not u.api]:
				self.__databasemanager.update(constants.USERS_TABLE_NAME, constants.USERS_TABLE_API_HEADER, "'{}'".format(str(self.__gen_api())), constants.USERS_TABLE_ID_HEADER+" IS "+str(i))				
	
	def __get_column(self, name):
		return next(x[0] for x in self.__schema if x[1] == name)
	
	def __to_object(self, rows):
		res = []
		if rows and len(rows) > 0:
			for row in rows:
				res.append(user(row[self.__get_column(constants.USERS_TABLE_ID_HEADER)], row[self.__get_column(constants.USERS_TABLE_USERNAME_HEADER)],\
								row[self.__get_column(constants.USERS_TABLE_HASH_HEADER)], row[self.__get_column(constants.USERS_TABLE_API_HEADER)]))
		return res
	
	def get(self):
		return self.__to_object(self.__databasemanager.select(constants.DB_ALL, constants.USERS_TABLE_NAME,''))

	def get_by_username(self, username):
		return self.__to_object(self.__databasemanager.select(constants.DB_ALL, constants.USERS_TABLE_NAME, constants.USERS_TABLE_USERNAME_HEADER + ' IS ' + "'{}'".format(username)))
	
	def get_by_api(self, api):
		return self.__to_object(self.__databasemanager.select(constants.DB_ALL, constants.USERS_TABLE_NAME, constants.USERS_TABLE_API_HEADER + ' IS ' + "'{}'".format(api)))
	
	def login_needed(self):
		us = self.get()		
		return us and len(us) > 0 or False
	
	def __add_salt(self, password, salt=""):
		salt = crypt.mksalt(crypt.METHOD_SHA512) if not salt else salt
		return hashlib.md5((password + salt).encode()).hexdigest(), salt
	
	def __gen_api(self):
		return self.__add_salt("","")[0]
	
	def add(self, userobj):	
		ids = self.get_by_username(userobj.username)
		if not ids:
			passw, salt = self.__add_salt(userobj.password)
			self.__databasemanager.insert(constants.USERS_TABLE_NAME, [constants.DB_NULL, userobj.username, str(passw), userobj.api])		
			ids = self.get_by_username(userobj.username)
			
			if ids and len(ids) > 0:
				self.__databasemanager.insert(constants.SALTS_TABLE_NAME, [constants.DB_NULL, str(ids[0].id), str(salt)])
			else: 
				raise Exception (self.__ADD_ERROR)
		else:
			raise Exception (self.__IN_ERROR)

	def delete(self, username):
		ids = self.get_by_username(username)																		 
		if ids and len(ids) > 0:
			self.__databasemanager.delete(constants.USERS_TABLE_NAME, constants.USERS_TABLE_USERNAME_HEADER+" IS '{}'".format(username))		
			self.__databasemanager.delete(constants.SALTS_TABLE_NAME, constants.SALTS_TABLE_USERID_HEADER+" IS "+str(ids[0].id))
		else:
			raise Exception (self.__NO_USER_ERROR)
							
	def change_password(self, username, oldpass, newpassw):
		try:
			self.check(username, oldpass)
			ids = self.get_by_username(username)
			if ids and len(ids) > 0:
				password, salt = self.__add_salt(newpassw)
				self.__databasemanager.update(constants.USERS_TABLE_NAME, constants.USERS_TABLE_HASH_HEADER, "'{}'".format(str(password)), constants.USERS_TABLE_ID_HEADER+" IS "+str(ids[0].id))
				self.__databasemanager.update(constants.SALTS_TABLE_NAME, constants.SALTS_TABLE_SALT_HEADER, "'{}'".format(str(salt)),  constants.SALTS_TABLE_USERID_HEADER+" IS "+str(ids[0].id))
			else:
				raise Exception (self.__NO_USER_ERROR)			
		except Exception as e:
			raise e			
			
	def check(self, username, passw):
		ids = self.get_by_username(username)
		if ids and len(ids) > 0:
			salt = self.__databasemanager.select(constants.SALTS_TABLE_SALT_HEADER, constants.SALTS_TABLE_NAME, constants.SALTS_TABLE_USERID_HEADER+" IS "+str(ids[0].id))[0]
			if salt:
				password = self.__add_salt(passw, salt[0])
				if not password[0] == ids[0].password:	
					raise Exception (self.__PASSWORD_ERROR)
		else:
			raise Exception (self.__NO_USER_ERROR)
	
	def __result(self, action, result=True):
		print (action, "SUCCESSFULLY!" if result else '')
		input("Press any key to continue...")
	
	def __user_check(self, exist=True):
		while True:
			username = input("Username: ")
			if exist:
				if self.get_by_username(username): break
				print (self.__NO_USER_ERROR)
			else:
				if not self.get_by_username(username): break
				print (self.__IN_ERROR)
				
		return username
	
	def __password(self, username, title):
		while True:
			password = getpass(title)
			try:
				self.check(username, password)
				break
			except Exception:
				pass
				print (self.__PASSWORD_ERROR)
				
		return password

	def __new_password(self, title, title_confirm):
		while True:
			newpassword = getpass(title)
			newpassword2 = getpass(title_confirm)					
			if newpassword == newpassword2: break
			print ("Passwords are not the same!")
		
		return newpassword
	
	def manage(self, log):
		valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
		loop = True

		while loop:
			us = self.get()
			title = 10 * "-" + " ePiframe user management " + 10 * "-"
			print(title)
			print(2 * "-", "Changing anything needs service restart!", 2 * "-")
			print("USERS:")
			print('\n'.join([u.username for u in us]) if us else '<NO USERS!>')
			print()
			print("1. Add new user")
			print("2. Delete user")
			print("3. Change user password")
			print("4. Show user API key")        
			print("5. Test user password")        
			print("6. Exit")
			print(len(title) * "-")
			self.__choice = input("Enter your choice [1-6]: ")
			
			if self.__choice == '1':
				print(5 * "-", "Adding new user", 5 * "-")
				username = self.__user_check(False)
				password = self.__new_password('Password [empty possible]: ', 'Confirm password [empty possible]: ')
				self.add(user('', username, password, self.__gen_api()))
				log.log(constants.USERS_ACTIONS_TAG + "User {} added!".format(username))
				self.__result("USER ADDED")
			elif self.__choice == '2':
				print(5 * "-", "Deleting user", 5 * "-")
				username = self.__user_check()
				while True:			
					choice = input("Do You really want to delete this user? [y/N]: ").lower() or "no"
					if choice in valid:
						if valid[choice]:
							self.delete(username)
							log.log(constants.USERS_ACTIONS_TAG + "User {} deleted!".format(username))
							self.__result("USER DELETED")
						else:
							self.__result("USER WAS NOT DELETED")
						break
					else:
						print("Please respond with 'yes' or 'no' (or 'y' or 'n')")
			elif self.__choice == '3':
				print(5 * "-", "Changing user password", 5 * "-")
				username = self.__user_check()
				currpassword = self.__password(username, 'Current password: ')
				newpassword = self.__new_password('New password [empty possible]: ', 'Confirm new password [empty possible]: ')
				self.change_password(username, currpassword, newpassword)
				log.log(constants.USERS_ACTIONS_TAG + "User {} password changed!".format(username))
				self.__result("PASSWORD CHANGED")
			elif self.__choice == '4':
				print(5 * "-", "Showing user API key", 5 * "-")
				username = self.__user_check()
				self.__password(username, 'Password: ')
				userobj = self.get_by_username(username)[0]
				self.__result("USER {} API KEY: {}".format(username, userobj.api), False)	
			elif self.__choice == '5':
				print(5 * "-", "Testing user password", 5 * "-")
				username = self.__user_check()
				self.__password(username, 'Password: ')
				self.__result("YOU HAVE LOGGED IN")
			elif self.__choice == '6':
				print("Exiting...")
				loop = False
			else:
				print("Wrong selection. Try again...")