#!/usr/bin/env python3

import sys, os, pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

PICKLE_FILE='token.pickle'
CREDS_FILE='credentials.json'
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']
PYTHON_VERSION = 3

def manage_pickle (picklefile:str, credfile:str, scopes:str):
    creds = None

    if os.path.exists(picklefile):
        with open(picklefile, 'rb') as token: creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credfile, scopes)
            creds = flow.run_local_server(port=0)
        with open(picklefile, 'wb') as token: pickle.dump(creds, token)

def remove_token (picklefile:str):
    if os.path.exists(picklefile): os.remove(picklefile)

if sys.version_info[0] < PYTHON_VERSION: raise Exception("Must be using Python {}!".format(PYTHON_VERSION))

print ("ePiframe - e-Paper Raspberry Pi Photo Frame - get token tool\nThis tool will help get the Google token file")
print ("(pickle file) for ePiframe. Run it on internet browser\nSaccessible machine to authenticate with Google account!")

if not '--help' in [x.lower() for x in sys.argv]:
	PICKLE_FILE = input("Enter the path of token pickle file [Leave empty for {}]: ".format(PICKLE_FILE)) or PICKLE_FILE
	print ('Token pickle file = ' + str(PICKLE_FILE))
	
	while True:
		CREDS_FILE = input("Enter the path of credentials JSON file [Leave empty for {}]: ".format(CREDS_FILE)) or CREDS_FILE
		if os.path.exists(CREDS_FILE): break
		print ("I did not find the file at, " + str(CREDS_FILE))	
	
	print ('Credentials JSON file = ' + str(CREDS_FILE))
	valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
	
	try:		
		if os.path.exists(PICKLE_FILE):
			print ("There is an existing token file: {}\nDo you want to remove it and create new one?".format(PICKLE_FILE))	
			
			res = None
			while True:			
				choice = input(" [Y/n] ").lower() or "yes"
				
				if choice in valid:
					res = valid[choice]
					break
				else:
					sys.stdout.write("Please respond with 'yes' or 'no' "
									 "(or 'y' or 'n').\n")
			if res:
				remove_token(PICKLE_FILE)			

		manage_pickle(PICKLE_FILE, CREDS_FILE, SCOPES)
	except Exception as e:
		print("Error! {}".format(e))
		raise

	print ("Success! Now copy the token file - {} to ePiframe folder on the frame device and update config.cfg configuration file".format(PICKLE_FILE))