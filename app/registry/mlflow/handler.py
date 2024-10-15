import mlflow
from mlflow.pyfunc import PyFuncModel

class MLFlowHandler:

    def __init__(self) -> None:
        mlflow.set_tracking_uri("http://mlflow.default.svc.cluster.local:5000")

    def get_production_model(self, store_id: str) -> PyFuncModel:
        model_name = "prophet_model_store_{}".format(store_id)
        
        model = mlflow.prophet.load_model(model_uri='models:/{}/latest'.format(model_name))
        return model
    
    