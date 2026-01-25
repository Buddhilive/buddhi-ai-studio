from pyloid_adapter.base_adapter import BaseAdapter
from pyloid_adapter.context import PyloidContext
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

# Import model download routes
from routes import models_router, chat_router, responses_router
from config import initialize_settings
from utils import get_models_directory
from models import ProblemDetail

app = FastAPI(
	title="Buddhi AI Studio API",
	description="Local LLM management and model download API",
	version="0.1.0",
)


# ============================================================================
# Error Handlers (RFC 9457)
# ============================================================================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
	"""Handle FastAPI request validation errors with RFC 9457 format.
	
	Args:
		request: FastAPI request
		exc: Validation error
		
	Returns:
		JSON response with problem details
	"""
	# Extract field errors
	errors = []
	for error in exc.errors():
		field = " -> ".join(str(loc) for loc in error["loc"])
		errors.append(f"{field}: {error['msg']}")
	
	problem = ProblemDetail(
		type="https://buddhi.ai/problems/validation-error",
		title="Validation Error",
		status=status.HTTP_422_UNPROCESSABLE_ENTITY,
		detail="; ".join(errors),
		instance=str(request.url),
	)
	
	return JSONResponse(
		status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
		content=problem.model_dump(),
	)


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
	"""Handle Pydantic validation errors with RFC 9457 format.
	
	Args:
		request: FastAPI request
		exc: Pydantic validation error
		
	Returns:
		JSON response with problem details
	"""
	errors = []
	for error in exc.errors():
		field = " -> ".join(str(loc) for loc in error["loc"])
		errors.append(f"{field}: {error['msg']}")
	
	problem = ProblemDetail(
		type="https://buddhi.ai/problems/validation-error",
		title="Data Validation Error",
		status=status.HTTP_422_UNPROCESSABLE_ENTITY,
		detail="; ".join(errors),
		instance=str(request.url),
	)
	
	return JSONResponse(
		status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
		content=problem.model_dump(),
	)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
	"""Handle generic exceptions with RFC 9457 format.
	
	Args:
		request: FastAPI request
		exc: Exception
		
	Returns:
		JSON response with problem details
	"""
	problem = ProblemDetail(
		type="https://buddhi.ai/problems/internal-error",
		title="Internal Server Error",
		status=status.HTTP_500_INTERNAL_SERVER_ERROR,
		detail=str(exc),
		instance=str(request.url),
	)
	
	return JSONResponse(
		status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
		content=problem.model_dump(),
	)


# ============================================================================
# Startup/Shutdown Events
# ============================================================================


@app.on_event("startup")
async def startup_event():
	"""Initialize application on startup."""
	# Pyloid app will be set via set_pyloid_app() function
	pass


@app.on_event("shutdown")
async def shutdown_event():
	"""Cleanup on application shutdown."""
	# Cleanup any background tasks if needed
	pass


# ============================================================================
# Pyloid Integration
# ============================================================================


def set_pyloid_app(pyloid_app):
	"""Set Pyloid app instance and initialize settings.
	
	This function should be called from main.py after Pyloid app is created.
	
	Args:
		pyloid_app: Pyloid application instance
	"""
	# Store Pyloid app in FastAPI state
	app.state.pyloid_app = pyloid_app
	
	# Get models directory and initialize settings
	models_dir = get_models_directory(pyloid_app)
	initialize_settings(str(models_dir))


# ============================================================================
# Setup Functions
# ============================================================================


def start(host: str, port: int):
	"""Start the FastAPI server.
	
	Args:
		host: Server host
		port: Server port
	"""
	import uvicorn
	uvicorn.run(app, host=host, port=port)


def setup_cors():
	"""Setup CORS middleware."""
	app.add_middleware(
		CORSMiddleware,
		allow_origins=['*'],
		allow_credentials=True,
		allow_methods=['*'],
		allow_headers=['*'],
	)


# ============================================================================
# Router Registration
# ============================================================================


# Register model download routes
app.include_router(models_router, prefix="/api")

# Register OpenAI-compatible chat routes (backward compatibility)
app.include_router(chat_router)

# Register OpenAI Responses API routes
app.include_router(responses_router)



# ============================================================================
# Create Adapter
# ============================================================================


adapter = BaseAdapter(start, setup_cors)


# ============================================================================
# Demo Routes (existing)
# ============================================================================


@app.get('/greet')
async def greet(name: str):
	"""Demo endpoint - greet user.
	
	Args:
		name: Name to greet
		
	Returns:
		Greeting message
	"""
	return f'Hello, {name}!'


@app.get('/create_window')
async def create_window(request: Request):
	"""Demo endpoint - create Pyloid window.
	
	Args:
		request: FastAPI request
	"""
	window_id = request.headers.get("X-Pyloid-Window-Id")
 
	if adapter.is_pyloid(window_id):
		print("pyloid request")
	else:
		print("not pyloid request")
  
	ctx: PyloidContext = adapter.get_context(window_id) 
 
	win = ctx.pyloid.create_window(title='Google Window')
	win.load_url('https://www.google.com')
	win.show_and_focus()

