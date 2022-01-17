import sys, os
import subprocess

class convertmanager:
	
	__ERROR_VALUE_TEXT = 'Configuration background_color should be one of {}'
	
	__INVERT_FLAG = "-negate"
	__ROTATE_CODE = '-rotate 90'
	__BACK_COLORS = ["white", "black", "photo"]
	
	__AUTO_GAMMA_ENH = '-auto-gamma '
	__AUTO_LEVEL_ENH = '-channel rgb -auto-level '
	__NORMALIZE_ENH = '-normalize '
	__BRIGHT_CONTRAST_ENH = '-brightness-contrast {},{} '
	
	__FILE_MARK = '[]'
	__GET_PHOTO_SIZE_CODE = '{} ' + __FILE_MARK + ' -format "%w,%h" info:'
	__GET_PHOTO_FORMAT_CODE = '{} ' + __FILE_MARK + ' -format "%m" info:'
	__GET_PHOTO_COMMENT_CODE = '{} ' + __FILE_MARK + ' -format "%c" info:'
	
	#Don't use blur! Blur will kill Raspberry Pi Zero.
	#Resizing to huge and then scaling to small will add some blur and it's 10x faster than blur operation.
	__PHOTO_BACK_CODE = '( -clone 0 -gravity center -sample x{} -scale {}% -resize {}x{}^ -crop {}x+0+0 +repage ) ( -clone 0 -sample {}x{} ) -delete 0 -gravity center -compose over -composite '
	__PHOTO_RESIZE_CODE = '-sample {}x{} '
		
	#options for ImageMagick converter
	#https://legacy.imagemagick.org/Usage/quantize/
	__CONVERT_OPTIONS = {
		'1'	:	'{} ' + __FILE_MARK + ' -limit thread 1 {} ( +clone {}{}-dither FloydSteinberg -remap pattern:gray50 {}-background {} -gravity center -extent {}x{} -type bilevel -write {} ) {} NULL:',
		'2'	:	'{} ' + __FILE_MARK + ' -limit thread 1 {} ( +clone {}{}-dither FloydSteinberg {}-background {} -gravity center -extent {}x{} -type bilevel -write {} ) {} NULL:',
		'3'	:	'{} ' + __FILE_MARK + ' -limit thread 1 {} ( +clone {}{}-dither FloydSteinberg -remap pattern:gray50 {}-background {} -gravity center -extent {}x{} -type bilevel -write {} ) {} NULL:',
		'4'	:	'{} ' + __FILE_MARK + ' -limit thread 1 {} ( +clone {}{}-dither FloydSteinberg -ordered-dither o4x4 {}-background {} -gravity center -extent {}x{} -type bilevel -write {} ) {} NULL:',
		'5'	:	'{} ' + __FILE_MARK + ' -limit thread 1 {} ( +clone {}{}{}-background {} -gravity center -extent {}x{} -type bilevel -write {} ) {} NULL:',
		'6'	:	'{} ' + __FILE_MARK + ' -limit thread 1 {} ( +clone {}{}-colors 2 +dither {}-background {} -gravity center -extent {}x{} -type bilevel -write {} ) {} NULL:'
	}
	
	__THUMB_SIZE = '200x120'
	__THUMB_1ST_PART = '( +clone -background white -gravity center -sample {}x{} -extent {}x{} -thumbnail ' + __THUMB_SIZE + ' -write {} +delete )'
	__THUMB_2ND_PART = '( +clone -thumbnail ' + __THUMB_SIZE + ' -write {} )'
		
	@classmethod		
	def verify_background_color (self, val):
		if not val.strip().lower() in self.__BACK_COLORS:
			raise Exception(self.__ERROR_VALUE_TEXT.format(self.__BACK_COLORS))
			
	@classmethod		
	def get_background_colors (self):
		return self.__BACK_COLORS
	
	@classmethod		
	def get_convert_options (self):
		return list(self.__CONVERT_OPTIONS.keys())
	
	def __convert_option (self, origwidth:int, origheight:int, target:str, config):
		option = int(config.get('convert_option'))
		width = config.getint('image_width')
		height = config.getint('image_height')
		back = config.get('background_color')
		
		if int(option) > len(self.__CONVERT_OPTIONS) or int(option) < 1: option = 1
		
		#space at the end as those flag are optional
		negate = self.__INVERT_FLAG + " " if config.getint('invert_colors') == 1 else ''
		rotate = self.__ROTATE_CODE + " " if config.getint('horizontal') == 0 else ''		
		
		back = back.strip().lower()		
				
		if not back in self.__BACK_COLORS:
			back = self.__BACK_COLORS[0]

		if back == "photo":
			back = self.__BACK_COLORS[0]
			#this takes more time to progress		
			aspectratio = int(origwidth) / int(origheight)
			newheight = max (int(width / aspectratio), height)
			scale = round(aspectratio * 10.0, 2)
			code = self.__PHOTO_BACK_CODE.format(newheight, scale, width, newheight, width, width, height)
		else:
			code = self.__PHOTO_RESIZE_CODE.format(width, height)
			
		if bool(config.getint('auto_gamma')): code += self.__AUTO_GAMMA_ENH
		if bool(config.getint('auto_level')): code += self.__AUTO_LEVEL_ENH
		if bool(config.getint('normalize')): code += self.__NORMALIZE_ENH
		code += self.__BRIGHT_CONTRAST_ENH.format(config.getint('brightness'),config.getint('contrast'))
		
		thumb1st = self.__THUMB_1ST_PART.format(width, height, width, height, os.path.join(config.get('photo_convert_path'), config.get('thumb_photo_download_name')))
		thumb2nd = self.__THUMB_2ND_PART.format(os.path.join(config.get('photo_convert_path'), config.get('thumb_photo_convert_filename')))
		
		ret = self.__CONVERT_OPTIONS[str(option)].format(config.get('convert_bin_path'), thumb1st, rotate, code, negate, back, width, height, target, thumb2nd)
		print (ret.replace('(','\(').replace(')','\)'))
		return ret
	
	def convert_image (self, origwidth:int, origheight:int, srcfile:str, target:str, config):
		args = (self.__convert_option(origwidth, origheight, target, config)).split()
		process = subprocess.Popen([x.replace(self.__FILE_MARK, srcfile) for x in args], stdout=subprocess.PIPE)
		process.wait()
		out, err = process.communicate()
		return err
	
	def get_image_size (self, bin:str, srcfile:str, firstframe:str):
		args = (self.__GET_PHOTO_SIZE_CODE.format(bin)).split()
		process = subprocess.Popen([x.replace(self.__FILE_MARK, srcfile+firstframe) for x in args], stdout=subprocess.PIPE)
		process.wait()
		out, err = process.communicate()
		wh = str(out.decode()).replace('"','').split(',') if out else ''
		width = wh[0] if wh and len(wh)>1 else ''
		height = wh[1] if wh and len(wh)>1 else ''
		return err, width, height
	
	def get_image_format (self, bin:str, srcfile:str, firstframe:str):
		args = (self.__GET_PHOTO_FORMAT_CODE.format(bin)).split()
		process = subprocess.Popen([x.replace(self.__FILE_MARK, srcfile+firstframe) for x in args], stdout=subprocess.PIPE)
		process.wait()
		out, err = process.communicate()
		m = str(out.decode()).replace('"','') if out else ''
		return err, m
	
	def get_image_comment (self, bin:str, srcfile:str):
		args = (self.__GET_PHOTO_COMMENT_CODE.format(bin)).split()
		process = subprocess.Popen([x.replace(self.__FILE_MARK, srcfile) for x in args], stdout=subprocess.PIPE)
		process.wait()
		out, err = process.communicate()
		c = str(out.decode()).replace('"','') if out else ''
		return err, c