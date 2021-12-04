from flask import Flask, render_template, request, redirect, jsonify, send_file, flash, session
from flask_login import LoginManager, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from time import sleep
from wtforms import StringField, BooleanField, IntegerField, SelectField
from modules.configmanager import configmanager
from modules.usersmanager import usersmanager
from modules.databasemanager import databasemanager
from misc.configprop import configprop
from misc.constants import constants
from werkzeug.utils import secure_filename
import re, os, glob, logging, base64

class webuimanager:

	__SETTINGS_HTML = 'settings.html'
	__LOGS_HTML = 'logs.html'
	__TOOLS_HTML = 'tools.html'
	__INDEX_HTML = 'index.html'
	__HTML_IND = '.html'
	
	__THUMB_TAG = 'thumb'
	__FILE_TAG = 'file'
	__THUMB_IND = 'thumb_'
	__ORIGINAL_TAG = 'original'
	
	__NO_PHOTO_ERROR = 'No Photo!'
	
	__HTML_IS_INVALID = " is-invalid"
	__HTML_INVALID = "invalid"
	__HTML_CLASS = 'class'
	__HTML_FILL = 'fill'
	__HTML_FLEX_FILL = 'flex-fill'
	__HTML_CLASSDEP = 'classdep'
	__HTML_PAD = 'pad'
	__HTML_FORM = ' form-control form-control-sm'
	__HTML_SELECT = ' form-select form-select-sm'
	__HTML_DISABLED = 'disabled'
	__HTML_PX3 = 'px-3'
	__HTML_CHECKBOX = ' checkbox form-check-input'

	__BUT_DEFAULTS = 'DEFAULTS'
	__BUT_CANCEL = 'CANCEL'
	__BUT_SAVE = 'SAVE'

	__FALSE_VALS = (0, '0', '')

	__REBOOT_ACT = 'reboot'
	__RESTART_ACT = 'restart'
	__POWEROFF_ACT = 'poweroff'
	__NEXT_ACT = 'next'
	
	__form = None
	__current = None

	def __init__ (self, backend):
		self.__backend = backend
		
		self.app = Flask(__name__, root_path=backend.get_path())
		self.app.config['SECRET_KEY'] = constants.EPIFRAME_SECRET
		
		self.app.add_url_rule('/get_image', view_func=self.get_image)
		self.app.add_url_rule('/get_status', view_func=self.get_status)
		self.app.add_url_rule('/_upload_photo', view_func=self.upload_photo, methods=['POST'])
		self.app.add_url_rule('/_log_stream', view_func=self.stream)
		self.app.add_url_rule('/_tools$', methods=['GET'], view_func=self.tools_functions)
		self.app.add_url_rule('/_tools$<action>', methods=['GET'], view_func=self.tools_functions)
		self.app.add_url_rule('/<url>', methods=['GET', 'POST'], view_func=self.handle)
		self.app.add_url_rule('/', defaults={'url': ''}, methods=['GET', 'POST'], view_func=self.handle)
		self.app.add_url_rule('/settings/<variable>', methods=['GET', 'POST'], view_func=self.setting)
		self.app.add_url_rule('/logout', view_func=self.logout)
		self.app.add_url_rule('/login', methods=['GET', 'POST'], view_func=self.login)
		
		self.app.add_url_rule('/api/get_image', view_func=self.get_image)
		self.app.add_url_rule('/api/get_status', view_func=self.get_status)
		self.app.add_url_rule('/api/get_log', view_func=self.stream)
		self.app.add_url_rule('/api/upload_photo', view_func=self.upload_photo, methods=['POST'])
		self.app.add_url_rule('/api/action=', methods=['GET'], view_func=self.tools_functions)
		self.app.add_url_rule('/api/action=<action>', methods=['GET'], view_func=self.tools_functions)
				
		self.__login_manager = LoginManager()
		self.__login_manager.init_app(self.app)
		self.__login_manager.login_view = "login"
		self.__login_manager.user_loader(self.load_user)									   
		self.__login_manager.request_loader(self.load_user_from_request)									   
	
	def start(self):
		log = logging.getLogger('werkzeug')
		if log:	log.setLevel(logging.CRITICAL)
		
		self.__dbman = databasemanager()
		self.__usersman=usersmanager(self.__dbman)
		
		self.app.config['LOGIN_DISABLED'] = not self.__usersman.login_needed()		
		self.app.run(host=self.config().get('web_host'), port=self.config().get('web_port'), debug=False)

	def config(self):
		return self.__backend.get_config()
		
	def __adapt_name(self, name):
		return ('- ' if self.config().get_property(name).get_dependency() else str()) + name.replace("_"," ").title()
	
	#@app.route('/login')
	def login(self):
		if request.method == 'POST':
			username = request.form.get('username')
			password = request.form.get('password')
			remember = True if request.form.get('remember') else False
			
			if username:
				try:
					self.__usersman.check(username, password)
					login_user(self.load_user(username), remember=remember)
				except Exception:
					pass
					flash('Please check your login details and try again!')
			else:
				flash('Please fill in all required data!')
			return redirect('/')
		else:
			return render_template('login.html')

	#@app.route('/logout')
	@login_required	
	def logout(self):
		logout_user()
		return redirect('/')
	
	def load_user(self, username):
		ret = None
		
		try:
			res = self.__usersman.get_by_username(username)					
			ret = res[0] if res and len(res)>0 else None
		except Exception:
			pass
						
		return ret
	
	def load_user_from_request(self, request):
		result = None
		api_key = request.args.get('api_key')

		if not api_key:
			api_key = request.headers.get('Authorization')
			if api_key:
				api_key = api_key.replace('Basic ', '', 1)
				
				try:
					key = base64.b64decode(api_key)
					if not '\\' in key.decode():
						api_key = key.decode()
				except Exception:
					pass
							
		if api_key:
			try:
				res = self.__usersman.get_by_api(api_key)					
				result = res[0] if res and len(res)>0 else None
			except Exception:
				pass

		return result
	
	#@app.route('/get_image')
	@login_required
	def get_image(self):
		thumb = self.__THUMB_IND if self.__THUMB_TAG in request.args else str()
		filename = str()

		if self.__ORIGINAL_TAG in request.args:
			if not thumb:
				files = glob.glob('{}.*'.format(self.__backend.get_download_file()))
				if files: 
					filename = max(files, key=os.path.getctime)
			else:
				filename = self.__backend.get_filename_if_exists('thumb_photo_download_name')
		else:
			filename = self.__backend.get_filename_if_exists(thumb+'photo_convert_filename')
			
		return send_file(filename, mimetype=constants.EXTENSION_TO_TYPE[str(filename).rsplit('.')[-1].lower()]) if filename else self.__NO_PHOTO_ERROR

	#@app.route('/_get_status')
	@login_required
	def get_status(self):
		mem = self.__backend.get_mem()
		load = self.__backend.get_load()
		uptime = self.__backend.get_uptime()
		state = self.__backend.get_state()
		service = self.__backend.get_service_state()
		temp = self.__backend.get_temp()
		update = self.__backend.get_next_time()

		original = self.__backend.get_filename_modtime_if_exists('thumb_photo_download_name')
		converted = self.__backend.get_filename_modtime_if_exists('thumb_photo_convert_filename')

		return jsonify(mem=mem+'%', load=load, uptime=uptime, state=state, temp=temp, update=update, service=service, original=original, converted=converted, version=constants.EPIFRAME_VERSION)

	#@app.route('/_upload_photo', methods=['POST'])
	@login_required
	def upload_photo(self):
		is_api = 'REQUEST_URI' in request.environ and request.environ['REQUEST_URI'] and '/api/' in request.environ['REQUEST_URI']
		res = jsonify(status="OK")
		
		if request.method == 'POST':
			file = request.files[self.__FILE_TAG]
			extension = file.filename.rsplit('.')[-1].lower()
			if file and extension in constants.EXTENSIONS:
				filename = secure_filename(file.filename)
				file.save(self.__backend.get_download_file() + '.' + extension)
			else: res = jsonify(error="File unknown!")
			self.__backend.refresh_frame()
		else: res = jsonify(error="Method Not Allowed!")
		
		return res if is_api else redirect('/')

	#@app.route('/_log_stream')
	@login_required
	def stream(self):
		if not os.path.exists(self.config().get('log_files')): 
			os.makedirs(os.path.dirname(self.config().get('log_files')), exist_ok=True)
			open(self.config().get('log_files'), 'a').close()
		with open(self.config().get('log_files')) as f:
				content = f.read()
		return self.app.response_class(content, mimetype='text/plain')

	#@app.route('/', defaults={'url': ''})
	#@app.route('/<url>', methods=['GET', 'POST'])
	@login_required
	def handle(self, url=str()):
		template = render_template(self.__INDEX_HTML, version=constants.EPIFRAME_VERSION)
		if url == self.__TOOLS_HTML.replace(self.__HTML_IND, str()): 
			template = render_template(self.__TOOLS_HTML, version=constants.EPIFRAME_VERSION)
		elif url == self.__LOGS_HTML.replace(self.__HTML_IND, str()):
			template = render_template(self.__LOGS_HTML)
		elif url == self.__SETTINGS_HTML.replace(self.__HTML_IND, str()):
			self.__backend.refresh()
			template = redirect('/{}/{}'.format(self.__SETTINGS_HTML.replace(self.__HTML_IND, str()), str(self.config().get_sections()[0])))
		return template

	#@app.route('/_tools$', methods=['GET'])
	#@app.route('/_tools$<action>', methods=['GET'])
	@login_required
	def tools_functions(self, action=str()):
		res = jsonify(status="OK")
		if request.method == 'GET':
			if action:
				if action == self.__REBOOT_ACT: self.__backend.reboot()
				elif action == self.__RESTART_ACT: self.__backend.restart()
				elif action == self.__POWEROFF_ACT: self.__backend.poweroff()
				elif action == self.__NEXT_ACT: self.__backend.fire_event(self.__backend.get_empty_params())
				else: res = jsonify(error="Action Unknown!")
			else: res = jsonify(error="No Action!")
		else: res = jsonify(error="Method Not Allowed!")
		return res

	#@app.route('/settings/<variable>', methods=['GET', 'POST'])
	@login_required
	def setting(self, variable=str()):
		class MyForm(FlaskForm):
			pass

		if variable:
			self.__current = variable
		else:
			self.__current = self.config().get_sections()[0]

		props = self.config().get_section_properties(self.__current)	

		if request.method == 'POST':
			for n in props:
				if self.config().get_property(n).get_type() != configprop.BOOLEAN_TYPE:
					if request.form.get(n) != None:
						self.config().set(n, str(request.form.get(n)))
				else:
					self.config().set(n, '1' if str(request.form.get(n)) == 'y' else '0')			
			s = re.search(r"\-\<\[.*?\]\>\-", str(request.form))
			if s:
				propname = s.group(0).replace('-<[','').replace(']>-','')
				self.config().set(propname, str(self.config().get_default(propname)))
			elif request.form.get(self.__BUT_SAVE) == self.__BUT_SAVE:
				try:
					self.config().verify_warnings()
				except Warning as e:
					flash(str(e))
					pass
				try:
					self.config().verify_exceptions()
					self.config().save()
				except Exception:
					session.pop('_flashes', None)
					pass		
			elif request.form.get(self.__BUT_DEFAULTS) == self.__BUT_DEFAULTS:
				for n in props:
					self.config().set(n, str(self.config().get_default(n)))
			elif request.form.get(self.__BUT_CANCEL) == self.__BUT_CANCEL:
				self.config().read_config()
			return redirect('/{}/{}'.format(self.__SETTINGS_HTML.replace(self.__HTML_IND, str()), self.__current))		

		for n in props:
			prop = self.config().get_property(n)
			render = {}
			render[self.__HTML_CLASS] = self.__HTML_FORM
			render[self.__HTML_FILL] = self.__HTML_FLEX_FILL
			if prop.get_dependency():
				render[self.__HTML_CLASS] = (str(prop.get_dependency()) if prop.get_dependency() else '') + self.__HTML_FORM
				render[self.__HTML_PAD] = self.__HTML_PX3		
				render[self.__HTML_CLASSDEP] = prop.get_dependency()
				if not bool(self.config().getint(prop.get_dependency())):
					render[self.__HTML_DISABLED] = self.__HTML_DISABLED

			if prop.get_type() == configprop.STRING_TYPE or prop.get_type() == configprop.INTEGER_TYPE:
				if prop.get_possible():
					render[self.__HTML_CLASS] = (str(prop.get_dependency()) if prop.get_dependency() else '') + self.__HTML_SELECT
					render[self.__HTML_FILL] = str()
					setattr(MyForm, n, SelectField(self.__adapt_name(n), default=self.config().get_default(n), choices=prop.get_possible(), render_kw=render, description=self.config().get_comment(n)))
				elif prop.get_type() == configprop.STRING_TYPE:
					setattr(MyForm, n, StringField(self.__adapt_name(n), default=self.config().get_default(n), description=self.config().get_comment(n), render_kw=render))
				else:
					render[self.__HTML_FILL] = str()					
					setattr(MyForm, n, IntegerField(self.__adapt_name(n), default=self.config().get_default(n), render_kw=render, description=self.config().get_comment(n)))
			elif prop.get_type() == configprop.FILE_TYPE:
				setattr(MyForm, n, StringField(self.__adapt_name(n), default=self.config().get_default(n), render_kw=render, description=self.config().get_comment(n)))
			elif prop.get_type() == configprop.BOOLEAN_TYPE:
				render[self.__HTML_CLASS]  = (str(prop.get_dependency()) if prop.get_dependency() else '') + self.__HTML_CHECKBOX
				setattr(MyForm, n, BooleanField(self.__adapt_name(n), default=self.config().get_default(n), false_values=self.__FALSE_VALS, description=self.config().get_comment(n),render_kw=render))
			elif prop.get_type() == configprop.STRINGLIST_TYPE:
				setattr(MyForm, n, StringField(self.__adapt_name(n), default=self.config().get_default(n), render_kw=render, description=self.config().get_comment(n)))
			elif prop.get_type() == configprop.INTLIST_TYPE:
				setattr(MyForm, n, StringField(self.__adapt_name(n), default=self.config().get_default(n), render_kw=render, description=self.config().get_comment(n)))		

		self.__form = MyForm(data = [(name, self.config().get(name)) for name in props if self.config().get_property(name).get_type() != configprop.BOOLEAN_TYPE])
		for i in [prop for prop in props if self.config().get_property(prop).get_type() == configprop.BOOLEAN_TYPE]:
			getattr(self.__form, i).data = self.config().getint(i)
		
		reset_needed = False
		for i in props:
			if self.config().get_property(i).get_resetneeded():
				reset_needed = True
			try:
				self.config().validate(i)
				getattr(self.__form, i).errors = ()
			except Warning:
				getattr(self.__form, i).errors = ()
				pass
			except Exception as e:
				getattr(self.__form, i).errors = (e)
				getattr(self.__form, i).render_kw[self.__HTML_CLASS] += self.__HTML_IS_INVALID
				getattr(self.__form, i).render_kw[self.__HTML_INVALID] = self.__HTML_IS_INVALID

		return render_template(self.__SETTINGS_HTML, form=self.__form, navlabels=self.config().get_sections(), reset_needed=reset_needed, version=constants.EPIFRAME_VERSION)	