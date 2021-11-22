from PIL import Image, ImageDraw, ImageFont
import math
from modules.weathermanager import weathermanager

class weatherstampmanager:
	
	__POSITION_VALUES = [0, 1, 2, 3]

	__FONTS = {
		'WEATHER_FONT' : 	'fonts/weathericons-regular-webfont.ttf',
		'NORMAL_FONT' :		'fonts/NotoSans-SemiCondensed.ttf'
	}
	
	__COLORS = {
		'WHITE' : 		255,
		'BLACK' : 		0
	}
	
	__MARGIN = 10
	__SPACE = 5

	__ICONS = {
		'01d' : 				'\uf00d',
		'01n' : 				'\uf02e',
		'10d' : 				'\uf015',
		'10n' : 				'\uf015',
		'09d' : 				'\uf017',
		'13d' : 				'\uf01b',
		'13n' : 				'\uf01b',
		'50d' : 				'\uf021',
		'50n' : 				'\uf021',
		'09n' : 				'\uf013',
		'02d' : 				'\uf002',
		'03d' : 				'\uf002',
		'04d' : 				'\uf002',
		'02n' : 				'\uf086',
		'03n' : 				'\uf086',
		'04n' : 				'\uf086',
		'11d' : 				'\uf01e',
		'11n' : 				'\uf01e'
	}
	
	__DEGREES = '\u00b0'
	
	__ERROR_VALUE_TEXT = 'Configuration position should be one of {}'
	__ERROR_CVALUE_TEXT = 'Configuration font_color should be one of {}'
	
	def __init__ (self, outputfile, width, height, horizontal, font, color, position):
		self.__outputfile = outputfile
		self.__width = width
		self.__height = height
		self.__font = font
		self.__position = position
		self.__color = color
		self.__horizontal = horizontal

	@classmethod		
	def verify_position (self, val):
		if not int(val) in self.__POSITION_VALUES:
			raise Exception(self.__ERROR_VALUE_TEXT.format(self.__POSITION_VALUES))

	@classmethod		
	def get_positions (self):
		return self.__POSITION_VALUES
	
	@classmethod		
	def verify_color (self, val):
		if not val in [k.lower() for k in self.__COLORS.keys()]:
			raise Exception(self.__ERROR_CVALUE_TEXT.format([k.lower() for k in self.__COLORS.keys()]))
			
	@classmethod		
	def get_colors (self):
		return [k.lower() for k in self.__COLORS.keys()]

	def compose(self, temp, units, icon):
		image = Image.open(self.__outputfile).convert('1')
		
		if not self.__horizontal: image = image.transpose(Image.ROTATE_90) 
		
		draw = ImageDraw.Draw(image)

		fontt = ImageFont.truetype(self.__FONTS['NORMAL_FONT'], self.__font)
		wfont = ImageFont.truetype(self.__FONTS['WEATHER_FONT'], self.__font)

		textw = self.__ICONS[icon]	
		sizew = draw.textlength(textw, font = wfont)
		
		textt = "{}{}{}".format(int(math.ceil(temp)), self.__DEGREES, "C" if weathermanager.is_metric(units) else "F" )
		sizet = draw.textlength(textt, font = fontt)
		
		x = self.__MARGIN
		y = self.__MARGIN
		
		if self.__position in [1, 3]:
			x = self.__width - sizew - self.__SPACE - sizet - self.__MARGIN
			
		if self.__position in [2, 3]:
			y = self.__height - self.__MARGIN - self.__font

		fillcolor = self.__COLORS[self.__color.upper()]
		strokecolor = (self.__COLORS['WHITE'] + self.__COLORS['BLACK']) - fillcolor
		
		draw.text((x, y), textw, font = wfont, fill = fillcolor, stroke_width=2, stroke_fill=strokecolor)
		draw.text((x + sizew + self.__SPACE, y), textt, font = fontt, fill = fillcolor, stroke_width=2, stroke_fill=strokecolor)
		
		if not self.__horizontal: image = image.transpose(Image.ROTATE_270) 
		image.save(self.__outputfile)