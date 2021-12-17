import os
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

class oauthmanager:

	def manage_pickle (self, picklefile:str, credfile:str, scopes:str):
		self.__creds = None
		
		# The file token.pickle stores the user's access and refresh tokens, and is
		# created automatically when the authorization flow completes for the first
		# time.
		if os.path.exists(picklefile):
			with open(picklefile, 'rb') as token:
				self.__creds = pickle.load(token)
		# If there are no (valid) credentials available, let the user log in.
		if not self.__creds or not self.__creds.valid:
			if self.__creds and self.__creds.expired and self.__creds.refresh_token:
				self.__creds.refresh(Request())
			else:
				flow = InstalledAppFlow.from_client_secrets_file(credfile, scopes)
				self.__creds = flow.run_local_server(port=0)
			# Save the credentials for the next run
			with open(picklefile, 'wb') as token:
				pickle.dump(self.__creds, token)
		os.chmod(picklefile, 0o0666)		
				
	def build_service (self, name:str, ver:str):
		self.__service = build(name, ver, credentials=self.__creds, static_discovery=False)
	
	def get (self, pagesize:int, exclude:bool, nextpagetokenheader:str, resp_for:str):	
		items = []
		nextpagetoken = None

		while nextpagetoken != '':
			results = self.__service.albums().list(
				pageSize = pagesize,
				pageToken=nextpagetoken,
				excludeNonAppCreatedData = exclude
			).execute()
			items += results.get(resp_for, [])
			nextpagetoken = results.get(nextpagetokenheader, '')
		
		self.__items = items
	
	def remove_token (self,picklefile:str):
		if os.path.exists(picklefile):
			os.remove(picklefile)
	
	def get_items (self, header:str, id:str, itemheader:str, pagesize:int, pagesizeheader:str, pagetokenheader:str, nextpagetokenrespheader:str):
		items = []
		nextpagetoken = None

		while nextpagetoken != '':
			results = self.__service.mediaItems().search(
				body = {
					pagesizeheader : pagesize,
					pagetokenheader : nextpagetoken,
					header : id
				}
			).execute()
			items += results.get(itemheader, [])
			nextpagetoken = results.get(nextpagetokenrespheader, '')
		
		return items
				
	def get_service (self):
		return self.__service
	
	def get_response (self):
		return self.__items
	
	def get_creds (self):
		return self.__creds