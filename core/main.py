from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Buddhi AI Studio",
    description="Buddhi AI Studio is an AI Agent Development Environment",
    version="0.0.1",
)

# Not safe! Add your own allowed domains
origins = [
    "http://localhost:3434",  
] 

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Welcome GET route for app
@app.get("/")
def read_root():
    return {"message": "Welcome to Buddhi AI"}