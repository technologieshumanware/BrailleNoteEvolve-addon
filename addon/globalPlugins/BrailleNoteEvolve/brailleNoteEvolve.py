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

addonHandler.initTranslation()

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

		postNvdaStartup.register(self._checkInitFailed)

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

	def terminate(self):
		"""
		Cleanup and restore original functions when the plugin is terminated.
		"""
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
