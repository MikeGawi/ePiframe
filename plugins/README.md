This is a place to install ePiframe plugins.

* Each plugin is a folder here, e.g. `git clone <plugin URL> <plugin_folder>` in this folder,
  then restart the ePiframe service.
* The folder name may contain letters, digits and `_` only (no dashes or dots).
* ePiframe 2.0 needs plugins written for the Plugin API v2. A 1.x plugin is skipped with an
  error in the log.
* The execution order is kept in *order.cfg* (created on the first run with new plugins,
  can be changed in the WebUI *Plugins - Execution Order* menu).
* Plugins can be kept in another folder set by the `EPIFRAME_PLUGINS_DIR` environment variable.
* A plugin that needs Python packages lists them in a *requirements.txt* file in its folder
  (pip format). Install them into the ePiframe environment with `sudo ./install.sh --plugins`
  (in the ePiframe folder) and restart the service; `./install.sh --update` installs them
  again. The packages must fit the versions ePiframe uses (*uv.lock*), otherwise nothing is
  installed and the error is shown. Never use `sudo pip3 install`: ePiframe doesn't see the
  system Python packages.

Go to https://github.com/MikeGawi/ePiframe_plugin to find something for You!
