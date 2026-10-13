# BrailleNoteEvolve add-on
# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# Copyright (C) 2026 Technologies Humanware

# Keysoft Options Menu management via named pipe
# Note: This is instantiated from the main BrailleNoteEvolve GlobalPlugin
from logHandler import log
from ._namedPipeBase import NamedPipeGlobalPlugin
from typing import Callable
import addonHandler
from . import _brailleSettingsDialog
from . import _keyboardSettingsDialog
from . import _languageProfileDialog

addonHandler.initTranslation()

class KeysoftOptionsMenuHandler(NamedPipeGlobalPlugin):
	"""Handler for managing Keysoft options menu via a named pipe."""

	def getIncomingPipeName(self) -> str:
		"""Return the name of the named pipe (same for incoming and outgoing)."""
		return "\\\\.\\pipe\\NVDANamedPipe"

	def getOutgoingPipeName(self) -> str:
		"""Return the name of the named pipe (same for incoming and outgoing)."""
		return "\\\\.\\pipe\\ControlCenterNamedPipe"

	def __init__(self, *args, **kwargs):
		# Define supported commands
		self.CONFIGURE_LANGUAGE_PROFILE = "OpenConfigureLanguageProfile"
		self.MANAGE_LANGUAGE_PROFILES = "OpenManageLanguageProfiles"
		self.SELECT_LANGUAGE_PROFILE = "OpenSelectLanguageProfile"
		self.OPEN_BRAILLE_SETTINGS = "OpenBrailleSettings"
		self.OPEN_KEYBOARD_SETTINGS = "OpenKeyboardSettings"
		
		super().__init__(*args, **kwargs)

	def processMessage(self, message, hPipe):
		"""Process a message received from the named pipe."""
		try:
			log.info(f"[KeysoftOptionsMenu] Received command: {message}")
			
			# Parse the message and determine which action to take
			if message == self.CONFIGURE_LANGUAGE_PROFILE:
				response = "success:LanguageProfile"
				self._write_to_pipe(hPipe, response)
				log.info(f"[KeysoftOptionsMenu] Sent response: {response}")
				self._handleOpenLanguageProfile()
			elif message == self.MANAGE_LANGUAGE_PROFILES:
				response = "success:ManageLanguageProfiles"
				self._write_to_pipe(hPipe, response)
				log.info(f"[KeysoftOptionsMenu] Sent response: {response}")
				self._handleManageLanguageProfiles()
			elif message == self.SELECT_LANGUAGE_PROFILE:
				response = "success:SelectLanguageProfile"
				self._write_to_pipe(hPipe, response)
				log.info(f"[KeysoftOptionsMenu] Sent response: {response}")
				self._handleSelectLanguageProfile()
			elif message == self.OPEN_BRAILLE_SETTINGS:
				response = "success:BrailleSettings"
				self._write_to_pipe(hPipe, response)
				log.info(f"[KeysoftOptionsMenu] Sent response: {response}")
				self._handleOpenBrailleSettings()
			elif message == self.OPEN_KEYBOARD_SETTINGS:
				response = "success:KeyboardSettings"
				self._write_to_pipe(hPipe, response)
				log.info(f"[KeysoftOptionsMenu] Sent response: {response}")
				self._handleOpenKeyboardSettings()
			else:
				log.warning(f"[KeysoftOptionsMenu] Unknown command: {message}")
				response = f"error:UnknownCommand:{message}"
				self._write_to_pipe(hPipe, response)
				log.info(f"[KeysoftOptionsMenu] Sent response: {response}")

		except Exception as e:
			log.error(f"[KeysoftOptionsMenu] Error processing message: {e}", exc_info=True)
			error_response = f"error:Exception:{str(e)}"
			self._write_to_pipe(hPipe, error_response)
			log.info(f"[KeysoftOptionsMenu] Sent error response: {error_response}")

	def _handleOpenBrailleSettings(self):
		"""Handle opening the braille settings dialog."""
		try:
			_brailleSettingsDialog.openBrailleSettings()
		except Exception as e:
			log.error(f"Error opening braille settings: {e}", exc_info=True)

	def _handleOpenKeyboardSettings(self):
		"""Handle opening the keyboard settings dialog."""
		try:
			_keyboardSettingsDialog.openKeyboardSettings()
		except Exception as e:
			log.error(f"Error opening keyboard settings: {e}", exc_info=True)

	def _handleOpenLanguageProfile(self):
		"""Handle opening the language profile configuration dialog."""
		try:
			_languageProfileDialog.openConfigureLanguageProfile()
		except Exception as e:
			log.error(f"Error opening language profile: {e}", exc_info=True)

	def _handleManageLanguageProfiles(self):
		"""Handle opening the manage language profiles dialog."""
		try:
			_languageProfileDialog.openManageLanguageProfiles()
		except Exception as e:
			log.error(f"Error opening manage language profiles: {e}", exc_info=True)

	def _handleSelectLanguageProfile(self):
		"""Handle opening the select language profile dialog."""
		try:
			_languageProfileDialog.openSelectLanguageProfile()
		except Exception as e:
			log.error(f"Error opening select language profile: {e}", exc_info=True)
