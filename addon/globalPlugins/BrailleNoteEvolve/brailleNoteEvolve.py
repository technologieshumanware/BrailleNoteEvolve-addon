# BrailleNoteEvolve add-on
# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# Copyright (C) 2026 Technologies Humanware

"""
Global plugin to override secure desktop change handling.
This plugin prevents the "Secure Desktop" message from being announced
when switching to/from secure desktop (UAC, login screen, etc.).
It also manages:
- Keysoft Options Menu via named pipes
- Braille IME pipe server
"""

from logHandler import log
import addonHandler
from core import postNvdaStartup
from gui.message import MessageDialog, DialogType
import globalPluginHandler
import config

addonHandler.initTranslation()

# Configuration specification for BrailleNote Evolve addon
confspec = {
	"startupProfile": 'string(default="")',
}

# Initialize addon configuration
config.conf.spec["braillenoteevolve"] = confspec

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""
	Global plugin that manages BrailleNote Evolve functionality:
	- Overrides secure desktop change handler
	- Manages Keysoft Options Menu named pipes
	- Manages Braille IME pipe server
	"""
	initSuccess = True

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# True once _restoreStartupProfile has run via postNvdaStartup.
		# Prevents _saveStartupProfile from clobbering the saved profile
		# when NVDA is launched in a silent/headless mode (e.g. --install-addon-silent
		# during a Control Center update), which exits before postNvdaStartup fires.
		self._startupCompleted = False

		postNvdaStartup.register(self._checkInitFailed)
		postNvdaStartup.register(self._restoreStartupProfile)
	
		# Initialize Keysoft Options Menu handler
		try:
			from .keysoftOptionsMenuNamedPipe import KeysoftOptionsMenuHandler
			self.keysoftMenuHandler = KeysoftOptionsMenuHandler()
			log.info("brailleNoteEvolve: Keysoft Options Menu handler started")
		except Exception as e:
			log.error(f"brailleNoteEvolve: Failed to start Keysoft Options Menu handler: {e}", exc_info=True)
			self.keysoftMenuHandler = None
			self.initSuccess = False

		# Initialize Braille IME Pipe Server
		try:
			from .brailleImeNamedPipe import BrailleImePipeServer
			self.brailleImePipeServer = BrailleImePipeServer()
			self.brailleImePipeServer.start_server()
			log.info("brailleNoteEvolve: Braille IME Pipe Server started")
		except Exception as e:
			log.error(f"brailleNoteEvolve: Failed to start Braille IME Pipe Server: {e}", exc_info=True)
			self.brailleImePipeServer = None
			self.initSuccess = False

		# Monkey-patch the _handleSecureDesktopChange function
		try:
			from winAPI import secureDesktop

			# Store the original function in case we need it later
			self._original_handleSecureDesktopChange = secureDesktop._handleSecureDesktopChange

			# Replace with our custom implementation
			secureDesktop._handleSecureDesktopChange = self._customHandleSecureDesktopChange

			log.info("brailleNoteEvolve: Successfully overridden _handleSecureDesktopChange")
		except Exception as e:
			log.error(f"brailleNoteEvolve: Failed to override _handleSecureDesktopChange: {e}", exc_info=True)
			self.initSuccess = False

	def _checkInitFailed(self):
		if not self.initSuccess:
			dialog = MessageDialog(
				parent=None,
				# Translators: label to inform user that BrailleNoteEvolve addon could not be loaded correctly
				message=_("BrailleNote evolve Add-on could not be loaded correctly."),
				# Translators: dialog title when announcing an error for BrailleNoteEvolve addon
				title=_("BrailleNote evolve Error"),
				dialogType=DialogType.ERROR
			)
			dialog.Show()

	def _restoreStartupProfile(self):
		"""Restore the saved startup profile if one was configured."""
		try:
			# Get the Startup Profile from the base profile config
			baseProfile = config.conf.profiles[0]			
			
			if "braillenoteevolve" not in baseProfile:
				baseProfile["braillenoteevolve"] = {}
				
			startupProfile = baseProfile["braillenoteevolve"]["startupProfile"]
			if startupProfile: 
				log.debug(f"brailleNoteEvolve: Restoring startup profile: {startupProfile}")
			
				if startupProfile in config.conf.listProfiles():
					config.conf.manualActivateProfile(startupProfile)
					log.info(f"brailleNoteEvolve: Successfully activated startup profile: {startupProfile}")
				else:
					log.warning(f"brailleNoteEvolve: Startup profile '{startupProfile}' not found, resetting to empty")
					baseProfile["braillenoteevolve"]["startupProfile"] = ""
					config.conf.save()
		except Exception as e:
			log.error(f"brailleNoteEvolve: Error restoring startup profile: {e}", exc_info=True)
		finally:
			# Signal terminate() that it is safe to persist the active profile.
			self._startupCompleted = True
			# Save the active profile immediately on every switch. Writing on
			# switch (rather than only in terminate) ensures the value is saved
			# before a window session ends (sign out, restart or shut down).
			try:
				config.post_configProfileSwitch.register(self._onProfileSwitch)
			except Exception as e:
				log.error(f"brailleNoteEvolve: Failed to register profile switch handler: {e}", exc_info=True)

	def _onProfileSwitch(self, **kwargs):
		"""Save the currently active profile whenever the user switches profiles."""
		self._saveStartupProfile()

	def _customHandleSecureDesktopChange(self):
		"""
		Custom implementation of _handleSecureDesktopChange that does everything
		except announce the "Secure Desktop" message.
		"""
		import api
		import keyboardHandler
		from NVDAObjects import NVDAObject
		from speech.speech import cancelSpeech

		# We don't receive key up events for any keys down before switching to a secure desktop,
		# so clear our recorded modifiers.
		keyboardHandler.currentModifiers.clear()

		# Before entering sleep mode,
		# cancel speech so that speech does not overlap with the new instance of NVDA
		# started on the secure desktop.
		cancelSpeech()

		# NOTE: The ui.message call is intentionally omitted here
		# This is the main purpose of this override - to prevent the "Secure Desktop" announcement

		class _SecureDesktopNVDAObject(NVDAObject):
			"""
			An NVDAObject must be focused to enable sleep mode while the secure desktop is active.
			For security purposes, it is ideal we use a fake NVDAObject, that is not tied to any real window.
			"""

			# Must be implemented to instantiate.
			processID = None

			# NVDA should sleep while the secure desktop is active.
			# If the desktop changes again, a new object will be focused,
			# ending sleep mode.
			sleepMode = NVDAObject.SLEEP_FULL

		secureDesktopObject = _SecureDesktopNVDAObject()
		api.setFocusObject(secureDesktopObject)

		# Still notify extension points about the secure desktop change
		from winAPI.secureDesktop import post_secureDesktopStateChange
		post_secureDesktopStateChange.notify(isSecureDesktop=True)

	def _saveStartupProfile(self):
		"""
		Save the currently active profile to the base profile config so it can be restored on next startup.
		"""
		# Skip when NVDA never reached postNvdaStartup (silent/headless runs
		# such as --install-addon-silent). No profile has been restored, so
		# saving now would overwrite the real value with an empty string.
		if not getattr(self, "_startupCompleted", False):
			log.info("brailleNoteEvolve: Skipping save of startup profile (silent/headless NVDA run).")
			return
		try:
			profileName = None
			if len(config.conf.profiles) > 1:
				lastProfile = config.conf.profiles[-1]
				if hasattr(lastProfile, 'manual') and lastProfile.manual:
					profileName = lastProfile.name
			
			baseProfile = config.conf.profiles[0]
			if "braillenoteevolve" not in baseProfile:
				baseProfile["braillenoteevolve"] = {}
			
			baseProfile["braillenoteevolve"]["startupProfile"] = profileName if profileName else ""
			config.conf.save()
			
			displayName = profileName if profileName else "(normal configuration)"
			log.info(f"brailleNoteEvolve: Saved startup profile: {displayName}")
		except Exception as e:
			log.error(f"brailleNoteEvolve: Error saving startup profile: {e}", exc_info=True)

	def terminate(self):
		"""
		Cleanup and restore original functions when the plugin is terminated.
		"""
		# Save the current profile before NVDA closes
		self._saveStartupProfile()
		
		# Unregister profile switch handler
		try:
			config.post_configProfileSwitch.unregister(self._onProfileSwitch)
			log.debug("brailleNoteEvolve: Unregistered profile switch handler")
		except Exception as e:
			log.error(f"brailleNoteEvolve: Failed to unregister profile switch handler: {e}", exc_info=True)
		
		# Stop Braille IME Pipe Server
		try:
			if hasattr(self, 'brailleImePipeServer') and self.brailleImePipeServer:
				self.brailleImePipeServer.stop_server()
				log.info("brailleNoteEvolve: Braille IME Pipe Server stopped")
		except Exception as e:
			log.error(f"brailleNoteEvolve: Failed to stop Braille IME Pipe Server: {e}", exc_info=True)

		# Stop Keysoft Options Menu handler
		try:
			if hasattr(self, 'keysoftMenuHandler') and self.keysoftMenuHandler:
				self.keysoftMenuHandler.terminate()
				log.info("brailleNoteEvolve: Keysoft Options Menu handler stopped")
		except Exception as e:
			log.error(f"brailleNoteEvolve: Failed to stop Keysoft Options Menu handler: {e}", exc_info=True)

		# Restore the original secure desktop handler
		try:
			from winAPI import secureDesktop
			if hasattr(self, '_original_handleSecureDesktopChange'):
				secureDesktop._handleSecureDesktopChange = self._original_handleSecureDesktopChange
				log.info("brailleNoteEvolve: Restored original _handleSecureDesktopChange")
		except Exception as e:
			log.error(f"brailleNoteEvolve: Failed to restore original _handleSecureDesktopChange: {e}", exc_info=True)
		finally:
			super().terminate()
