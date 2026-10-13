# BrailleNoteEvolve Introduction

BrailleNoteEvolve is a NVDA add-on that facilitates interaction with external modules through named pipes, like the Options Menu, regrouping some of the tyical settings into language profiles, and offering a more direct access to some NVDA settings. It also provides a communication channel between NVDA and the BrailleIME for activation and deactivation, general status awareness, and a pass through for the translation requests. 

 


## BrailleNoteEvolve settings
This addon doesn't expose any setting by itself, but it is an essential part of the Options Menu



## Main usages
Facilitates interaction with external modules, and therefore provides a better, more customized user experience on the BrailleNote evolve.


## Building the addon
This addon follows the typical NVDA addon structure, and building it is done through invoking scons on the sconstruct file. 
A few parameters can be passed to specify a resulting version of the addon.  


## Debugging 
Logging would appear in the nvda.log file. 
The addon can be debugged alongside NVDA with the Python debugger of VSCode, provided it gets installed in the user config location. 
For more info: 
https://technologieshumanware.atlassian.net/wiki/spaces/BNW/pages/1004306433/Debug+HumanWare+AddOn


## Localization
Standard NVDA addon localization, described in more details at:
https://technologieshumanware.atlassian.net/wiki/spaces/BNW/pages/457637891/Addons+Localizations



## License. 
This falls under the NVDA plugin exemption where the plugin communicates with non-GPL modules to perform some actions, a situation analog to a speech engine plugin using a proprietary driver. The code of the addon itself is GPL 


## Contact and developer information
Technologies HumanWare <github@humanware.com>
