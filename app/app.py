from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
from .helpers.request import ForecastRequest, TrainModelRequest,TrainAllModelsRequest, create_forecast_index
from .registry.mlflow.handler import MLFlowHandler
from typing import List
import uvicorn 
from kfp import Client
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Logging
import logging
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s" 
logging.basicConfig(format = log_format, level = logging.INFO)

ml_models = {}
service_handlers = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    
    import os
    os.environ["AZURE_CLIENT_ID"] = ""
    os.environ["AZURE_TENANT_ID"] = ""
    os.environ["AZURE_CLIENT_SECRET"] = ""

    #load_dotenv()

    # Create handlers
    service_handlers['mlflow'] = MLFlowHandler()
    logging.info("Initiatilised mlflow handler {}".format(type(service_handlers['mlflow'])))
    yield
    # Clean up handlers
    service_handlers.clear()
    ml_models.clear()
    logging.info("Handlers and ml models cleared")

app = FastAPI(lifespan=lifespan)

@app.post("/forecast/", status_code=200)
async def parse_request(forecast_request: List[ForecastRequest]):
    '''
    1. Retrieve each model from model registry
    2. Forecast with it
    3. Cache it
    '''
    async with lifespan(app=app):
        forecasts = []
        for item in forecast_request:
            model_name = 'prophet_model_store_{}'.format(item.store_id)
            if model_name not in ml_models.keys():
                ml_models[model_name] = service_handlers['mlflow'].get_production_model(item.store_id)
            else:
                pass
            forecast_input = create_forecast_index(
                begin_date=item.begin_date, 
                end_date=item.end_date
                )
            forecasts.append(ml_models[model_name].predict(forecast_input))
        return forecasts    

@app.post("/train/", status_code=200)
async def train_model(store_train: List[TrainModelRequest]):
    
    async with lifespan(app=app):
        for item in store_train:

            

            client = Client()
            
            client.create_run_from_pipeline_package('/app/train_pipelines/training_pipeline_one_model.yml', 
                                                arguments={
                                                    'n_store': int(item.store_id),
                                                'seasonality': {
                                                    'yaerly' : item.yaerly,
                                                    'weekly': item.weekly,
                                                    'daily' : item.daily}
                                                    }, enable_caching=True)
            
@app.post("/train_all/", status_code=200)
async def train_all_models(seasonality: TrainAllModelsRequest):
    async with lifespan(app=app):
        client = Client()
        client.create_run_from_pipeline_package('/app/train_pipelines/training_pipeline_all_models.yml', 
                                                arguments={
                                                    'seasonality': {
                                                    'yaerly' : seasonality.yaerly,
                                                    'weekly': seasonality.weekly,
                                                    'daily' : seasonality.daily}
                                                    }, enable_caching=True)