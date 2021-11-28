from misc.constants import constants
import sqlite3

class databasemanager:

	__SELECT_DB = "SELECT "+constants.DB_NAME_COL+" FROM "+constants.DB_SQLITE_MASTER_TAB+" WHERE type='table' AND "+constants.DB_NAME_COL+"='{}'"
	__BACK_TAG = "_back"
	
	def __init__ (self):
		self.__dbconnection = sqlite3.connect(constants.USERS_DB_FILE, check_same_thread=False)
		cur = self.__dbconnection.cursor()
		
		dbs = {	constants.USERS_TABLE_NAME : "CREATE TABLE {} (id INTEGER PRIMARY KEY ASC, username text, hash text)".format(constants.USERS_TABLE_NAME),
				constants.SALTS_TABLE_NAME : "CREATE TABLE {} (id INTEGER PRIMARY KEY ASC, userid INTEGER, salt text, FOREIGN KEY(userid) REFERENCES {}(id))".format(constants.SALTS_TABLE_NAME, constants.USERS_TABLE_NAME)}
				
		for db in dbs.keys():
			cur.execute(self.__SELECT_DB.format(db))
			if not cur.fetchone():
				cur.execute(dbs[db])
				self.__dbconnection.commit()		
			else:
				#simple backward compatibility
				if self.get_create(db)[0][0] != dbs[db]:
					fields = ','.join([x[1] for x in self.get_schema(db)])
					cur = self.__dbconnection.cursor()
					cur.execute('ALTER TABLE {} RENAME TO {}'.format(db, db+self.__BACK_TAG))
					cur.execute(dbs[db])
					cur.execute('INSERT INTO {} ({}) SELECT {} FROM {}'.format(db, fields, fields, db+self.__BACK_TAG))
					cur.execute('DROP TABLE {}'.format(db+self.__BACK_TAG))
					self.__dbconnection.commit()					
				
	def __commit (self, query:str, fields=""):
		cur = self.__dbconnection.cursor()
		if fields:		
			cur.executemany(query, fields)
		else:
			cur.execute(query, "")
		self.__dbconnection.commit()
		
	def __get (self, query:str, fields=""):
		cur = self.__dbconnection.cursor()
		cur.execute(query, fields)
		self.__dbconnection.commit()
		return cur.fetchall()
		
	def __change_many(self, fields):
		return ','.join(fields) if isinstance(fields, list) else fields
	
	def __to_strings(self, fields):	
		vals=[]
		for i, e in enumerate(fields):
			vals.append("'{}'".format(e) if isinstance(e, str) and e != constants.DB_NULL else e)
		return vals
		
	def select (self, fields, From, where=None):
		return self.__get("SELECT {} FROM {}".format(self.__change_many(fields), self.__change_many(From)) + (" WHERE {}".format (where) if where else ""))
	
	def update (self, table, field, value, where):
		return self.__commit("UPDATE {} SET {} = {} WHERE {}".format(table, field, value, where))
	
	def delete (self, table, where):
		return self.__commit("DELETE FROM {} WHERE {}".format(table, where))	

	def insert (self, to, values):
		return self.__commit("INSERT INTO {} VALUES ({})".format(self.__change_many(to), self.__change_many(self.__to_strings(values))))
	
	def get_schema (self, For):
		return self.__get('PRAGMA table_info("{}")'.format(For))
	
	def get_create (self, For):
		return self.select(constants.DB_SQL_COL, constants.DB_SQLITE_MASTER_TAB, '{} IS "{}"'.format(constants.DB_NAME_COL, For))