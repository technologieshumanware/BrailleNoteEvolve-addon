# BrailleNoteEvolve add-on
# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# Copyright (C) 2026 Technologies Humanware

# Named pipe base class for NVDA global plugins
# Provides common functionality for named pipe communication

import ctypes
import ctypes.wintypes
import threading
import time
import globalPluginHandler
from logHandler import log
from abc import ABC, abstractmethod

# Named pipe constants
PIPE_ACCESS_DUPLEX = 0x3
PIPE_TYPE_MESSAGE = 0x4
PIPE_READMODE_MESSAGE = 0x2
PIPE_WAIT = 0x0
PIPE_UNLIMITED_INSTANCES = 255
INVALID_HANDLE_VALUE = -1
ERROR_PIPE_CONNECTED = 535
BUFFER_SIZE = 1024

GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80


class NamedPipeGlobalPlugin(globalPluginHandler.GlobalPlugin, ABC):
	"""
	Abstract base class for global plugins that use named pipes for communication.
	
	Subclasses must implement:
	- getIncomingPipeName(): str - Name of the pipe to listen on
	- getOutgoingPipeName(): str - Name of the pipe to send to
	- processMessage(message: str, hPipe): - Handle incoming messages
	"""

	def __init__(self, *args, **kwargs):
		super(NamedPipeGlobalPlugin, self).__init__(*args, **kwargs)
		self.running = True
		self.incomingPipeName = self.getIncomingPipeName()
		self.outgoingPipeName = self.getOutgoingPipeName()
		
		# Initialize Windows API functions
		self._init_win_api_functions()
		
		# Start listener thread
		self.listenerThread = threading.Thread(target=self.pipeListener, name=f"pipeListener-{self.__class__.__name__}")
		self.listenerThread.daemon = True
		self.listenerThread.start()

	@abstractmethod
	def getIncomingPipeName(self) -> str:
		"""Return the name of the incoming named pipe."""
		pass

	@abstractmethod
	def getOutgoingPipeName(self) -> str:
		"""Return the name of the outgoing named pipe."""
		pass

	@abstractmethod
	def processMessage(self, message: str, hPipe):
		"""
		Process a message received from the named pipe.
		
		Args:
			message: The message string received
			hPipe: The pipe handle for sending responses
		"""
		pass

	def _init_win_api_functions(self):
		"""Initialize Windows API functions."""
		self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

		# CreateNamedPipeW
		self.CreateNamedPipeW = self.kernel32.CreateNamedPipeW
		self.CreateNamedPipeW.argtypes = [
			ctypes.c_wchar_p,
			ctypes.wintypes.DWORD,
			ctypes.wintypes.DWORD,
			ctypes.wintypes.DWORD,
			ctypes.wintypes.DWORD,
			ctypes.wintypes.DWORD,
			ctypes.wintypes.DWORD,
			ctypes.c_void_p
		]
		self.CreateNamedPipeW.restype = ctypes.wintypes.HANDLE

		# ConnectNamedPipe
		self.ConnectNamedPipe = self.kernel32.ConnectNamedPipe
		self.ConnectNamedPipe.argtypes = [
			ctypes.wintypes.HANDLE,
			ctypes.c_void_p
		]
		self.ConnectNamedPipe.restype = ctypes.wintypes.BOOL

		# ReadFile
		self.ReadFile = self.kernel32.ReadFile
		self.ReadFile.argtypes = [
			ctypes.wintypes.HANDLE,
			ctypes.c_void_p,
			ctypes.wintypes.DWORD,
			ctypes.POINTER(ctypes.wintypes.DWORD),
			ctypes.c_void_p
		]
		self.ReadFile.restype = ctypes.wintypes.BOOL

		# WriteFile
		self.WriteFile = self.kernel32.WriteFile
		self.WriteFile.argtypes = [
			ctypes.wintypes.HANDLE,
			ctypes.c_void_p,
			ctypes.wintypes.DWORD,
			ctypes.POINTER(ctypes.wintypes.DWORD),
			ctypes.c_void_p
		]
		self.WriteFile.restype = ctypes.wintypes.BOOL

		# CloseHandle
		self.CloseHandle = self.kernel32.CloseHandle
		self.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
		self.CloseHandle.restype = ctypes.wintypes.BOOL

		# CreateFileW
		self.CreateFileW = self.kernel32.CreateFileW
		self.CreateFileW.argtypes = [
			ctypes.c_wchar_p,
			ctypes.wintypes.DWORD,
			ctypes.wintypes.DWORD,
			ctypes.c_void_p,
			ctypes.wintypes.DWORD,
			ctypes.wintypes.DWORD,
			ctypes.wintypes.HANDLE
		]
		self.CreateFileW.restype = ctypes.wintypes.HANDLE

		# FlushFileBuffers
		self.FlushFileBuffers = self.kernel32.FlushFileBuffers
		self.FlushFileBuffers.argtypes = [ctypes.wintypes.HANDLE]
		self.FlushFileBuffers.restype = ctypes.wintypes.BOOL

	def _write_to_pipe(self, pipe_handle, message):
		"""Helper method to write a message to a pipe."""
		if isinstance(message, str):
			message = message.encode('utf-8')

		bytesWritten = ctypes.wintypes.DWORD(0)
		result = self.WriteFile(
			pipe_handle,
			message,
			len(message),
			ctypes.byref(bytesWritten),
			None
		)

		if not result:
			error = ctypes.get_last_error()
			log.error(f"Failed to write to pipe: {error}")
			return False
		
		# Flush to ensure data is sent immediately
		self.FlushFileBuffers(pipe_handle)
		return True

	def pipeListener(self):
		"""Thread function that listens to incoming messages on the named pipe."""
		while self.running:
			try:
				hPipe = self.CreateNamedPipeW(
					self.incomingPipeName,
					PIPE_ACCESS_DUPLEX,
					PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
					PIPE_UNLIMITED_INSTANCES,
					BUFFER_SIZE,
					BUFFER_SIZE,
					0,
					None
				)

				if hPipe == INVALID_HANDLE_VALUE:
					log.error(f"Failed to create named pipe: {ctypes.get_last_error()}")
					time.sleep(1)
					continue

				# Wait for a client to connect
				result = self.ConnectNamedPipe(hPipe, None)
				error = ctypes.get_last_error()

				if result == 0 and error != ERROR_PIPE_CONNECTED:
					log.error(f"Failed to connect to named pipe: {error}")
					self.CloseHandle(hPipe)
					continue

				buffer = ctypes.create_string_buffer(BUFFER_SIZE)
				bytesRead = ctypes.wintypes.DWORD(0)

				result = self.ReadFile(hPipe, buffer, BUFFER_SIZE, ctypes.byref(bytesRead), None)

				if result:
					bytesReceived = buffer.raw[:bytesRead.value]
					try:
						message = bytesReceived.decode('utf-8')
						self.processMessage(message, hPipe)
					except UnicodeDecodeError as e:
						log.error(f"Unicode decode error: {e}, bytes: {bytesReceived!r}")
					except Exception as e:
						log.error(f"Exception in processMessage: {e}", exc_info=True)
				else:
					log.error(f"Failed to read from pipe: {ctypes.get_last_error()}")

				self.CloseHandle(hPipe)

			except Exception as e:
				log.error(f"Exception in pipe listener: {e}")
				time.sleep(1)

	def sendMessage(self, message):
		"""Send a message to the control center via the named pipe."""
		try:
			hPipe = self.CreateFileW(
				self.outgoingPipeName,
				GENERIC_WRITE,
				0,
				None,
				OPEN_EXISTING,
				FILE_ATTRIBUTE_NORMAL,
				None
			)

			if hPipe == INVALID_HANDLE_VALUE:
				log.error(f"Failed to connect to outgoing pipe: {ctypes.get_last_error()}")
				return

			self._write_to_pipe(hPipe, message)
			self.CloseHandle(hPipe)

		except Exception as e:
			log.error(f"Exception in sending message: {e}")

	def terminate(self):
		"""Stop the pipe listener and clean up."""
		self.running = False
		return super(NamedPipeGlobalPlugin, self).terminate()
