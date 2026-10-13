# BrailleNoteEvolve add-on
# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# Copyright (C) 2026 Technologies Humanware

# Language profile dialogs module
from typing import Callable
from collections import OrderedDict
import brailleTables
import config
import eventHandler
import gui
from gui.guiHelper import BoxSizerHelper
from gui.configProfiles import NewProfileDialog, ProfilesDialog
from nvwave import playErrorSound
import queueHandler
import synthDriverHandler
import wx
from gui import settingsDialogs, nvdaControls
from logHandler import log
import ui
import winreg
import addonHandler
import api
import braille

addonHandler.initTranslation()

# Constants for braille types (must match HumanwareBrailleTranslation addon)
BRAILLE_TYPE_LITERARY = "Literary braille"
BRAILLE_TYPE_COMPUTER = "Computer braille"

# Constants for math codes (must match HWMath addon)
MATH_CODE_NEMETH = "Nemeth"
MATH_CODE_UEB = "UEB"
MATH_CODE_FR = "FR"

# Mapping dictionaries
BRAILLE_TYPE_MAP = {
	# Translators: Grade type choice for Computer Braille
    _("Computer Braille"): BRAILLE_TYPE_COMPUTER,
	# Translators: Grade type choice for Literary Braille
    _("Literary Braille"): BRAILLE_TYPE_LITERARY	
}

MATH_CODE_MAP = {
	# Translators: Math code choice for Nemeth Braille			
    _("Nemeth"): MATH_CODE_NEMETH,
	# Translators: Math code choice for Unified English Braille (UEB)
    _("UEB"): MATH_CODE_UEB,
	# Translators: Math code choice for French Braille
    _("FR"): MATH_CODE_FR
}

def getLocalizedBrailleType(constant):
    """Get localized label for braille type constant."""
    for label, const in BRAILLE_TYPE_MAP.items():
        if const == constant:
            return label
    return next(iter(BRAILLE_TYPE_MAP.keys()))

def getLocalizedMathCode(constant):
    """Get localized label for math code constant."""
    for label, const in MATH_CODE_MAP.items():
        if const == constant:
            return label
    return next(iter(MATH_CODE_MAP.keys()))

class ConfigureLanguageProfileDialog(settingsDialogs.SettingsDialog):
	"""Dialog for configuring a language profile."""
	# Translators: Title of the Configure Language Profile dialog
	title = _("Configure Language Profile")

	def __init__(self, *args, **kwargs):
		log.debug("Initializing configure language profile dialog")

		self.computerBrailleTranslatorChoices = []
		self.computerBrailleTranslatorFiles = []
  
		current_profile_name = None
		try:
			if config.conf.profiles and len(config.conf.profiles) > 0:
				current_profile_name = config.conf.profiles[-1].name
		except Exception as e:
			log.error(f"Error getting current profile name : {e}")

		# Translators: The default profile name for a language profile when no profile is currently active
		display_name = current_profile_name if current_profile_name else _("(normal configuration)")
		# Translators: Title of the Configure Language Profile dialog when a profile name can be displayed
		self.title = _("Configure Language Profile - {}").format(display_name)

		self.hwMathModule = self.getAddonModule("HWMath")
		self.hwBrailleModule = self.getAddonModule("HumanwareBrailleTranslation")

		# Initialize empty collections to avoid AttributeError
		self.driverList = []
		self.synthNames = []
		self.initialSettings = {}

		# Now call super().__init__ which will call makeSettings()
		super().__init__(*args, **kwargs)

		# Continue with the rest of the initialization
		try:
			self.driverList = synthDriverHandler.getSynthList()
			self.synthNames = [x[0] for x in self.driverList]
			log.debug(f"Loaded {len(self.driverList)} synthesizers")

			if self.driverList:
				self._storeInitialSettings()
		except Exception as e:
			log.error(f"Error initializing synthesizer list: {e}", exc_info=True)
			self.driverList = []
			self.synthNames = []

	def getAddonModule(self, addonName:str, moduleName: str = "globalPlugins"):
		"""Get a module from a running addon.
		
		This method tries to import the module directly from the running addon.
		@param addonName: The name of the addon
		@param moduleName: The module name within the addon (e.g., 'globalPlugins')
		@return: The module object or None if not found
		"""
		log.info(f"Attempt to retrieve {addonName} addon module")
		try:
			# Try to import the module directly from the running addon
			import sys
			module_path = f"{moduleName}.{addonName}"
			# Check if the module is loaded in sys.modules (case-insensitive)
			module_path_lower = module_path.lower()
			for key in sys.modules.keys():
				if key.lower() == module_path_lower:
					module = sys.modules[key]
					log.info(f"Addon module {addonName} found in sys.modules as '{key}' (addon is loaded and enabled)")
					return module
			
			log.info(f"{addonName} addon module not found in sys.modules (addon not loaded or disabled)")
			return None
		except Exception as e:
			log.error(f"Error attempting to get {addonName} addon module: {e}")
			return None

	def makeSettings(self, settingsSizer):
		"""Create and add the settings controls."""
		log.debug("Creating Configure Language profile controls")
		sHelper = BoxSizerHelper(self, sizer=settingsSizer)

		# Synthesizer selection
		synthListID = wx.NewId()
		self.synthList = sHelper.addLabeledControl(
			# Translators: Label for a dropdown to select the speech synthesizer to use for the current language profile
			_("Synthesizer:"), wx.Choice, id=synthListID, choices=[]
		)
		self.synthList.Bind(wx.EVT_CHOICE, self.onSynthesizerChange)

		# Voice selection
		self.voiceList = sHelper.addLabeledControl(
			# Translators: Label for a dropdown to select the voice to use for the current language profile
			_("Voice:"), wx.Choice, choices=[]
		)
		self.voiceList.Bind(wx.EVT_CHOICE, self.onVoiceChange)

		self.variantList = sHelper.addLabeledControl(
			# Translators: Label for a dropdown to select the voice variant to use for the current language profile
			_("Variant:"), wx.Choice, choices=[]
		)
		self.variantList.Bind(wx.EVT_CHOICE, self.onVariantChange)

		# Rate control
		self.rateSpeed = sHelper.addLabeledControl(
			# Translators: Label for a slider to adjust the speech rate for the current language profile
			_("Rate:"), nvdaControls.EnhancedInputSlider,
			minValue=0, maxValue=100,
			style=wx.SL_HORIZONTAL
		)
		self.rateSpeed.Bind(wx.EVT_SLIDER, self.onRateSpeedChange)

		# Pitch control
		self.voicePitch = sHelper.addLabeledControl(
			# Translators: Label for a slider to adjust the voice pitch for the current language profile
			_("Pitch:"), nvdaControls.EnhancedInputSlider,
			minValue=0, maxValue=100,
			style=wx.SL_HORIZONTAL
		)
		self.voicePitch.Bind(wx.EVT_SLIDER, self.onVoicePitchChange)

		# Braille section - only if HumanwareBrailleTranslation is available
		if self.hwBrailleModule is not None:

			# TODO We don't want to save localized settings in the config file!
			# Braille grade for entry
			self.gradeTypes = list(BRAILLE_TYPE_MAP.keys())
			self.gradeEntryChoice = sHelper.addLabeledControl(
				# Translators: Label for a dropdown to select the preferred braille grade for entry in the current language profile
				_("Preferred Braille Grade for Entry:"), wx.Choice,
				choices=self.gradeTypes
			)

			# Braille grade for display
			self.gradeDisplayChoice = sHelper.addLabeledControl(
				# Translators: Label for a dropdown to select the preferred braille grade for display in the current language profile
				_("Preferred Braille Grade for Display:"), wx.Choice,
				choices=self.gradeTypes
			)

			# Computer translator
			self.computerTranslatorChoices = self.getComputerBrailleTranslatorsChoices()
			self.computerBrailleTranslatorChoice =sHelper.addLabeledControl(
				# Translators: Label for a dropdown to select the computer braille translator to use for the current language profile
				_("Computer Braille Translator:"), wx.Choice,
				choices=self.computerTranslatorChoices
			)

			# Literary translator
			translationProvider = getattr(self.hwBrailleModule, "translationProvider", None)
			if translationProvider is not None:
				try:
					literaryTranslatorChoices = translationProvider.getTranslators()
				except Exception as e:
					log.warning(f"Error getting translators: {e}")
					literaryTranslatorChoices = []
			else:
				log.warning("translationProvider not available in hwBrailleModule")
				literaryTranslatorChoices = []
			self.literaryBrailleTranslatorChoice = sHelper.addLabeledControl(
				# Translators: Label for a dropdown to select the literary braille translator to use for the current language profile
				_("Literary Braille Translator:"), wx.Choice,
				choices=literaryTranslatorChoices
			)

		else:
			log.debug("HumanwareBrailleTranslation addon not available, skipping braille settings")

		# Math code - always in its own group when available
		if self.hwMathModule is not None:

			mathCodeChoices = list(MATH_CODE_MAP.keys())
			self.mathCodeChoice = sHelper.addLabeledControl(
				# Translators: Label for a dropdown to select the preferred braille code for math for the current language profile
				_("Preferred Braille Type for Math:"), wx.Choice,
				choices=mathCodeChoices
			)

			# Initialize math code selection
			try:
				mathCode = config.conf["HWMath"]["mathCodeChoice"]
				localizedMathCode = getLocalizedMathCode(mathCode)
				try:
					index = mathCodeChoices.index(localizedMathCode)
					self.mathCodeChoice.SetSelection(index)
					log.debug(f"Set math code to {mathCode}")
				except ValueError:
					log.warning(f"Math code {mathCode} not in available choices")
					self.mathCodeChoice.SetSelection(0)  # Default to first option
			except KeyError:
				log.warning("HWMath configuration not found")
				self.mathCodeChoice.SetSelection(0)  # Default to first option
		else:
			log.debug("HWMath addon not available, skipping Math Code setting")
			self.mathCodeChoice = None

		# Initialize UI with current values
		self.updateSynthesizerList()
		self.updateVoiceList()
		self.updateVariantList()

		wx.CallAfter(self.synthList.SetFocus)

		# Set rate and pitch values
		try:
			driver = self.getDriver()
			self.rateSpeed.SetValue(driver.rate)
			self.voicePitch.SetValue(driver.pitch)
		except Exception as e:
			log.error(f"Error setting rate/pitch values: {e}", exc_info=True)

		# Initialize braille settings
		try:
			if self.hwBrailleModule is not None:
				# Entry grade
				try:
					entryGrade = config.conf["HumanwareBrailleTranslation"]["TranslatorTypeForEntry"]
					localizedEntryGrade = getLocalizedBrailleType(entryGrade)
					log.debug(f"Entry grade: {entryGrade}")
					try:
						self.gradeEntryChoice.SetSelection(self.gradeTypes.index(localizedEntryGrade))
					except ValueError:
						log.warning(f"Entry grade {entryGrade} not in available choices")
				except (KeyError, AttributeError) as e:
					log.warning(f"Could not set entry grade: {e}")

				# Display grade
				try:
					displayGrade = config.conf["HumanwareBrailleTranslation"]["TranslatorTypeForDisplay"]
					localizedDisplayGrade = getLocalizedBrailleType(displayGrade)
					log.debug(f"Display grade: {displayGrade}")
					try:
						self.gradeDisplayChoice.SetSelection(self.gradeTypes.index(localizedDisplayGrade))
					except ValueError:
						log.warning(f"Display grade {displayGrade} not in available choices")
				except (KeyError, AttributeError) as e:
					log.warning(f"Could not set display grade: {e}")

				# Computer translator
				try:
					computerTranslator = config.conf["HumanwareBrailleTranslation"]["G0TranslatorChoice"]
					self.computerBrailleTranslatorFiles = self.getComputerBrailleTranslatorsFiles()
     
					try:
						index = self.computerBrailleTranslatorFiles.index(computerTranslator)
						self.computerBrailleTranslatorChoice.SetSelection(index)
					except ValueError:
						log.warning(f"Computer translator {computerTranslator} not in available choices")
				except (KeyError, AttributeError) as e:
					log.warning(f"Could not set computer translator: {e}")

				# Literary translator
				try:
					literaryTranslator = config.conf["HumanwareBrailleTranslation"]["translatorChoice"]
					translationProvider = getattr(self.hwBrailleModule, "translationProvider", None)
					if translationProvider is not None:
						try:
							literaryTranslatorChoices = translationProvider.getTranslators()
							index = literaryTranslatorChoices.index(literaryTranslator)
							self.literaryBrailleTranslatorChoice.SetSelection(index)
						except ValueError:
							log.warning(f"Literary translator {literaryTranslator} not in available choices")
						except Exception as e:
							log.warning(f"Error getting literary translators: {e}")
					else:
						log.warning("translationProvider not available")
				except (KeyError, AttributeError, ImportError) as e:
					log.warning(f"Could not set literary translator: {e}")
			else:
				log.debug("Skipping braille settings initialization - addon not available")
		except Exception as e:
			log.error(f"Error initializing braille settings: {e}", exc_info=True)

	def onVoiceChange(self, evt):
		selection = evt.GetSelection()
		if selection != -1 and self.voices:
			voice = self.voices[selection].id
			log.debug(f"Voice change to {voice}")
			driver = self.getDriver()
			driver.voice = voice

		try:
			rateValue = self.rateSpeed.GetValue()
			if rateValue != driver.rate:
				driver.rate = rateValue
		except Exception as e:
			log.error(f"Error setting rate value : {e}")

	def onVariantChange(self, evt):
		selection = evt.GetSelection()
		if selection != -1 and hasattr(self, 'variantNames') and self.variantNames:
			variantName = self.variantNames[selection]
			log.debug(f"Variant change to {variantName}")
			driver = self.getDriver()
			driver.variant = variantName

	def onRateSpeedChange(self, evt):
		value = evt.GetInt()
		log.debug(f"Rate speed change to {value}")
		driver = self.getDriver()
		driver.rate = value

	def onVoicePitchChange(self, evt):
		value = evt.GetInt()
		log.debug(f"Voice pitch change to {value}")
		driver = self.getDriver()
		driver.pitch = value

	def _storeInitialSettings(self):
		"""Store all initial settings values for restoration on cancel."""
		log.debug("Storing initial settings values")
		try:
			driver = self.getDriver()

			self.initialSettings = {
				"synthName": driver.name,
				"voice": driver.voice,
				"rate": driver.rate,
				"pitch": driver.pitch,
			}

			try:
				self.initialSettings["variant"] = getattr(driver, "variant", "")
			except(AttributeError, NotImplementedError):
				self.initialSettings["variant"] = ""

			# Store braille settings if available
			if self.hwBrailleModule is not None:
				try:
					self.initialSettings.update({
						"brailleGradeEntry": config.conf["HumanwareBrailleTranslation"]["TranslatorTypeForEntry"],
						"brailleGradeDisplay": config.conf["HumanwareBrailleTranslation"]["TranslatorTypeForDisplay"],
						"computerTranslator": config.conf["HumanwareBrailleTranslation"]["G0TranslatorChoice"],
						"literaryTranslator": config.conf["HumanwareBrailleTranslation"]["translatorChoice"],
					})
				except KeyError as e:
					log.warning(f"Could not store some braille settings: {e}")

			# Add Math Code setting only if available
			if self.hwMathModule is not None:
				try:
					self.initialSettings["mathCode"] = config.conf["HWMath"]["mathCodeChoice"]
				except KeyError:
					log.warning("HWMath config not found despite addon being available")

			log.debug(f"Initial settings stored: {self.initialSettings}")
		except Exception as e:
			log.error(f"Error storing initial settings: {e}", exc_info=True)

	def onCancel(self, evt):
		"""Restore all settings to their initial values when dialog is canceled."""
		log.debug("Dialog canceled, restoring initial settings")
		
		try:
			# Restore synthesizer
			if synthDriverHandler.getSynth().name != self.initialSettings["synthName"]:
				synthDriverHandler.setSynth(self.initialSettings["synthName"])

			# Restore voice, rate, and pitch
			driver = synthDriverHandler.getSynth()
			driver.voice = self.initialSettings["voice"]
			driver.rate = self.initialSettings["rate"]
			driver.pitch = self.initialSettings["pitch"]

			try:
				if "variant" in self.initialSettings and hasattr(driver, "variant"):
					driver.variant = self.initialSettings["variant"]
			except (AttributeError, NotImplementedError):
				pass

			# Restore braille settings if available
			if self.hwBrailleModule is not None:
				try:
					config.conf["HumanwareBrailleTranslation"]["TranslatorTypeForEntry"] = self.initialSettings.get("brailleGradeEntry", "")
					config.conf["HumanwareBrailleTranslation"]["TranslatorTypeForDisplay"] = self.initialSettings.get("brailleGradeDisplay", "")
					config.conf["HumanwareBrailleTranslation"]["G0TranslatorChoice"] = self.initialSettings.get("computerTranslator", "")
					config.conf["HumanwareBrailleTranslation"]["translatorChoice"] = self.initialSettings.get("literaryTranslator", "")
				except KeyError as e:
					log.warning(f"Could not restore some braille settings: {e}")

			# Restore math code if available
			if self.hwMathModule is not None and "mathCode" in self.initialSettings:
				try:
					config.conf["HWMath"]["mathCodeChoice"] = self.initialSettings["mathCode"]
				except KeyError:
					log.warning("Cannot restore HWMath settings - configuration not found")

			log.info("All settings restored to initial values")
		except Exception as e:
			log.error(f"Error restoring settings: {e}", exc_info=True)

		# Call the parent class's onCancel
		super().onCancel(evt)

	def onOk(self, evt):
		"""Save all settings when dialog is confirmed."""
		log.debug("Dialog confirmed, saving settings")
		try:
			driver = self.getDriver()
			synthName = driver.name

			# Save the main synthesizer setting
			log.debug(f"Setting speech synthesizer to {synthName}")
			config.conf["speech"]["synth"] = synthName

			# Save synthesizer-specific settings
			log.debug(f"Saving settings for {synthName} synthesizer")
			if hasattr(driver, "voice"):
				config.conf["speech"][synthName]["voice"] = driver.voice

			if hasattr(driver, "rate"):
				config.conf["speech"][synthName]["rate"] = driver.rate

			if hasattr(driver, "pitch"):
				config.conf["speech"][synthName]["pitch"] = driver.pitch

			# Save variant if available
			try:
				if hasattr(driver, "variant"):
					config.conf["speech"][synthName]["variant"] = driver.variant
			except (AttributeError, NotImplementedError):
				log.debug(f"Variant not available for {synthName}")

			# Save braille settings if available
			if self.hwBrailleModule is not None:
				# Save braille entry grade
				if hasattr(self, "gradeEntryChoice") and self.gradeEntryChoice is not None and self.gradeEntryChoice.GetSelection() != -1:
					entryGrade = self.gradeTypes[self.gradeEntryChoice.GetSelection()]
					log.debug(f"Setting braille entry grade to {entryGrade}")
					config.conf["HumanwareBrailleTranslation"]["TranslatorTypeForEntry"] = BRAILLE_TYPE_MAP[entryGrade]

				# Save braille display grade
				if hasattr(self, "gradeDisplayChoice") and self.gradeDisplayChoice is not None and self.gradeDisplayChoice.GetSelection() != -1:
					displayGrade = self.gradeTypes[self.gradeDisplayChoice.GetSelection()]
					log.debug(f"Setting braille display grade to {displayGrade}")
					config.conf["HumanwareBrailleTranslation"]["TranslatorTypeForDisplay"] = BRAILLE_TYPE_MAP[displayGrade]

				# Save computer translator
				if hasattr(self, "computerBrailleTranslatorChoice") and self.computerBrailleTranslatorChoice is not None and self.computerBrailleTranslatorChoice.GetSelection() != -1:
					computerTranslator = self.computerTranslatorChoices[self.computerBrailleTranslatorChoice.GetSelection()]
					index = self.computerTranslatorChoices.index(computerTranslator)
					computerTranslatorFile = self.computerBrailleTranslatorFiles[index]
					config.conf["HumanwareBrailleTranslation"]["G0TranslatorChoice"] = computerTranslatorFile

				# Save literary translator
				if hasattr(self, "literaryBrailleTranslatorChoice") and self.literaryBrailleTranslatorChoice is not None and self.literaryBrailleTranslatorChoice.GetSelection() != -1:
					translationProvider = getattr(self.hwBrailleModule, "translationProvider", None)
					if translationProvider is not None:
						try:
							literaryTranslatorChoices = translationProvider.getTranslators()
							literaryTranslator = literaryTranslatorChoices[self.literaryBrailleTranslatorChoice.GetSelection()]
							log.debug(f"Setting literary translator to {literaryTranslator}")
							config.conf["HumanwareBrailleTranslation"]["translatorChoice"] = literaryTranslator
						except Exception as e:
							log.error(f"Error saving literary translator: {e}")
					else:
						log.warning("Cannot save literary translator - translationProvider not available")

			# Save math code if available
			if self.hwMathModule is not None and hasattr(self, "mathCodeChoice") and self.mathCodeChoice is not None and self.mathCodeChoice.GetSelection() != -1:
				try:
					mathCodeChoices = list(MATH_CODE_MAP.keys())
					mathCode = mathCodeChoices[self.mathCodeChoice.GetSelection()]
					log.debug(f"Setting math code to {mathCode}")
					config.conf["HWMath"]["mathCodeChoice"] = MATH_CODE_MAP[mathCode]
					self._saveMathSettingToRegistry()
				except KeyError:
					log.error("Cannot save HWMath settings - configuration not found")

			config.conf.save()
			log.info("All settings saved successfully")
		except Exception as e:
			log.error(f"Error saving settings: {e}", exc_info=True)

		# Call the parent class's onOk
		super().onOk(evt)

	def _saveMathSettingToRegistry(self):
		# Write that in registry for other apps to access it
		registry_key = r"SOFTWARE\Humanware\Settings"
		value = config.conf["HWMath"]["mathCodeChoice"]
		with winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry_key) as k:
			winreg.SetValueEx(k, "MathBrailleCode", None, winreg.REG_SZ, value)

	def getDriver(self):
		"""Get the current synthesizer driver."""
		return synthDriverHandler.getSynth()

	def updateSynthesizerList(self):
		"""Update the list of available synthesizers in the UI."""
		log.debug("Updating synthesizer list")
		try:
			# Make sure driverList exists and has data
			if not hasattr(self, "driverList") or not self.driverList:
				log.info("Driver list not available, refreshing...")
				self.driverList = synthDriverHandler.getSynthList()
				self.synthNames = [x[0] for x in self.driverList]

			# Get display names for the synthesizers
			options = [x[1] for x in self.driverList]
			log.debug(f"Found {len(options)} synthesizer options")

			# Clear and populate the list
			self.synthList.Clear()
			self.synthList.Set(options)

			# Set the current selection
			try:
				currentDriver = self.getDriver()
				index = self.synthNames.index(currentDriver.name)
				self.synthList.SetSelection(index)
			except (ValueError, AttributeError) as e:
				log.warning(f"Could not set current synthesizer selection: {e}")
				if self.synthList.GetCount() > 0:
					self.synthList.SetSelection(0)
		except Exception as e:
			log.error(f"Error updating synthesizer list: {e}", exc_info=True)

	def updateVariantList(self):
		log.debug("Attempt to get variant list")
		driver = self.getDriver()
		try:
			self.variantList.Clear()
			variants: OrderedDict[str, synthDriverHandler.VoiceInfo] =driver._getAvailableVariants()

			if variants:
				self.variantList.Enable(True)
				self.variantNames = list(variants.keys())
				self.variants = variants
				self.variantList.AppendItems(self.variantNames)

			try:
				currentVariant = getattr(driver, "variant", "")
				log.debug(f"Current variant is: {currentVariant}")

				if currentVariant and currentVariant in self.variantNames:
					index = self.variantNames.index(currentVariant)
					self.variantList.SetSelection(index)
					log.debug(f"Set variant selection to index {index}: {currentVariant}")

				elif self.variantList.GetCount() > 0:
					self.variantList.SetSelection(0)
					log.debug("Current variant not found, defaulting to first item")

				else:
					log.debug("No variants available for this synthesizer")
					self.variantList.Enable(False)
					self.variantNames = []
					self.variants = {}

			except (ValueError, AttributeError) as e:
				log.warning(f"Failed to retrieve the current variant : {e}")
				if self.variantList.GetCount() > 0:
					self.variantList.SetSelection(0)

		except NotImplementedError:
			log.warning(f"No variant for {driver.getDisplayName()}")
			self.variantList.Enable(False)
			self.variantNames = []
			self.variants = []

		except Exception as e:
			log.error(f"Error getting variant list : {e}", exc_info=True)

	def updateVoiceList(self):
		"""Update the list of available voices for the current synthesizer."""
		log.debug("Updating voice list")
		try:
			# Clear the current list first
			self.voiceList.Clear()

			driver = self.getDriver()
			self.voices = list(driver.availableVoices.values())

			# Add voices to the list
			self.voiceList.AppendItems([voice.displayName for voice in self.voices])

			# Set the current selection
			try:
				currentVoice = driver.voice
				index = [voice.id for voice in self.voices].index(currentVoice)
				self.voiceList.SetSelection(index)
			except (ValueError, AttributeError) as e:
				log.debug(f"Voice selection issue: {e}")
				if self.voiceList.GetCount() > 0:
					self.voiceList.SetSelection(0)
		except Exception as e:
			log.error(f"Error updating voice list: {e}", exc_info=True)

	def onSynthesizerChange(self, evt):
		"""Handle change of synthesizer selection."""
		selection = evt.GetSelection()
		if selection != -1:
			synthName = self.synthNames[selection]
			log.debug(f"Synthesizer change to {synthName}")

			synthDriverHandler.setSynth(synthName)
			self.updateVoiceList()
			self.updateVariantList()

			try:
				driver = self.getDriver()
				if hasattr(driver, "rate"):
					self.rateSpeed.SetValue(driver.rate)
					log.debug(f"Restored rate to {driver.rate} for synthesizer {synthName}")

				if hasattr(driver, "pitch"):
					self.voicePitch.SetValue(driver.pitch)
					log.debug(f"Restored pitch to {driver.pitch} for synthesizer {synthName}")
			except Exception as e:
				log.error(f"Error restoring rate/pitch for synthesizer {synthName}: {e}", exc_info=True)

		evt.Skip()
  
	def getComputerBrailleTranslatorsChoices(self):
		"""Get the list of available computer braille translators."""
		try:
			return [table.displayName for table in brailleTables.listTables() if table.computerBraille]
		except Exception as e:
			log.error(f"Error retrieving computer braille translators: {e}", exc_info=True)
			return []

	def getComputerBrailleTranslatorsFiles(self): 
		"""Get the list of available computer braille translator files."""
		try:
			return [table.fileName for table in brailleTables.listTables() if table.computerBraille]
		except Exception as e:
			log.error(f"Error retrieving computer braille translator files: {e}", exc_info=True)
			return []


class CustomProfilesDialog(ProfilesDialog):
	"""Custom profiles dialog with trigger-related UI elements hidden."""

	def __init__(self, parent):
		super().__init__(parent)

		# Hide trigger-related UI elements
		for child in self.Children:
			if hasattr(child, "GetLabel"):
				childLabel = child.GetLabel()

				# Hide the Triggers button
				# Translators: Label for the button to configure triggers
				# The "&" indicates that the next character is a keyboard accelerator
				if childLabel == _("&Triggers..."):
					log.debug("Hiding Triggers button")
					child.Hide()
					child.Enable(False)

				# Hide the temporarily disable triggers checkbox
				# Translators: Label for the checkbox to temporarily disable all triggers
				# The "&" indicates that the next character is a keyboard accelerator
				elif childLabel == _("Temporarily d&isable all triggers"):
					log.debug("Hiding disable triggers checkbox")
					child.Hide()
					child.Enable(False)

		# Update layout after hiding elements
		self.Layout()
		self.Fit()
		self.CenterOnScreen()

	def onNew(self, evt):
		self.Disable()
		# Call the original NewProfileDialog but customize it
		dialog = NewProfileDialog(self)

		for child in dialog.Children:
			log.debug(f"Child Label: {child.GetLabel()}")
			if isinstance(child, wx.RadioBox):
				log.debug("Hiding trigger choice radio box")
				child.Hide()
				child.Enable(False)

		dialog.Layout()
		dialog.Fit()
		dialog.CenterOnScreen()

		# Translators: Title of the New Language Profile dialog
		dialog.SetTitle(_("New Language Profile"))

		# Show the modified dialog
		dialog.Show()


class SelectLanguageProfileDialog(settingsDialogs.SettingsDialog):
	"""Dialog for selecting a language profile."""
	# Translators: Title of the Select Language Profile dialog
	title = _("Select Language Profile")

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

	def getProfileDisplay(self, name):
		return name if name else _("(normal configuration)")

	def makeSettings(self, settingsSizer):
		"""Create and add the settings controls."""
		log.debug("Creating Configure Language profile controls")
		sHelper = BoxSizerHelper(self, sizer=settingsSizer)

		self.profileNames = [None]
		self.profileNames.extend(config.conf.listProfiles())

		#Profile selection control
		self.profileList = sHelper.addLabeledControl(		
		_("Select Language Profile"),
		wx.ListBox,
		choices = [self.getProfileDisplay(name) for name in self.profileNames]
		)

		self.profileList.Bind(wx.EVT_LISTBOX, self.onProfileChange)

		try:
			currentProfileName = config.conf.profiles[-1].name
			log.debug(f"Current active profile: {currentProfileName}")

			currentIndex = self.profileNames.index(currentProfileName)
			self.profileList.SetSelection(currentIndex)
		except (ValueError, IndexError, AttributeError) as e:
			log.debug(f"Could not set current profile selection : {e}")
			self.profileList.SetSelection(0)

		wx.CallAfter(self.profileList.SetFocus)

	def onProfileChange(self, evt):
		"""Handle change of profile selection."""
		selection = self.profileList.GetSelection()
		if selection != -1:
			profileName = self.profileNames[selection]
			log.debug(f"Profile selection changed to {self.getProfileDisplay(profileName)}")
		evt.Skip()

	def onOk(self, evt):
		"""Handle OK button press to activate the selected profile."""		
		selection = self.profileList.GetSelection()
		if selection != -1:
			profileName = self.profileNames[selection]
			log.debug(f"Activating profile: {self.getProfileDisplay(profileName)}")

			try:
				config.conf.manualActivateProfile(profileName)
				log.info(f"Successfully activated profile : {self.getProfileDisplay(profileName)}")

			except Exception as e:
				log.error(f"Error activating profile : {e}", exc_info=True)
				gui.messageBox(
					# Translators: Message displayed when there is an error activating the selected language profile
					_("Error activating profile."),
					# Translators: General error dialog title
					_("Error"),
					wx.OK | wx.ICON_ERROR,
					self
				)
				return

		super().onOk(evt)


# Module-level functions for opening dialogs

_configureLanguageProfileDialog = None
_manageLanguageProfilesDialog = None
_selectLanguageProfileDialog = None


def openConfigureLanguageProfile():
	"""Open the configure language profile dialog."""
	log.info("Opening Configure Language profile")
	wx.CallAfter(_openConfigureLanguageProfileMainThread)


def _onConfigureLanguageProfileDialogDestroy(evt):
	"""Handle dialog destroy event - clear the dialog reference."""
	global _configureLanguageProfileDialog
	_configureLanguageProfileDialog = None
	evt.Skip()
	# Explicitly restore NVDA focus tracking after dialog closes
	# This is needed because the dialog was opened from a background thread
	try:
		focus = api.getDesktopObject().objectWithFocus()
		if focus:
			queueHandler.queueFunction(queueHandler.eventQueue, eventHandler.queueEvent, "gainFocus", focus)
	except Exception as e:
		log.error(f"Error restoring focus after dialog close: {e}", exc_info=True)


def _openConfigureLanguageProfileMainThread():
	"""This method runs in the main thread to safely open the Configure Language profile dialog"""
	global _configureLanguageProfileDialog
	
	gui.mainFrame.prePopup()
	try:
		_configureLanguageProfileDialog = ConfigureLanguageProfileDialog(gui.mainFrame)
		_configureLanguageProfileDialog.Bind(wx.EVT_WINDOW_DESTROY, _onConfigureLanguageProfileDialogDestroy)
		_configureLanguageProfileDialog.Show()
	except settingsDialogs.SettingsDialog.MultiInstanceErrorWithDialog:
		_configureLanguageProfileDialog.Raise()
		_configureLanguageProfileDialog.SetFocus()
	except Exception as e:
		log.error(f"Error creating dialog: {e}", exc_info=True)
	finally:
		gui.mainFrame.postPopup()


def openManageLanguageProfiles():
	"""Open the manage language profiles dialog."""
	log.info("Opening Manage Language profiles")
	wx.CallAfter(_openManageLanguageProfilesMainThread)

def _onManageLanguageProfilesDialogDestroy(evt):
	"""Handle dialog destroy event - clear the dialog reference."""
	global _manageLanguageProfilesDialog
	_manageLanguageProfilesDialog = None
	evt.Skip()
	# Explicitly restore NVDA focus tracking after dialog closes
	# This is needed because the dialog was opened from a background thread
	try:
		focus = api.getDesktopObject().objectWithFocus()
		if focus:
			queueHandler.queueFunction(queueHandler.eventQueue, eventHandler.queueEvent, "gainFocus", focus)
	except Exception as e:
		log.error(f"Error restoring focus after dialog close: {e}", exc_info=True)


def _openManageLanguageProfilesMainThread():
	"""This method runs in the main thread to safely open the Manage Language profile dialog"""
	global _manageLanguageProfilesDialog
	
	gui.mainFrame.prePopup()
	try:
		if _manageLanguageProfilesDialog is not None:
			_manageLanguageProfilesDialog.Raise()
			_manageLanguageProfilesDialog.SetFocus()
		else:
			_manageLanguageProfilesDialog = CustomProfilesDialog(gui.mainFrame)			
			_manageLanguageProfilesDialog.Bind(wx.EVT_WINDOW_DESTROY, _onManageLanguageProfilesDialogDestroy)
			# Translators: Title of the Manage Language Profiles dialog
			_manageLanguageProfilesDialog.SetTitle(_("Manage Language Profiles"))
			_manageLanguageProfilesDialog.Show()
	finally:
		gui.mainFrame.postPopup()


def openSelectLanguageProfile():
	"""Open the select language profile dialog."""
	log.info("Opening Select Language Profile")
	wx.CallAfter(_openSelectLanguageProfileThread)

def _onSelectLanguageProfileDialogDestroy(evt):
	"""Handle dialog destroy event - clear the dialog reference."""
	global _selectLanguageProfileDialog
	_selectLanguageProfileDialog = None
	evt.Skip()
	# Explicitly restore NVDA focus tracking after dialog closes
	# This is needed because the dialog was opened from a background thread
	try:
		focus = api.getDesktopObject().objectWithFocus()
		if focus:
			queueHandler.queueFunction(queueHandler.eventQueue, eventHandler.queueEvent, "gainFocus", focus)
	except Exception as e:
		log.error(f"Error restoring focus after dialog close: {e}", exc_info=True)


def _openSelectLanguageProfileThread():
	"""This method runs in the main thread to safely open the Select Language profile dialog"""
	global _selectLanguageProfileDialog
	
	gui.mainFrame.prePopup()
	try:
		_selectLanguageProfileDialog = SelectLanguageProfileDialog(gui.mainFrame)		
		_selectLanguageProfileDialog.Bind(wx.EVT_WINDOW_DESTROY, _onSelectLanguageProfileDialogDestroy)
		_selectLanguageProfileDialog.Show()
	except settingsDialogs.SettingsDialog.MultiInstanceErrorWithDialog:
		_selectLanguageProfileDialog.Raise()
		_selectLanguageProfileDialog.SetFocus()
	except Exception as e:
		log.error(f"Error creating dialog: {e}", exc_info=True)
	finally:
		gui.mainFrame.postPopup()

def handleSelectLanguageProfileShortcut():
	profileNames = [None]
	profileNames.extend(config.conf.listProfiles())

	if len(profileNames) > 2:
		wx.CallAfter(_openSelectLanguageProfileThread)
		return

	try:
		currentProfileIndex = profileNames.index(config.conf.profiles[-1].name)
		currentProfileName = profileNames[currentProfileIndex]

		if len(profileNames) ==0:
			raise ValueError("No profiles available, not even the default profile")

		if len(profileNames) == 1:
			log.info("Profile switching skipped: Only the default profile (normal configuration) is available.")
			playErrorSound()
			return

		if currentProfileName is None:
			targetProfileName = profileNames[1]
			log.info(f"Switching to profile : {targetProfileName}")
			wx.CallAfter(_switchToProfile, targetProfileName)
		else:
			log.info("Switching to profile : (normal configuration)")
			wx.CallAfter(_switchToProfile, None)

	except Exception as e:
		log.error(f"Error switch profiles: {e}")

def _switchToProfile(profileName):
	try:
		config.conf.manualActivateProfile(profileName)
		displayName = profileName if profileName else _("(normal configuration)")
		log.info(f"Activated profile : {displayName}")

		# Braille and speech
		ui.message(displayName)
	except Exception as e:
		log.error(f"Error switching profiles: {e}", exc_info=True)
