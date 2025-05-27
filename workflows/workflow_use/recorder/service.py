import asyncio
import json
import pathlib
from typing import Optional

import uvicorn
from aiohttp import ClientSession, web
from fastapi import FastAPI
from playwright.async_api import BrowserContext, async_playwright

# Assuming views.py is correctly located for this import path
from workflow_use.recorder.views import (
	HttpRecordingStoppedEvent,
	HttpWorkflowUpdateEvent,
	RecorderEvent,
	WorkflowDefinitionSchema,  # This is the expected output type
)

# Path Configuration (should be identical to recorder.py if run from the same context)
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
EXT_DIR = SCRIPT_DIR.parent.parent.parent / 'extension' / '.output' / 'chrome-mv3'
USER_DATA_DIR = SCRIPT_DIR / 'user_data_dir'


class RecordingService:
	def __init__(self, app: Optional[FastAPI] = None):
		self.event_queue: asyncio.Queue[RecorderEvent] = asyncio.Queue()
		self.last_workflow_update_event: Optional[HttpWorkflowUpdateEvent] = None
		self.playwright_context: Optional[BrowserContext] = None

		self.final_workflow_output: Optional[WorkflowDefinitionSchema] = None
		self.recording_complete_event = asyncio.Event()
		self.final_workflow_processed_lock = asyncio.Lock()
		self.final_workflow_processed_flag = False

		if app:
			print("[Service] Using provided FastAPI app instance.")
		else:
			print("[Service] Creating new FastAPI app instance with title 'Temporary Recording Event Server'.")
		self.app = app or FastAPI(title='Temporary Recording Event Server')
		self.app.add_api_route('/event', self._handle_event_post, methods=['POST'], status_code=202)
		# -- DEBUGGING --
		# Turn this on to debug requests
		# @self.app.middleware("http")
		# async def log_requests(request: Request, call_next):
		#     print(f"[Debug] Incoming request: {request.method} {request.url}")
		#     try:
		#         # Read request body
		#         body = await request.body()
		#         print(f"[Debug] Request body: {body.decode('utf-8', errors='replace')}")
		#         response = await call_next(request)
		#         print(f"[Debug] Response status: {response.status_code}")
		#         return response
		#     except Exception as e:
		#         print(f"[Error] Error processing request: {str(e)}")

		self.uvicorn_server_instance: Optional[uvicorn.Server] = None
		self.server_task: Optional[asyncio.Task] = None
		self.playwright_task: Optional[asyncio.Task] = None
		self.event_processor_task: Optional[asyncio.Task] = None

	async def _handle_event_post(self, event_data: RecorderEvent):
		if isinstance(event_data, HttpWorkflowUpdateEvent):
			self.last_workflow_update_event = event_data
		await self.event_queue.put(event_data)
		return {'status': 'accepted', 'message': 'Event queued for processing'}

	async def _process_event_queue(self):
		print('[Service] Event processing task started.')
		try:
			while True:
				event = await self.event_queue.get()
				print(f'[Service] Event Received: {event.type}')
				if isinstance(event, HttpWorkflowUpdateEvent):
					# self.last_workflow_update_event is already updated in _handle_event_post
					pass
				elif isinstance(event, HttpRecordingStoppedEvent):
					print('[Service] RecordingStoppedEvent received, processing final workflow...')
					await self._capture_and_signal_final_workflow('RecordingStoppedEvent')
				self.event_queue.task_done()
		except asyncio.CancelledError:
			print('[Service] Event processing task cancelled.')
		except Exception as e:
			print(f'[Service] Error in event processing task: {e}')

	async def _capture_and_signal_final_workflow(self, trigger_reason: str):
		processed_this_call = False
		async with self.final_workflow_processed_lock:
			if not self.final_workflow_processed_flag and self.last_workflow_update_event:
				print(f'[Service] Capturing final workflow (Trigger: {trigger_reason}).')
				self.final_workflow_output = self.last_workflow_update_event.payload
				self.final_workflow_processed_flag = True
				processed_this_call = True

		if processed_this_call:
			print('[Service] Final workflow captured. Setting recording_complete_event.')
			self.recording_complete_event.set()  # Signal completion to the main method

			# If processing was due to RecordingStoppedEvent, also try to close the browser
			if trigger_reason == 'RecordingStoppedEvent' and self.playwright_context:
				print('[Service] Attempting to close Playwright browser due to RecordingStoppedEvent...')
				try:
					await self.playwright_context.close()
					print('[Service] Playwright browser close command issued.')
				except Exception as e_close:
					print(f'[Service] Error closing Playwright browser on recording stop: {e_close}')

	async def _launch_playwright_and_wait(self):
		print(f'[Service] Attempting to load extension from: {EXT_DIR}')
		if not EXT_DIR.exists() or not EXT_DIR.is_dir():
			print(f'[Service] ERROR: Extension directory not found: {EXT_DIR}')
			self.recording_complete_event.set()  # Signal failure
			return

		# delete the user data dir
		USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
		print(f'[Service] Using Playwright user data directory: {USER_DATA_DIR}')

		async with async_playwright() as p:
			try:
				self.playwright_context = await p.chromium.launch_persistent_context(
					str(USER_DATA_DIR.resolve()),
					headless=False,
					no_viewport=True,
					args=[
						f'--disable-extensions-except={str(EXT_DIR.resolve())}',
						f'--load-extension={str(EXT_DIR.resolve())}',
					],
				)
				print('[Service] Playwright browser launched. Waiting for close or recording stop...')
				await self.playwright_context.wait_for_event('close', timeout=0)
				print("[Service] Playwright context 'close' event detected.")
			except asyncio.CancelledError:
				print('[Service] Playwright task cancelled.')
				if self.playwright_context:
					try:
						await self.playwright_context.close()
					except Exception as e:
						pass  # Best effort
				raise  # Re-raise to be caught by gather
			except Exception as e:
				print(f'[Service] Error in Playwright task: {e}')
			finally:
				print('[Service] Playwright task finalization.')
				self.playwright_context = None
				# This call ensures that if browser is closed manually, we still try to capture.
				await self._capture_and_signal_final_workflow('PlaywrightTaskEnded')

	async def capture_workflow(self) -> Optional[WorkflowDefinitionSchema]:
		print('[Service] Starting capture_workflow session...')
		# Reset state for this session
		self.last_workflow_update_event = None
		self.final_workflow_output = None
		self.recording_complete_event.clear()
		self.final_workflow_processed_flag = False

		# Start background tasks
		self.event_processor_task = asyncio.create_task(self._process_event_queue())
		self.playwright_task = asyncio.create_task(self._launch_playwright_and_wait())

		# Configure and start Uvicorn server
		config = uvicorn.Config(self.app, host='127.0.0.1', port=7331, log_level='warning', loop='asyncio')
		self.uvicorn_server_instance = uvicorn.Server(config)
		self.server_task = asyncio.create_task(self.uvicorn_server_instance.serve())
		print('[Service] Uvicorn server task started.')

		try:
			print('[Service] Waiting for recording to complete...')
			await self.recording_complete_event.wait()
			print('[Service] Recording complete event received. Proceeding to cleanup.')
		except asyncio.CancelledError:
			print('[Service] capture_workflow task was cancelled externally.')
		finally:
			print('[Service] Starting cleanup phase...')

			# 1. Stop Uvicorn server
			if self.uvicorn_server_instance and self.server_task and not self.server_task.done():
				print('[Service] Signaling Uvicorn server to shut down...')
				self.uvicorn_server_instance.should_exit = True
				try:
					await asyncio.wait_for(self.server_task, timeout=5)  # Give server time to shut down
				except asyncio.TimeoutError:
					print('[Service] Uvicorn server shutdown timed out. Cancelling task.')
					self.server_task.cancel()
				except asyncio.CancelledError:  # If capture_workflow itself was cancelled
					pass
				except Exception as e_server_shutdown:
					print(f'[Service] Error during Uvicorn server shutdown: {e_server_shutdown}')

			# 2. Stop Playwright task (and ensure browser is closed)
			if self.playwright_task and not self.playwright_task.done():
				print('[Service] Cancelling Playwright task...')
				self.playwright_task.cancel()
				try:
					await self.playwright_task
				except asyncio.CancelledError:
					pass
				except Exception as e_pw_cancel:
					print(f'[Service] Error awaiting cancelled Playwright task: {e_pw_cancel}')

			if self.playwright_context:  # Final check to close context if still open
				print('[Service] Ensuring Playwright context is closed in cleanup...')
				try:
					await self.playwright_context.close()
				except Exception as e_pc_close:
					print(f'[Service] Error closing context in final cleanup: {e_pc_close}')
				self.playwright_context = None

			# 3. Stop event processor task
			if self.event_processor_task and not self.event_processor_task.done():
				print('[Service] Cancelling event processor task...')
				self.event_processor_task.cancel()
				try:
					await self.event_processor_task
				except asyncio.CancelledError:
					pass
				except Exception as e_ep_cancel:
					print(f'[Service] Error awaiting cancelled event processor task: {e_ep_cancel}')

			print('[Service] Cleanup phase complete.')

		if self.final_workflow_output:
			print('[Service] Returning captured workflow.')
		else:
			print('[Service] No workflow captured or an error occurred.')
		return self.final_workflow_output
	
	# Setup a temporary reverse proxy to the main server
	async def _start_proxy_server(self):
		async def proxy(request):
			target_url = f"http://127.0.0.1:8000{request.rel_url}"
			data = await request.read()
			async with ClientSession() as session:
				async with session.request(
					method=request.method,
					url=target_url,
					headers={k: v for k, v in request.headers.items() if k.lower() != 'host'},
					data=data
				) as resp:
					body = await resp.read()
					return web.Response(status=resp.status, body=body, headers=resp.headers)

		self._proxy_app = web.Application()
		self._proxy_app.router.add_route('*', '/{tail:.*}', proxy)
		self._proxy_runner = web.AppRunner(self._proxy_app)
		await self._proxy_runner.setup()
		self._proxy_site = web.TCPSite(self._proxy_runner, '127.0.0.1', 7331)
		await self._proxy_site.start()
		print("[Services] Reverse proxy started on port 7331.")

	async def _stop_proxy_server(self):
		if hasattr(self, '_proxy_site'):
			print("[Services] Stopping reverse proxy on port 7331.")
			await self._proxy_runner.cleanup()
	
	async def record_workflow_using_main_server(self) -> Optional[WorkflowDefinitionSchema]:
		"""Used in the UI version because there is already a Uvicorn server."""
		
		print('[Service] Starting Playwright-only workflow recording session...')
		self.last_workflow_update_event = None
		self.final_workflow_output = None
		self.recording_complete_event.clear()
		self.final_workflow_processed_flag = False

		# Start reverse proxy on port 7331
		await self._start_proxy_server()

		self.event_processor_task = asyncio.create_task(self._process_event_queue())
		self.playwright_task = asyncio.create_task(self._launch_playwright_and_wait())

		try:
			print('[Service] Recording finished, proceeding to cleanup.')
			await self.recording_complete_event.wait()
			print('[Service] Recording complete event received. Proceeding to cleanup.')
		except asyncio.CancelledError:
			print('[Service] record_workflow_using_main_server was cancelled.')
		finally:
			print('[Service] Starting cleanup phase (Playwright-only mode)...')

			await self._stop_proxy_server()

			if self.playwright_task and not self.playwright_task.done():
				print('[Service] Cancelling Playwright task...')
				self.playwright_task.cancel()
				try:
					await self.playwright_task
				except asyncio.CancelledError:
					pass
				except Exception as e_pw_cancel:
					print(f'[Service] Error awaiting cancelled Playwright task: {e_pw_cancel}')

			# Ensure browser context is closed
			if self.playwright_context:
				try:
					await self.playwright_context.close()
				except Exception as e:
					print(f'[Service] Error closing Playwright context: {e}')
				self.playwright_context = None

			# Stop event processor task
			if self.event_processor_task and not self.event_processor_task.done():
				print('[Service] Cancelling event processor task...')
				self.event_processor_task.cancel()
				try:
					await self.event_processor_task
				except asyncio.CancelledError:
					pass
				except Exception as e_ep:
					print(f'[Service] Error while awaiting event processor: {e_ep}')

			print('[Service] Cleanup complete.')

		if self.final_workflow_output:
			print('[Service] Returning captured workflow.')
			print(self.final_workflow_output)
		else:
			print('[Service] No workflow captured.')
		return self.final_workflow_output


async def main_service_runner():  # Example of how to run the service
	service = RecordingService()
	workflow_data = await service.capture_workflow()
	if workflow_data:
		print('\n--- CAPTURED WORKFLOW DATA (from main_service_runner) ---')
		# Assuming WorkflowDefinitionSchema has model_dump_json or similar
		try:
			print(workflow_data.model_dump_json(indent=2))
		except AttributeError:
			print(json.dumps(workflow_data, indent=2))  # Fallback for plain dicts if model_dump_json not present
		print('-----------------------------------------------------')
	else:
		print('No workflow data was captured by the service.')


if __name__ == '__main__':
	# This allows running service.py directly for testing
	try:
		asyncio.run(main_service_runner())
	except KeyboardInterrupt:
		print('Service runner interrupted by user.')
