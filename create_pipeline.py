from kfp import dsl
from kfp import compiler
from kfp.dsl import Dataset
from kfp.dsl import Input
from kfp.dsl import Model
from kfp.dsl import Output
from kfp import compiler
import os


@dsl.component(packages_to_install=['pandas', 'kagglehub'])
def download_kaggle_dataset(kaggle_df : Output[Dataset]):
  import kagglehub
  import pandas as pd

  path_tmp = kagglehub.dataset_download('pratyushakar/rossmann-store-sales')
  df = pd.read_csv(path_tmp + '/train.csv')
 
  with open(kaggle_df.path, 'w') as f:
        df.to_csv(f, index=False)

@dsl.component(packages_to_install=['pandas'])
def prep_store_data(kaggle_df: Input[Dataset], df_store_out: Output[Dataset], 
                    store_id:  int, store_open:  int = 1):
    import pandas as pd
    
    with open(kaggle_df.path) as f:
        df = pd.read_csv(f)

    df_store = df[(df['Store'] == store_id) & (df['Open'] == store_open)].reset_index(drop=True)
    df_store['Date'] = pd.to_datetime(df_store['Date'])
    df_store.rename(columns= {'Date': 'ds', 'Sales': 'y'}, inplace=True)

    df_store.sort_values('ds', ascending=True, inplace=True)
    with open(df_store_out.path, 'w') as f:
        df_store.to_csv(f)

@dsl.component(packages_to_install=['pandas', 'prophet','mlflow'])
def train_model(df_train: Input[Dataset], seasonality: dict, model_out : Output[Model]):
    from prophet import Prophet
    import pickle
    import pandas as pd

    model=Prophet(yearly_seasonality=seasonality['yaerly'], weekly_seasonality=seasonality['weekly'], daily_seasonality=seasonality['daily'], interval_width = 0.95)
    
    with open(df_train.path) as f:
        df = pd.read_csv(f)

    model.fit(df)

    with open(model_out.path, 'wb') as f:
        pickle.dump(model, f)

@dsl.component(packages_to_install=['mlflow', 'prophet', 'azure-storage-blob', 'azure-identity'])
def save_model(model : Input[Model], id_store : int):
    import pickle
    import mlflow

    with open(model.path, 'rb') as f:
        model_l = pickle.load(f)    
    import logging

    import os

    os.environ["AZURE_CLIENT_ID"] = ""
    os.environ["AZURE_TENANT_ID"] = ""
    os.environ["AZURE_CLIENT_SECRET"] = ""


    logging.basicConfig(level=logging.DEBUG)

    mlflow.set_tracking_uri("http://mlflow.default.svc.cluster.local:5000")

    with mlflow.start_run():
        try:
            mlflow.prophet.log_model(pr_model=model_l, artifact_path="prophet_model_store_{}".format(id_store), 
                                     registered_model_name="prophet_model_store_{}".format(id_store))
            logging.info("Modello salvato con successo")
        except Exception as e:
            logging.error(f"Errore durante il salvataggio del modello: {e}")


@dsl.component(packages_to_install=['pandas', 'prophet','mlflow', 'ray[client]==2.9.0','azure-storage-blob', 'azure-identity'])
def train_save_all_models(kaggle_df: Input[Dataset], seasonality: dict):
    from prophet import Prophet
    import ray
    import pandas as pd
    import mlflow
    import pickle
    import os

    os.environ["AZURE_CLIENT_ID"] = ""
    os.environ["AZURE_TENANT_ID"] = ""
    os.environ["AZURE_CLIENT_SECRET"] = ""

    @ray.remote(num_returns=1)
    def prep_train(df: pd.DataFrame, store_id: int, seasonality : dict, store_open: int=1):
        import pandas as pd
        from prophet import Prophet

        df_store = df[(df['Store'] == store_id) & (df['Open'] == store_open)].reset_index(drop=True)
        df_store['Date'] = pd.to_datetime(df_store['Date'])
        df_store.rename(columns= {'Date': 'ds', 'Sales': 'y'}, inplace=True)
        df_store.sort_values('ds', ascending=True, inplace=True) 

        model=Prophet(yearly_seasonality=seasonality['yaerly'], 
                    weekly_seasonality=seasonality['weekly'],
                    daily_seasonality=seasonality['daily'],
                    interval_width = 0.95)
        
        model.fit(df_store)
        return model 
    
    with open(kaggle_df.path, 'rb') as f:
        df = pd.read_csv(f)

    store_ids = df['Store'].unique()

    ray.init()
    df_id = ray.put(df)
    
    model_refs = [prep_train.remote(df=df_id, store_id=store_id,
                                     seasonality= seasonality, store_open=1) 
                                     for store_id in store_ids]
    models = ray.get(model_refs)

    mlflow.set_tracking_uri("http://mlflow.default.svc.cluster.local:5000")
    with mlflow.start_run():
        for k,m in enumerate(models):
            mlflow.prophet.log_model(pr_model=m,artifact_path="prophet_model_store_{}".format(k),
                                        registered_model_name='prophet_model_store_{}'.format(k))



@dsl.pipeline(name='training_pipeline_all_models')
def training_pipeline_all_models(seasonality : dict):
    download_kaggle_dataset_task = download_kaggle_dataset()
    df_kaggle = download_kaggle_dataset_task.outputs['kaggle_df']

    train_save_all_models(kaggle_df=df_kaggle, seasonality=seasonality)


@dsl.pipeline(name='training_pipeline_one_model')
def training_pipeline_one_model(n_store: int, seasonality : dict):
    download_kaggle_dataset_task = download_kaggle_dataset()
    df_kaggle = download_kaggle_dataset_task.outputs['kaggle_df']

    prep_store_data_task = prep_store_data(kaggle_df=df_kaggle, store_id=n_store)
    store_df = prep_store_data_task.outputs['df_store_out']

    train_model_task = train_model(df_train=store_df, seasonality=seasonality)
    model = train_model_task.outputs['model_out']

    save_model(model=model, id_store=n_store)


base_path = 'app/train_pipelines/'
if not os.path.exists(base_path):
    os.mkdir(base_path)
compiler.Compiler().compile(training_pipeline_all_models, base_path+'training_pipeline_all_models.yml')
compiler.Compiler().compile(training_pipeline_one_model, base_path+'training_pipeline_one_model.yml')
