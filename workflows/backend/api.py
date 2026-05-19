import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .recorder_router import router as recorder_router
from .routers import router

app = FastAPI(title='Workflow Execution Service')

# Add CORS middleware
# Allow requests from: React UI dev server, Chrome extensions (any ID), localhost variants
app.add_middleware(
	CORSMiddleware,
	allow_origins=[
		'http://localhost:5173',
		'http://127.0.0.1:5173',
	],
	# Chrome extension origins are handled by allow_origin_regex
	allow_origin_regex=r'^chrome-extension://.*$',
	allow_credentials=True,
	allow_methods=['*'],
	allow_headers=['*'],
)

# Include routers
app.include_router(router)
app.include_router(recorder_router)


# Optional standalone runner
if __name__ == '__main__':
	uvicorn.run('api:app', host='127.0.0.1', port=8000, log_level='info')
