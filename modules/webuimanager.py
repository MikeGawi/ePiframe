from flask import Flask, render_template, request, redirect, jsonify, send_file, flash, session
from flask_login import LoginManager, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, IntegerField, SelectField, FloatField
from wtforms.widgets import NumberInput, PasswordInput
from modules.usersmanager import usersmanager
from modules.databasemanager import databasemanager
from misc.configprop import configprop
from misc.constants import constants
from werkzeug.utils import secure_filename
import modules.configmanager as confman 
from tempfile import mkstemp
import re, os, glob, logging, base64

class webuimanager:

	__SETTINGS_HTML = 'settings.html'
	__PLUGINS_HTML = 'plugins.html'
	__LOGS_HTML = 'logs.html'
	__STATS_HTML = 'stats.html'
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
	__HTML_CLASSDEPVAL = 'depval'
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
	
	class site_bind:
		def __init__ (self, url, func, methods = ['GET'], defaults = None):
			self.url = url
			self.func = func
			self.methods = methods
			self.defaults = defaults
			
	class menu_entry:
		def __init__ (self, name, url, id, icon):
			self.url = url
			self.icon = icon
			self.name = name
			self.id = id
			
	class action_entry:
		def __init__ (self, name, func, icon, action):
			self.func = func
			self.name = name
			self.icon = icon
			self.action = action
	
	def __init__ (self, backend):
		self.__backend = backend
		self.__dbman = databasemanager()
		self.__usersman = usersmanager(self.__dbman)
		
		self.app = Flask(__name__, root_path=backend.get_path())
		self.app.config['SECRET_KEY'] = constants.EPIFRAME_SECRET
		
		self.MENU = [
			self.menu_entry('Home', '/', 'home-menu', 'bi bi-house'),		
			self.menu_entry('Logs', '/logs', 'logs-menu', 'bi bi-activity'),		
			self.menu_entry('Stats', '/stats', 'stats-menu', 'bi bi-graph-up'),		
			self.menu_entry('Settings', '/settings', 'settings-menu', 'bi bi-gear'),		
			self.menu_entry('Tools', '/tools', 'tools-menu', 'bi bi-tools'),
			self.menu_entry('Plugins', '/plugins', 'plugins-menu', 'bi bi-plug')
		]
		
		self.WEBSITES = [
			self.site_bind('/get_image', self.get_image),
			self.site_bind('/get_status', self.get_status),
			self.site_bind('/_log_stream', self.stream),
			self.site_bind('/_upload_photo', self.upload_photo, methods=['POST']),
			self.site_bind('/_tools$', self.tools_functions),
			self.site_bind('/_tools$<action>', self.tools_functions),
			self.site_bind('/<url>', self.handle, methods=['GET', 'POST']),
			self.site_bind('/', self.handle, methods=['GET', 'POST'], defaults={'url': ''}),
			self.site_bind('/settings/<variable>', self.setting, methods=['GET', 'POST'], defaults={'variable': ''}),
			self.site_bind('/plugins', self.plugins, methods=['GET', 'POST']),
			self.site_bind('/logout', self.logout),
			self.site_bind('/login', self.login, methods=['GET', 'POST']),
			self.site_bind('/export', self.export),
			self.site_bind('/import', self.import_settings, methods=['POST'])			
		]

		for site in self.WEBSITES:
			self.app.add_url_rule(site.url, methods=site.methods, view_func=site.func)
		
		for plug in self.__backend.get_plugins().plugin_website():
			for ws in plug.add_website(self, self.__usersman, self.__backend):
				self.app.register_blueprint(ws, url_prefix='/')
				
		self.API = [
			self.site_bind('/api/get_image', self.get_image),
			self.site_bind('/api/get_status', self.get_status),
			self.site_bind('/api/get_log', self.stream),
			self.site_bind('/api/upload_photo', self.upload_photo, methods=['POST']),
			self.site_bind('/api/action=', self.tools_functions),
			self.site_bind('/api/action=<action>', self.tools_functions)
		]
		
		for plug in self.__backend.get_plugins().plugin_api():	self.API += plug.extend_api(self, self.__usersman, self.__backend)
		
		for api_site in self.API: self.app.add_url_rule(api_site.url, methods=api_site.methods, view_func=api_site.func, defaults=api_site.defaults)		
		
		self.ACTIONS = {
			self.__NEXT_ACT : self.action_entry('Next Photo', self.__backend.next_photo, 'bi bi-skip-end', self.__NEXT_ACT),
			self.__RESTART_ACT : self.action_entry('Restart Service', self.__backend.restart, 'bi bi-arrow-repeat', self.__RESTART_ACT),
			self.__REBOOT_ACT : self.action_entry('Reboot', self.__backend.reboot, 'bi bi-arrow-counterclockwise', self.__REBOOT_ACT)
		}
		
		def merge_dicts(x, y):
			z = x.copy()
			z.update(y)
			return z
		
		for plug in self.__backend.get_plugins().plugin_action(): self.ACTIONS = merge_dicts(self.ACTIONS, plug.add_action(self, self.__usersman, self.__backend))
				
		self.app.context_processor(self.inject_context)
				
		self.__login_manager = LoginManager()
		self.__login_manager.init_app(self.app)
		self.__login_manager.login_view = "login"
		self.__login_manager.user_loader(self.load_user)									   
		self.__login_manager.request_loader(self.load_user_from_request)									   
	
	def add_menu_entries(self, entries): 
		self.MENU += entries
	
	def get_app(self):
		return self.app
	
	def inject_context(self):
		return dict(dark_theme=bool(self.config().getint('dark_theme')), menu=self.MENU if bool(self.config().getint('show_stats')) else [x for x in self.MENU if x.name != 'Stats' and x.url != '/stats'])
	
	def start(self):
		log = logging.getLogger('werkzeug')
		if log:	log.setLevel(logging.CRITICAL)
		
		self.app.config['LOGIN_DISABLED'] = not self.__usersman.login_needed()		
		self.app.run(host=self.config().get('web_host'), port=self.config().get('web_port'), debug = False)

	def config(self):
		return self.__backend.get_config()
		
	def __adapt_name(self, config, name):
		return ('- ' if config.get_property(name).get_dependency() else str()) + name.replace("_"," ").title()
	
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
	
	#@app.route('/export')
	@login_required
	def export(self):
		return send_file(constants.CONFIG_FILE, as_attachment=True)
	
	#@app.route('/import', methods=['POST'])
	@login_required
	def import_settings(self):
		if request.method == 'POST':
			file = request.files[self.__FILE_TAG]
			if file:
				filename = secure_filename(file.filename)
				status, temp = mkstemp(text=True)
				file.save(temp)
				
				try:
					temp_conf = confman.configmanager(temp, constants.CONFIG_FILE_DEFAULT)
					temp_conf.verify()
					temp_conf.save(constants.CONFIG_FILE)
					self.__backend.refresh()
					flash("File has been imported successfully!")
				except Exception as e:
					flash("Error importing settings file: {}".format(str(e)))
					pass
				finally:
					if os.path.exists(temp):
						os.remove(temp)
		return redirect('/{}'.format(self.__SETTINGS_HTML.replace(self.__HTML_IND, str())))	

	#@app.route('/', defaults={'url': ''})
	#@app.route('/<url>', methods=['GET', 'POST'])
	@login_required
	def handle(self, url=str()):
		template = render_template(self.__INDEX_HTML, version=constants.EPIFRAME_VERSION)
		if url == self.__TOOLS_HTML.replace(self.__HTML_IND, str()): 
			template = render_template(self.__TOOLS_HTML, version=constants.EPIFRAME_VERSION, actions=list(self.ACTIONS.values()))
		elif url == self.__LOGS_HTML.replace(self.__HTML_IND, str()):
			template = render_template(self.__LOGS_HTML)
		elif url == self.__STATS_HTML.replace(self.__HTML_IND, str()):
			template = render_template(self.__STATS_HTML, version=constants.EPIFRAME_VERSION)
		elif url == self.__SETTINGS_HTML.replace(self.__HTML_IND, str()):
			self.__backend.refresh()
			template = redirect('/{}/{}'.format(self.__SETTINGS_HTML.replace(self.__HTML_IND, str()), str(self.config().get_sections()[0])))
		elif url == self.__PLUGINS_HTML.replace(self.__HTML_IND, str()):
			self.__backend.refresh()
			template = redirect('/{}'.format(self.__PLUGINS_HTML.replace(self.__HTML_IND, str())))
		return template

	#@app.route('/_tools$', methods=['GET'])
	#@app.route('/_tools$<action>', methods=['GET'])
	@login_required
	def tools_functions(self, action=str()):
		res = jsonify(status="OK")
		if request.method == 'GET':
			if action:
				if action in self.ACTIONS: self.ACTIONS[action].func()
				elif action == self.__POWEROFF_ACT: self.__backend.poweroff()
				else: res = jsonify(error="Action Unknown!")
			else: res = jsonify(error="No Action!")
		else: res = jsonify(error="Method Not Allowed!")
		return res

	def __build_settings(self, config, props):
		class MyForm(FlaskForm): pass
		
		for n in props:
			prop = config.get_property(n)
			render = {}
			render[self.__HTML_CLASS] = (str(prop.get_dependency()) if prop.get_dependency() else '') + self.__HTML_FORM
			render[self.__HTML_FILL] = self.__HTML_FLEX_FILL
			if prop.get_dependency():
				render[self.__HTML_PAD] = self.__HTML_PX3		
				render[self.__HTML_CLASSDEP] = prop.get_dependency()
				render[self.__HTML_CLASSDEPVAL] = prop.get_dependency_value() if prop.get_dependency_value() else '1'
				if (not prop.get_dependency_value() and not bool(config.getint(prop.get_dependency()))) or (prop.get_dependency_value() and not config.get(prop.get_dependency()) == prop.get_dependency_value()):
					render[self.__HTML_DISABLED] = self.__HTML_DISABLED

			if prop.get_type() == configprop.STRING_TYPE or prop.get_type() == configprop.INTEGER_TYPE or prop.get_type() == configprop.FLOAT_TYPE:
				if prop.get_possible():
					render[self.__HTML_CLASS] = (str(prop.get_dependency()) if prop.get_dependency() else '') + self.__HTML_SELECT
					render[self.__HTML_FILL] = str()
					setattr(MyForm, n, SelectField(self.__adapt_name(config, n), default=config.get_default(n), choices=prop.get_possible(), render_kw=render, description=config.get_comment(n)))
				elif prop.get_type() == configprop.STRING_TYPE:
					setattr(MyForm, n, StringField(self.__adapt_name(config, n), default=config.get_default(n), description=config.get_comment(n), render_kw=render))
				elif prop.get_type() == configprop.INTEGER_TYPE:
					render[self.__HTML_FILL] = str()					
					setattr(MyForm, n, IntegerField(self.__adapt_name(config, n), widget=NumberInput(min = prop.get_min(), max = prop.get_max()), default=config.get_default(n), render_kw=render, description=config.get_comment(n)))
				else:
					render[self.__HTML_FILL] = str()					
					setattr(MyForm, n, FloatField(self.__adapt_name(config, n), widget=NumberInput(min = prop.get_min(), max = prop.get_max(), step = "any"), default=config.get_default(n), render_kw=render, description=config.get_comment(n)))
			elif prop.get_type() == configprop.FILE_TYPE:
				setattr(MyForm, n, StringField(self.__adapt_name(config, n), default=config.get_default(n), render_kw=render, description=config.get_comment(n)))
			elif prop.get_type() == configprop.BOOLEAN_TYPE:
				render[self.__HTML_CLASS]  = (str(prop.get_dependency()) if prop.get_dependency() else '') + self.__HTML_CHECKBOX
				setattr(MyForm, n, BooleanField(self.__adapt_name(config, n), default=config.get_default(n), false_values=self.__FALSE_VALS, description=config.get_comment(n), render_kw=render))
			elif prop.get_type() == configprop.STRINGLIST_TYPE:
				setattr(MyForm, n, StringField(self.__adapt_name(config, n), default=config.get_default(n), render_kw=render, description=config.get_comment(n)))
			elif prop.get_type() == configprop.INTLIST_TYPE:
				setattr(MyForm, n, StringField(self.__adapt_name(config, n), default=config.get_default(n), render_kw=render, description=config.get_comment(n)))
			elif prop.get_type() == configprop.PASSWORD_TYPE:
				setattr(MyForm, n, StringField(self.__adapt_name(config, n), widget=PasswordInput(hide_value=False), default=config.get_default(n), description=config.get_comment(n), render_kw=render))

		form = MyForm(data = [(name, config.get(name)) for name in props if config.get_property(name).get_type() != configprop.BOOLEAN_TYPE])
		for i in [prop for prop in props if config.get_property(prop).get_type() == configprop.BOOLEAN_TYPE]:
			getattr(form, i).data = config.getint(i)
		
		for i in props:
			try:
				config.validate(i)
				getattr(form, i).errors = ()
			except Warning:
				getattr(form, i).errors = ()
				pass
			except Exception as e:
				getattr(form, i).errors = (e)
				getattr(form, i).render_kw[self.__HTML_CLASS] += self.__HTML_IS_INVALID
				getattr(form, i).render_kw[self.__HTML_INVALID] = self.__HTML_IS_INVALID
		return form
	
	#@app.route('/settings/<variable>', methods=['GET', 'POST'])
	@login_required
	def setting(self, variable=str()):
		props = self.config().get_section_properties(variable if variable else self.config().get_sections()[0])	

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
			return redirect(request.path)
				
		reset_needed = False		
		for i in props:
			if self.config().get_property(i).get_resetneeded():
				reset_needed = True
				break
		
		return render_template(self.__SETTINGS_HTML, form=self.__build_settings(self.config(), props), navlabels=self.config().get_sections(), reset_needed=reset_needed, version=constants.EPIFRAME_VERSION)
	
	#@app.route('/plugins', self.plugins, methods=['GET', 'POST'])
	@login_required
	def plugins(self):
		if len(self.__backend.get_plugins().get_plugins()) > 0:		
			curr_plugin = [x for x in self.__backend.get_plugins().get_plugins() if x.name == request.args.get('plugin')][0] if request.args.get('plugin') else self.__backend.get_plugins().get_plugins()[0]
			config = curr_plugin.config
			settings = request.args.get('variable') if request.args.get('variable') else config.get_sections()[0]
			props = config.get_section_properties(settings)

			if request.method == 'POST':
				for n in props:
					if config.get_property(n).get_type() != configprop.BOOLEAN_TYPE:
						if request.form.get(n) != None:
							config.set(n, str(request.form.get(n)))
					else:
						config.set(n, '1' if str(request.form.get(n)) == 'y' else '0')			
				s = re.search(r"\-\<\[.*?\]\>\-", str(request.form))
				if s:
					propname = s.group(0).replace('-<[','').replace(']>-','')
					config.set(propname, str(config.get_default(propname)))
				elif request.form.get(self.__BUT_SAVE) == self.__BUT_SAVE:
					try:
						config.verify_warnings()
					except Warning as e:
						flash(str(e))
						pass
					try:
						config.verify_exceptions()
						config.save()
					except Exception:
						session.pop('_flashes', None)
						pass		
				elif request.form.get(self.__BUT_DEFAULTS) == self.__BUT_DEFAULTS:
					for n in props:
						config.set(n, str(config.get_default(n)))
				elif request.form.get(self.__BUT_CANCEL) == self.__BUT_CANCEL:
					config.read_config()
				return redirect("{}?plugin={}&variable={}".format(request.base_url, curr_plugin.name, settings))

			reset_needed = False		
			for i in props:
				if config.get_property(i).get_resetneeded():
					reset_needed = True
					break
		
			template = render_template(self.__PLUGINS_HTML, info="", plugin_name=curr_plugin.name, sett_name=settings, plugins=[x.name for x in self.__backend.get_plugins().get_plugins()], form=self.__build_settings(config, props), navlabels=config.get_sections(), reset_needed=reset_needed, version=constants.EPIFRAME_VERSION)
		else:
			template = render_template(self.__PLUGINS_HTML, info='<ul><li>There are no <b>ePiframe</b> plugins installed! </li><li>Go to <a href="https://github.com/MikeGawi/ePiframe_plugin" target="_blank">ePiframe_plugin</a> site to find something for You!</li></ul>')
		return template