import pandas as pd

class photomanager:
	
	__album = pd.DataFrame()
	__photos = pd.DataFrame()
	
	def set_photos (self, album, mediametadataheader:str, photoheader:str, mimeheader:str, mimetype:str):
		self.__album = album
		
		#get media items				
		dfmeta = album.get_data().mediaMetadata.apply(pd.Series)

		#build all items table
		all = pd.concat(
			[
			album.get_data().drop(mediametadataheader, axis = 1), 
			dfmeta.drop(photoheader, axis = 1), 
			dfmeta.photo.apply(pd.Series)
			], axis=1
		)

		#get only photos
		isimage = all[mimeheader].str.startswith(mimetype)
		self.__photos = all[isimage].reset_index(drop = True)
		
		return self.__photos
	
	def get_album (self):
		return self.__album
	
	def get_photos (self):
		return self.__photos
	
	@classmethod
	def get_num_of_photos (self, photos):
		return len(photos.axes[0])
	
	@classmethod
	def reset_index (self, photos):
		return photos.reset_index(drop = True)	
	
	@classmethod
	def get_photos_attribute (self, photos, attribute:str):
		return photos[attribute]
	
	@classmethod
	def get_photo_attribute (self, photo, attribute:str):
		return photo[attribute]
	
	@classmethod
	def get_photo_by_index (self, photos, index:int):
		return photos.iloc[index]