from fastapi import FastAPI
from services.recruiter_company_service.app.middleware.cors import setup_cors
from services.recruiter_company_service.app.routes.recruiters import router as recruiters_router
from services.shared.observability import attach_observability

app = FastAPI(title='Recruiter Company Service')
setup_cors(app)
attach_observability(app, 'recruiter_company_service')
app.include_router(recruiters_router)
