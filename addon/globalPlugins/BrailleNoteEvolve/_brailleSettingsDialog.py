# BrailleNoteEvolve add-on
# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# Copyright (C) 2026 Technologies Humanware

# Braille settings dialog module
from typing import Callable
import addonHandler
import api
import braille
import config
from config.configFlags import ShowMessages
import gui
from gui.guiHelper import BoxSizerHelper
from gui import settingsDialogs, nvdaControls
from logHandler import log
import wx

addonHandler.initTranslation()

class BrailleSettingsDialog(settingsDialogs.SettingsDialog):
	"""Dialog for configuring braille settings."""
	# Translators: Title of the Braille Settings dialog
	title = _("Braille Settings")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

	def makeSettings(self, settingsSizer):
		"""Create and add the braille settings controls."""
		sHelper = BoxSizerHelper(self, sizer=settingsSizer)

		# Show messages (using NVDA's ShowMessages enum)
		showMessagesChoices = [mode.displayString for mode in ShowMessages]
		self.showMessagesChoice = sHelper.addLabeledControl(
			# Translators: Label for a dropdown to select when NVDA should show messages on the braille display
			_("Show messages"), wx.Choice,
			choices=showMessagesChoices
		)
		self.showMessagesChoice.Bind(wx.EVT_CHOICE, self.onShowMessagesChange)
		# Set initial value before checking if we should disable messageTimeout
		showMessagesValue = config.conf["braille"].get("showMessages", ShowMessages.USE_TIMEOUT.value)
		try:
			showMessagesEnum = ShowMessages(showMessagesValue)
			self.showMessagesChoice.SetSelection(showMessagesEnum.value)
		except ValueError:
			# Default to USE_TIMEOUT if invalid value
			self.showMessagesChoice.SetSelection(ShowMessages.USE_TIMEOUT.value)

		# Message timeout (sec)
		minTimeout = int(
			config.conf.getConfigValidation(
				("braille", "messageTimeout"),
			).kwargs["min"],
		)
		maxTimeOut = int(
			config.conf.getConfigValidation(
				("braille", "messageTimeout"),
			).kwargs["max"],
		)
		# Translators: Label for a spin control to set how many seconds messages should be shown on the braille display before disappearing
		# The "&" indicates that the next character is a keyboard accelerator
		messageTimeoutText = _("Message &timeout (sec)")
		self.messageTimeoutEdit = sHelper.addLabeledControl(
			messageTimeoutText,
			nvdaControls.SelectOnFocusSpinCtrl,
			min=minTimeout,
			max=maxTimeOut,
			initial=config.conf["braille"].get("messageTimeout", 4)
		)
		if self.showMessagesChoice.GetSelection() != ShowMessages.USE_TIMEOUT.value:
			self.messageTimeoutEdit.Disable()

		# Show cursor
		# Translators: Label for a checkbox to toggle whether the braille display cursor is shown
		# The "&" indicates that the next character is a keyboard accelerator
		showCursorLabelText = _("&Show cursor")
		self.showCursorCheckBox = sHelper.addItem(
			wx.CheckBox(self, label=showCursorLabelText),
		)
		self.showCursorCheckBox.SetValue(config.conf["braille"]["showCursor"])

		# Show selection
		self.brailleShowSelectionCombo: nvdaControls.FeatureFlagCombo = (
			sHelper.addLabeledControl(
				# Translators: Label for a dropdown to select whether the braille display should show selection
				# The "&" indicates that the next character is a keyboard accelerator
				labelText=_("Show se&lection"),
				wxCtrlClass=nvdaControls.FeatureFlagCombo,
				keyPath=["braille", "showSelection"],
				conf=config.conf,
			)
		)

	def postInit(self):
		"""Set focus to the first control."""
		self.showMessagesChoice.SetFocus()

	def onOk(self, evt):
		"""Save all braille settings when dialog is confirmed."""
		try:
			# Save show messages setting using NVDA's ShowMessages enum
			showMessagesSelection = self.showMessagesChoice.GetSelection()
			
			# Convert selection index to ShowMessages enum value
			config.conf["braille"]["showMessages"] = showMessagesSelection

			# Save message timeout
			config.conf["braille"]["messageTimeout"] = self.messageTimeoutEdit.GetValue()

			# Save show cursor
			config.conf["braille"]["showCursor"] = self.showCursorCheckBox.GetValue()

			# Save show selection
			self.brailleShowSelectionCombo.saveCurrentValueToConf()

			config.conf.save()

		except Exception as e:
			log.error(f"Error saving braille settings: {e}", exc_info=True)

		super().onOk(evt)

	def onShowMessagesChange(self, evt):
		"""Enable or disable message timeout based on show messages selection."""
		self.messageTimeoutEdit.Enable(evt.GetSelection() == ShowMessages.USE_TIMEOUT.value)


def openBrailleSettings():
	"""Open the braille settings dialog."""
	wx.CallAfter(_openBrailleSettingsMainThread)


_brailleSettingsDialog = None


def _onBrailleSettingsDialogDestroy(evt):
	global _brailleSettingsDialog
	_brailleSettingsDialog = None
	evt.Skip()
	# Update braille display to show the currently focused object
	# after the dialog closes, preventing it from staying stuck on the dialog button
	wx.CallAfter(braille.handler.handleGainFocus, api.getFocusObject())


def _openBrailleSettingsMainThread():
	"""This method runs in the main thread to safely open the Braille Settings dialog"""
	global _brailleSettingsDialog
	
	try:
		# Check if dialog already exists
		if _brailleSettingsDialog is not None:
			_brailleSettingsDialog.Raise()
			_brailleSettingsDialog.SetFocus()
			return

		gui.mainFrame.prePopup()
		_brailleSettingsDialog = BrailleSettingsDialog(gui.mainFrame)
		_brailleSettingsDialog.Bind(wx.EVT_WINDOW_DESTROY, _onBrailleSettingsDialogDestroy)
		_brailleSettingsDialog.Show()
	except settingsDialogs.SettingsDialog.MultiInstanceErrorWithDialog:
		_brailleSettingsDialog.Raise()
		_brailleSettingsDialog.SetFocus()
	except Exception as e:
		log.error(f"Error creating braille settings dialog: {e}", exc_info=True)
	finally:
		gui.mainFrame.postPopup()
