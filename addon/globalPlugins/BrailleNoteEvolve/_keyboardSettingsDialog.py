# BrailleNoteEvolve add-on
# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# Copyright (C) 2026 Technologies Humanware

# Keyboard settings dialog module
import addonHandler
import api
import config
from config.configFlags import TypingEcho
import eventHandler
import gui
from gui.guiHelper import BoxSizerHelper
from gui import settingsDialogs
from logHandler import log
import queueHandler
import wx

addonHandler.initTranslation()

class KeyboardSettingsDialog(settingsDialogs.SettingsDialog):
	"""Dialog for configuring keyboard settings."""
	# Translators: Title of the Keyboard Settings dialog
	title = _("Keyboard Settings")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

	def makeSettings(self, settingsSizer):
		"""Create and add the keyboard settings controls."""
		sHelper = BoxSizerHelper(self, sizer=settingsSizer)

		# Speak typed characters
		speakTypedCharsChoices = [mode.displayString for mode in TypingEcho]
		self.speakTypedCharsList = sHelper.addLabeledControl(
			# Translators: Label for a dropdown to select whether NVDA should speak typed characters
			# The "&" indicates that the next character is a keyboard accelerator
			_("Speak typed &characters:"),
			wx.Choice,
			choices=speakTypedCharsChoices
		)

		# Speak typed words
		speakTypedWordsChoices = [mode.displayString for mode in TypingEcho]
		self.speakTypedWordsList = sHelper.addLabeledControl(
			# Translators: Label for a dropdown to select whether NVDA should speak typed words
			# The "&" indicates that the next character is a keyboard accelerator
			_("Speak typed &words:"),
			wx.Choice,
			choices=speakTypedWordsChoices
		)

		# Speak command keys
		self.speakCommandKeysCheckBox = sHelper.addItem(
			# Translators: Label for a checkbox to toggle whether NVDA should speak command keys
			# The "&" indicates that the next character is a keyboard accelerator
			wx.CheckBox(self, label=_("Speak c&ommand keys"))
		)

		# Initialize values
		self.initializeValues()

	def postInit(self):
		"""Set focus to the first control."""
		self.speakTypedCharsList.SetFocus()

	def initializeValues(self):
		"""Initialize the controls with current configuration values."""
		try:
			# Speak typed characters
			self.speakTypedCharsList.SetSelection(
				config.conf["keyboard"]["speakTypedCharacters"]
			)

			# Speak typed words
			self.speakTypedWordsList.SetSelection(
				config.conf["keyboard"]["speakTypedWords"]
			)

			# Speak command keys
			self.speakCommandKeysCheckBox.SetValue(
				config.conf["keyboard"]["speakCommandKeys"]
			)

		except Exception as e:
			log.error(f"Error initializing keyboard settings values: {e}", exc_info=True)

	def onOk(self, evt):
		"""Save all keyboard settings when dialog is confirmed."""	
		try:
			# Save speak typed characters
			config.conf["keyboard"]["speakTypedCharacters"] = (
				self.speakTypedCharsList.GetSelection()
			)

			# Save speak typed words
			config.conf["keyboard"]["speakTypedWords"] = (
				self.speakTypedWordsList.GetSelection()
			)

			# Save speak command keys
			config.conf["keyboard"]["speakCommandKeys"] = (
				self.speakCommandKeysCheckBox.IsChecked()
			)

			config.conf.save()

		except Exception as e:
			log.error(f"Error saving keyboard settings: {e}", exc_info=True)

		super().onOk(evt)


def openKeyboardSettings():
	"""Open the keyboard settings dialog."""
	log.info("Request to open keyboard settings dialog received")
	wx.CallAfter(_openKeyboardSettingsMainThread)


_keyboardSettingsDialog = None

def _onKeyboardSettingsDialogDestroy(evt):
	"""Handle dialog destroy event - clear the dialog reference."""
	global _keyboardSettingsDialog
	_keyboardSettingsDialog = None
	evt.Skip()
	# Explicitly restore NVDA focus tracking after dialog closes
	# This is needed because the dialog was opened from a background thread
	try:
		focus = api.getDesktopObject().objectWithFocus()
		if focus:
			queueHandler.queueFunction(queueHandler.eventQueue, eventHandler.queueEvent, "gainFocus", focus)
	except Exception as e:
		log.error(f"Error restoring focus after dialog close: {e}", exc_info=True)


def _openKeyboardSettingsMainThread():
	"""This method runs in the main thread to safely open the Keyboard Settings dialog"""
	global _keyboardSettingsDialog
	
	# Check if dialog already exists BEFORE prePopup
	if _keyboardSettingsDialog is not None:
		_keyboardSettingsDialog.Raise()
		_keyboardSettingsDialog.SetFocus()
		return
	
	gui.mainFrame.prePopup()
	try:
		_keyboardSettingsDialog = KeyboardSettingsDialog(gui.mainFrame)
		_keyboardSettingsDialog.Bind(wx.EVT_WINDOW_DESTROY, _onKeyboardSettingsDialogDestroy)
		_keyboardSettingsDialog.Show()
	except settingsDialogs.SettingsDialog.MultiInstanceErrorWithDialog:
		_keyboardSettingsDialog.Raise()
		_keyboardSettingsDialog.SetFocus()
	except Exception as e:
		log.error(f"Error creating keyboard settings dialog: {e}", exc_info=True)
	finally:
		gui.mainFrame.postPopup()
