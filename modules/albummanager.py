import pandas as pd

class albummanager:
	
	__albumData = pd.DataFrame()
	__albumNames = pd.DataFrame()
	
	def __init__ (self, albums, names:str, header:str):
		dfAlbums = pd.DataFrame(albums)
		
		#search for albums
		if names:
			albumNames = names.split(',')
			#remove duplicates
			albumNames = list(set(albumNames))	

			for name in albumNames:
				if name.strip():
					album = dfAlbums[dfAlbums[header] == name.strip()]
					if not album.empty:
						self.__albumNames = self.__albumNames.append(album)
		else:
			self.__albumNames = dfAlbums

	def get_albums (self):
		return self.__albumNames
	
	def append_data (self, data):
		pdData = pd.DataFrame(data)
			
		if not pdData.empty:										
			self.__albumData = self.__albumData.append(pdData)
	
	def get_data (self):
		return self.__albumData