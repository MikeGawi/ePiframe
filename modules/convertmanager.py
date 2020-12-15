import sys, os
import subprocess

class convertmanager:
	
	__INVERT_FLAG = "-negate"
	__ROTATE_CODE = '-rotate "90"'
	__BACK_COLORS = ["white", "black", "photo"]
	__SCALE_HORIZON = '-scale 2.51%'
	__SCALE_VERTIC = '-scale 4%'
	
	#Don't use blur! Blur will kill Raspberry Pi Zero.
	#Resizing to huge and then scaling to small will add some blur and it's 10x faster than blur operation.
	__PHOTO_BACK_CODE = '( -clone 0 -gravity center ' + __SCALE_HORIZON + ' -resize 4000% -crop {}x{}+0+0 +repage ) ( -clone 0 -resize {}x{} ) -delete 0 -gravity center -compose over -composite'
	
	#options for ImageMagick converter
	#https://www.imagemagick.org/Usage/quantize/
	#1st {} is for convert binary path, 2nd - source file, 3rd rotation, 4th - photo background code (optional),  {}x{} - size, 7th - invert colors, 8th - back color, 9th&10th frame size, last {} - target file
	__CONVERT_OPTIONS = {
		'1'	:	'{} {} {}{}-brightness-contrast 0,20 -resize {}x{} -dither FloydSteinberg -remap pattern:gray50 {}-background {} -gravity center -extent {}x{} -type bilevel {}',
		'2'	:	'{} {} {}{}-resize {}x{} -dither FloydSteinberg {}-background {} -gravity center -extent {}x{} -type bilevel {}',
		'3'	:	'{} {} {}{}-resize {}x{} -dither FloydSteinberg -remap pattern:gray50 {}-background {} -gravity center -extent {}x{} -type bilevel {}',
		'4'	:	'{} {} {}{}-resize {}x{} -dither FloydSteinberg -ordered-dither o4x4 {}-background {} -gravity center -extent {}x{} -type bilevel {}',
		'5'	:	'{} {} {}{}-resize {}x{} {}-background {} -gravity center -extent {}x{} -type bilevel {}',
		'6'	:	'{} {} {}{}-resize {}x{} -colors 2 +dither {}-background {} -gravity center -extent {}x{} -type bilevel {}'
	}
		
	def __convert_option (self, origwidth:int, origheight:int, option:int, bin:str, srcfile:str, width:int, height:int, invert:int, horizontal:int, back:str, target:str):
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
			aspectratio = width / height
			newheight = int(int(origwidth) / aspectratio)
			#space at the end as this flag is optional
			code = self.__PHOTO_BACK_CODE.format(origwidth, newheight, origwidth, newheight) + " "
			
			#bigger scale to cover whole screen in vertical position
			if horizontal == 0: code = code.replace(self.__SCALE_HORIZON, self.__SCALE_VERTIC)
		else:
			code = ''
		
		ret = self.__CONVERT_OPTIONS[str(option)].format(bin, srcfile, rotate, code, width, height, negate, back, width, height, target)
		print (ret)
		return ret
	
	def convert_image (self, origwidth:int, origheight:int, option:int, bin:str, srcfile:str, width:int, height:int, invert:int, horizontal:int, back:str, target:str):
		args = (self.__convert_option(origwidth, origheight, option, bin, srcfile, width, height, invert, horizontal, back, target)).split()
		process = subprocess.Popen(args, stdout=subprocess.PIPE)
		process.wait()
		out, err = process.communicate()
		return err