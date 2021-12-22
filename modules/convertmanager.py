import sys, os
import subprocess

#aspect = orgwidth/orgheight
#scriptheight = 800 / aspect
#scale = aspect * 10
#usr/bin/convert photo.jpg -limit thread 1 \( +clone \( -clone 0 -gravity center -sample scriptheight -scale scale% -resize 800x -crop 800x+0+0 +repage \) \( -clone 0 -sample x480 \) -delete 0 -gravity center -compose over -composite -auto-gamma -channel rgb -auto-level -normalize -brightness-contrast 0,10 -dither FloydSteinberg -remap pattern:gray50 -background white -gravity center -extent 800x480 -type bilevel -write ./photo2.bmp \) NULL:


class convertmanager:
	
	__ERROR_VALUE_TEXT = 'Configuration background_color should be one of {}'
	
	__INVERT_FLAG = "-negate"
	__ROTATE_CODE = '-rotate 90'
	__BACK_COLORS = ["white", "black", "photo"]
	
	__GET_PHOTO_SIZE_CODE = '{} {} -format "%w,%h" info:'
	
	#Don't use blur! Blur will kill Raspberry Pi Zero.
	#Resizing to huge and then scaling to small will add some blur and it's 10x faster than blur operation.
	__PHOTO_BACK_CODE = '( -clone 0 -gravity center -sample x{} -scale {}% -resize {}x -crop {}x+0+0 +repage ) ( -clone 0 -sample x{} ) -delete 0 -gravity center -compose over -composite '
	__PHOTO_RESIZE_CODE = '-sample {}x{} '
		
	#options for ImageMagick converter
	#https://legacy.imagemagick.org/Usage/quantize/
	__CONVERT_OPTIONS = {
		'1'	:	'{} {} -limit thread 1 {} ( +clone {}{}-brightness-contrast 0,10 -dither FloydSteinberg -remap pattern:gray50 {}-background {} -gravity center -extent {}x{} -type bilevel -write {} ) {} NULL:',
		'2'	:	'{} {} -limit thread 1 {} ( +clone {}{}-dither FloydSteinberg {}-background {} -gravity center -extent {}x{} -type bilevel -write {} ) {} NULL:',
		'3'	:	'{} {} -limit thread 1 {} ( +clone {}{}-dither FloydSteinberg -remap pattern:gray50 {}-background {} -gravity center -extent {}x{} -type bilevel -write {} ) {} NULL:',
		'4'	:	'{} {} -limit thread 1 {} ( +clone {}{}-dither FloydSteinberg -ordered-dither o4x4 {}-background {} -gravity center -extent {}x{} -type bilevel -write {} ) {} NULL:',
		'5'	:	'{} {} -limit thread 1 {} ( +clone {}{}{}-background {} -gravity center -extent {}x{} -type bilevel -write {} ) {} NULL:',
		'6'	:	'{} {} -limit thread 1 {} ( +clone {}{}-colors 2 +dither {}-background {} -gravity center -extent {}x{} -type bilevel -write {} ) {} NULL:'
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
	
	def __convert_option (self, origwidth:int, origheight:int, option:int, bin:str, srcfile:str, width:int, height:int, invert:int, horizontal:int, back:str, target:str, thumborgfile:str, thumbconvfile:str):
		if int(option) > len(self.__CONVERT_OPTIONS) or int(option) < 1: option = 1
		
		#space at the end as those flag are optional
		negate = self.__INVERT_FLAG + " " if invert == 1 else ''
		rotate = self.__ROTATE_CODE + " " if horizontal == 0 else ''
			
		
		back = back.strip().lower()		
				
		if not back in self.__BACK_COLORS:
			back = self.__BACK_COLORS[0]

		if back == "photo":
			back = self.__BACK_COLORS[0]
			#this takes more time to progress		
			aspectratio = int(origwidth) / int(origwidth)
			newheight = int(width / aspectratio)
			scale = round(aspectratio * 10.0, 2)
			code = self.__PHOTO_BACK_CODE.format(newheight, scale, width, width, height)
			
		else:
			code = self.__PHOTO_RESIZE_CODE.format(width, height)
		
		thumb1st = self.__THUMB_1ST_PART.format(width, height, width, height, thumborgfile)
		thumb2nd = self.__THUMB_2ND_PART.format(thumbconvfile)
		
		ret = self.__CONVERT_OPTIONS[str(option)].format(bin, srcfile, thumb1st, rotate, code, negate, back, width, height, target, thumb2nd)
		print (ret.replace('(','\(').replace(')','\)'))
		return ret
	
	def convert_image (self, origwidth:int, origheight:int, option:int, bin:str, srcfile:str, width:int, height:int, invert:int, horizontal:int, back:str, target:str, thumborgfile:str, thumbconvfile:str):
		args = (self.__convert_option(origwidth, origheight, option, bin, srcfile, width, height, invert, horizontal, back, target, thumborgfile, thumbconvfile)).split()
		process = subprocess.Popen(args, stdout=subprocess.PIPE)
		process.wait()
		out, err = process.communicate()
		return err
	
	def get_image_size (self, bin:str, srcfile:str):
		args = (self.__GET_PHOTO_SIZE_CODE.format(bin, srcfile)).split()
		process = subprocess.Popen(args, stdout=subprocess.PIPE)
		process.wait()
		out, err = process.communicate()
		wh = str(out.decode()).replace('"','').split(',')
		width = wh[0]
		height = wh[1]
		return err, width, height