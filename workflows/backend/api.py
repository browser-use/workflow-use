import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import router

app = FastAPI(title='Workflow Execution Service')

# Add CORS middleware
app.add_middleware(
	CORSMiddleware,
	allow_origins=['http://localhost:5173'],
	allow_credentials=True,
	allow_methods=['*'],
	allow_headers=['*'],
)

# Include routers
app.include_router(router)


# Optional standalone runner
if __name__ == '__main__':
	uvicorn.run('api:app', host='127.0.0.1', port=8000, log_level='info')
