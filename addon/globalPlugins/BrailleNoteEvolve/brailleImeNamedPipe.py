# BrailleNoteEvolve add-on
# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# Copyright (C) 2026 Technologies Humanware


import json
import threading
import ctypes
from ctypes import wintypes

from logHandler import log
import brailleInput

PIPE_NAME = r"\\.\pipe\BrailleIMEPipe"
IME_PIPE_NAME = r"\\.\pipe\BrailleIMEPipeServer"
BUFFER_SIZE = 4096
TIMEOUT_MS = 1000
NUM_PIPE_INSTANCES = 5

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

ULONG_PTR = ctypes.c_uint64
HANDLE = wintypes.HANDLE
LPCWSTR = wintypes.LPCWSTR
DWORD = wintypes.DWORD
BOOL = wintypes.BOOL
LPVOID = wintypes.LPVOID
LPDWORD = ctypes.POINTER(DWORD)

class OVERLAPPED(ctypes.Structure):
	_fields_ = [
		("Internal", ULONG_PTR),
		("InternalHigh", ULONG_PTR),
		("Offset", DWORD),
		("OffsetHigh", DWORD),
		("hEvent", HANDLE)
	]
	_pack_ = 8

LPOVERLAPPED = ctypes.POINTER(OVERLAPPED)

kernel32.CreateNamedPipeW.restype = HANDLE
kernel32.CreateNamedPipeW.argtypes = [
	LPCWSTR, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, LPVOID
]

kernel32.ConnectNamedPipe.restype = BOOL
kernel32.ConnectNamedPipe.argtypes = [HANDLE, LPVOID]

kernel32.ReadFile.restype = BOOL
kernel32.ReadFile.argtypes = [HANDLE, LPVOID, DWORD, LPDWORD, LPVOID]

kernel32.WriteFile.restype = BOOL
kernel32.WriteFile.argtypes = [HANDLE, LPVOID, DWORD, LPDWORD, LPVOID]

kernel32.DisconnectNamedPipe.restype = BOOL
kernel32.DisconnectNamedPipe.argtypes = [HANDLE]

kernel32.CreateFileW.restype = HANDLE
kernel32.CreateFileW.argtypes = [LPCWSTR, DWORD, DWORD, LPVOID, DWORD, DWORD, HANDLE]

kernel32.WaitNamedPipeW.restype = BOOL
kernel32.WaitNamedPipeW.argtypes = [LPCWSTR, DWORD]

kernel32.CreateEventW.restype = HANDLE
kernel32.CreateEventW.argtypes = [LPVOID, BOOL, BOOL, LPCWSTR]

kernel32.WaitForSingleObject.restype = DWORD
kernel32.WaitForSingleObject.argtypes = [HANDLE, DWORD]

kernel32.GetOverlappedResult.restype = BOOL
kernel32.GetOverlappedResult.argtypes = [HANDLE, LPOVERLAPPED, LPDWORD, BOOL]

kernel32.ResetEvent.restype = BOOL
kernel32.ResetEvent.argtypes = [HANDLE]

kernel32.CloseHandle.restype = BOOL
kernel32.CloseHandle.argtypes = [HANDLE]

FILE_FLAG_OVERLAPPED = 0x40000000
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
ERROR_IO_PENDING = 997
INFINITE = 0xFFFFFFFF

PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_MESSAGE = 0x00000004
PIPE_READMODE_MESSAGE = 0x00000002
PIPE_WAIT = 0x00000000
PIPE_UNLIMITED_INSTANCES = 255
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value  # Properly sized for 32/64-bit
ERROR_PIPE_CONNECTED = 535
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
NMPWAIT_USE_DEFAULT_WAIT = 0
IME_PIPE_WAIT_TIMEOUT_MS = 200

def get_last_error():
	return kernel32.GetLastError()

class BrailleImePipeServer:
	def __init__(self):
		self.pipe_name = PIPE_NAME
		self.running = False
		self.server_thread = None
		self.pipe_threads = []
		self.pipe_instances_lock = threading.Lock()
		self.unicode_braille_input_enable = False

	def start_server(self):
		if not self.running:
			log.info("Starting Braille IME Pipe Server...")
			self.running = True
			self.server_thread = threading.Thread(target=self._manage_pipe_instances, daemon=True)
			self.server_thread.start()
			log.info("Braille IME Pipe Server started.")
		else :
			log.info("Braille IME Pipe Server is already running.")

	def stop_server(self):
		if self.running:
			log.info("Stopping Braille IME Pipe Server...")
			self.running = False

			with self.pipe_instances_lock:
				for thread in self.pipe_threads:
					if thread.is_alive():
						thread.join(timeout=1.0)

			if self.server_thread and self.server_thread.is_alive():
				self.server_thread.join(timeout=1.0)
				log.info("Braille IME Pipe Server stopped.")
			else :
				log.info("Braille IME Pipe Server thread was not alive.")
		else :
			log.info("Braille IME Pipe Server is not running.")

	def _manage_pipe_instances(self):
		while self.running:
			try:
				with self.pipe_instances_lock:
					self.pipe_threads = [t for t in self.pipe_threads if t.is_alive()]
					active_threads = len(self.pipe_threads)

				instances_to_create = NUM_PIPE_INSTANCES - active_threads
				for _ in range(instances_to_create):
					if not self.running:
						break

					thread = threading.Thread(target=self._handle_pipe_instance, daemon=True)
					thread.start()

					with self.pipe_instances_lock:
						self.pipe_threads.append(thread)

				threading.Event().wait(0.1)

			except Exception as e :
				if self.running:
					log.error(f"Error in pipe instance manager : {e}")

	def _handle_pipe_instance(self):
		pipe_handle = INVALID_HANDLE_VALUE
		event_handle = kernel32.CreateEventW(None, True, False, None)

		overlapped = OVERLAPPED()
		overlapped.hEvent = event_handle

		try:
			pipe_handle = kernel32.CreateNamedPipeW(
				self.pipe_name,
				PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
				PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
				PIPE_UNLIMITED_INSTANCES,
				BUFFER_SIZE,
				BUFFER_SIZE,
				TIMEOUT_MS,
				None
			)

			if pipe_handle == INVALID_HANDLE_VALUE:
				error_code = get_last_error()
				log.error(f"Failed to create named pipe. Error code : {error_code}")
				return

			log.debug("Pipe instance created, waiting for client to connect...")

			connected = kernel32.ConnectNamedPipe(pipe_handle, ctypes.byref(overlapped))
			err = get_last_error()

			if not connected and err == ERROR_IO_PENDING:
				while self.running:
					wait_res = kernel32.WaitForSingleObject(event_handle, 200)
					if wait_res == WAIT_OBJECT_0:
						break
					elif wait_res == WAIT_TIMEOUT:
						continue

				if not self.running:
					return
			elif not connected and err != ERROR_PIPE_CONNECTED:
				log.error(f"Failed to connect named pipe. Error code: {err}")
				return

			log.debug("Client connected to Braille IME pipe")
			self.handle_client(pipe_handle, overlapped)

			kernel32.DisconnectNamedPipe(pipe_handle)
			log.debug("Client disconnected from Braille IME pipe")

		except Exception as e:
			if self.running:
				log.error(f"Error in pipe instance handler : {e}")

		finally:
			if pipe_handle != INVALID_HANDLE_VALUE:
				kernel32.CloseHandle(pipe_handle)
			if event_handle:
				kernel32.CloseHandle(event_handle)


	def handle_client(self, pipe_handle, overlapped):
			bytes_read = DWORD(0)
			bytes_written = DWORD(0)

			try:
				buffer = ctypes.create_string_buffer(BUFFER_SIZE)

				kernel32.ResetEvent(overlapped.hEvent)

				success = kernel32.ReadFile(
					pipe_handle,
					buffer,
					BUFFER_SIZE,
					ctypes.byref(bytes_read),
					ctypes.byref(overlapped) # Pass overlapped struct
				)

				# Wait for asynchronous read to finish
				if not success and get_last_error() == ERROR_IO_PENDING:
					kernel32.WaitForSingleObject(overlapped.hEvent, INFINITE)
					success = kernel32.GetOverlappedResult(pipe_handle, ctypes.byref(overlapped), ctypes.byref(bytes_read), False)

				if success and bytes_read.value > 0:
					message = buffer.raw[:bytes_read.value].decode('utf-16-le').strip()
					log.debug(f"Received message: {message}")

					response_message = self._handle_command(message)
					response_bytes = (response_message).encode('utf-16-le')

					kernel32.ResetEvent(overlapped.hEvent)

					success = kernel32.WriteFile(
						pipe_handle,
						response_bytes,
						len(response_bytes),
						ctypes.byref(bytes_written),
						ctypes.byref(overlapped) # Pass overlapped struct
					)

					# Wait for asynchronous write to finish
					if not success and get_last_error() == ERROR_IO_PENDING:
						kernel32.WaitForSingleObject(overlapped.hEvent, INFINITE)
						success = kernel32.GetOverlappedResult(pipe_handle, ctypes.byref(overlapped), ctypes.byref(bytes_written), False)

					if success:
						log.debug(f"Sent response: {response_message}")
					else:
						log.error(f"Failed to send response. Error code: {get_last_error()}")

				else:
					log.error(f"Failed to read message. Error code: {get_last_error()}")

			except Exception as e:
				log.error(f"Error handling client: {e}")
	
	def _set_unicode_braille_mode(self, enable: bool):
		"""ask to enable or disable Unicode Braille input mode."""
		if brailleInput.handler and brailleInput.handler.nativeBrailleRequired and enable:
			#should be already enabled
			brailleInput.handler._setUnicodeBrailleInput(enable)
			return "BRLUCX_disabled"

		try:
			import brailleTranslation
			if brailleTranslation.translationProvider.useComputerBrailleForInput() and enable:
				#context doesn't warrant a change of input mode
				return "BRLUCX_disabled"
		except (ImportError, AttributeError) as e:
			log.warning(f"Could not check braille translation provider: {e}")


		if brailleInput.handler:
			brailleInput.handler._setUnicodeBrailleInput(enable)
			self.unicode_braille_input_enable = enable
			log.info(f"Unicode Braille Input {'enabled' if enable else 'disabled'}")
			return "OK"
		else:
			log.warning("Braille input handler not available")
			return "ERROR"

	def _handle_command(self, message: str) -> str:

		#now controlled the other way, return OK and do nothing.
		if message == "ENABLE_UNICODE_BRAILLE": 	#TODO rename. ENABLE_UNICODE_BRAILLE_INPUT
			return "OK"
			#return self._set_unicode_braille_mode(True)

		if message == "DISABLE_UNICODE_BRAILLE":  #TODO Rename
			return "OK"
			#return self._set_unicode_braille_mode(False)

		parts = message.split(":", 2)

		# Validate that we have all required parts
		if len(parts) < 3:
			log.warning(f"Invalid message format: {message}. Expected format: command:cursorPos:text")
			return message

		command = parts[0]
		try:
			cursorPosition = int(parts[1]) if int(parts[1]) > -1 else None
		except ValueError:
			log.warning(f"Invalid cursor position: {parts[1]}")
			cursorPosition = None
		text = parts[2]

		try:
			import brailleTranslation
			if brailleTranslation.translationProvider is None:
				brailleTranslation.initialize()

			provider = brailleTranslation.translationProvider

			if not provider:
				log.warning("Braille translation provider not available")
				return message
		except ImportError as e:
			log.error(f"Failed to import brailleTranslation: {e}")
			return "ERROR:BrailleTranslationNotAvailable"

		if command == "B2P":
			data = provider.backTranslate(brl = text, cursorPos=cursorPosition)
			return json.dumps(data, ensure_ascii=False)

		if command == "P2B":
			data = provider.translateInGradeForEntry(txt = text, cursorPos=cursorPosition)
			return json.dumps(data, ensure_ascii=False)

		return message


class BrailleImePipeClient:
	"""Client to send messages to the IME's pipe server."""

	def __init__(self, pipe_name=IME_PIPE_NAME):
		self.pipe_name = pipe_name
		self.client_lock = threading.Lock()

	def send_message(self, message: str) -> bool:
		"""Send a message to the IME pipe server.

		Args:
			message: The message to send to the IME
		"""
		ret = True

		with self.client_lock:
			pipe_handle = INVALID_HANDLE_VALUE

			try:
				# Wait for the pipe to be available. Keep the main thread under watchdog timeout.
				timeout_ms = (
					IME_PIPE_WAIT_TIMEOUT_MS
					if threading.current_thread() is threading.main_thread()
					else NMPWAIT_USE_DEFAULT_WAIT
				)
				if not kernel32.WaitNamedPipeW(self.pipe_name, timeout_ms):
					log.info(f"IME pipe not available: {get_last_error()}")
					return False

				# Connect to the pipe
				pipe_handle = kernel32.CreateFileW(
					self.pipe_name,
					GENERIC_READ | GENERIC_WRITE,
					0,
					None,
					OPEN_EXISTING,
					FILE_ATTRIBUTE_NORMAL,
					None
				)

				if pipe_handle == INVALID_HANDLE_VALUE:
					error_code = get_last_error()
					log.info(f"Failed to connect to IME pipe. Error code: {error_code}")
					return False

				log.debug(f"Connected to IME pipe, sending message: {message}")

				# Send the message
				message_bytes = message.encode('utf-16-le')
				bytes_written = DWORD(0)

				success = kernel32.WriteFile(
					pipe_handle,
					message_bytes,
					len(message_bytes),
					ctypes.byref(bytes_written),
					None
				)

				if not success:
					error_code = get_last_error()
					log.info(f"Failed to write to IME pipe. Error code: {error_code}")
					return False

				log.debug(f"Message sent successfully to IME: {message}")
				ret = True

			except Exception as e:
				log.info(f"Error sending message to IME: {e}")
				ret = False

			finally:
				if pipe_handle != INVALID_HANDLE_VALUE:
					kernel32.CloseHandle(pipe_handle)
			return ret
	

	def notify_selection_start(self) -> bool:
		"""Notify IME that selection has started."""
		return self.send_message("start-selection")

	def notify_selection_end(self) -> bool:
		"""Notify IME that selection has ended."""
		return self.send_message("end-selection")

	def notify_translation_suspended(self) -> bool:
		"""Notify IME that translation has been suspended."""
		return self.send_message("translation-suspended")

	def notify_translation_resumed(self) -> bool:
		"""Notify IME that translation has resumed."""
		return self.send_message("translation-resumed")

	def notify_brlucx_enabled(self) -> bool:
		"""Notify IME that brlucx is enabled."""
		return self.send_message("BRLUCX_enabled")

	def notify_brlucx_disabled(self) -> bool:
		"""Notify IME that brlucx is disabled."""
		return self.send_message("BRLUCX_disabled")



# Global pipe client instance
_pipe_client = None


def get_pipe_client() -> BrailleImePipeClient:
	"""Get or create the global pipe client instance."""
	global _pipe_client
	if _pipe_client is None:
		_pipe_client = BrailleImePipeClient()
	return _pipe_client


# Note: This module is instantiated from the main BrailleNoteEvolve GlobalPlugin
# The BrailleImePipeServer is started and stopped from there.
