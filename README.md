
# Foreact Application on Azure

This example entails the development of an application designed to support the logistics operations of a large retail enterprise. The primary objective is to optimize the flow of goods by empowering regional logistics planners to proactively anticipate periods of heightened demand and mitigate the risk of product shortages

The user stories collected after the stakeholder interview are:

- User Story 1: As a local logistics planner, I want to log in to a dashboard in the morning at 09:00 and be able to see forecasts of item demand at the store level for the next few days so that I can understand transport demand ahead of time.

- User Story 2: As a local logistics planner, I want to be able to request an update of my forecast if I see it is out of date. I want the new forecast to be returned in under 5 minutes
so that I can make decisions on transport demand effectively.

- User Story 3: As a local logistics planner, I want to be able to filter for forecasts for specific stores so that I can understand what stores are driving demand and use this in de-
cision-making.


This is the architecture of the application

!!!!!!!!!!!!!!!!!!!!!!!!!!!!1Immagine Architettura con Tool

The application will be deployied on Azure Kuberntetes Cluster


## Creare un Azure Kuberntetes cluster

```
az aks create --resource-group <resource group> --name <cluster name> --node-count 1  --generate-ssh-keys
```

### Connect kubectl to the cluster
To administer the cluster, we establish a connection with ```kubectl``

```
az aks get-credentials --resource-group <resource group> --name <cluster name> --overwrite-existing 
```

## Deploy Applications

### Kubeflow

``` Kubeflow ``` is employed to coordinate the training pipeline

```
kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/cluster-scoped-resources?ref=2.2.0"
kubectl wait --for condition=established --timeout=60s crd/applications.app.k8s.io
kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/env/dev?ref=2.2.0"
```

> 📝 Await the transition of all container pods to a running state, excluding the proxy-agent pod


### KubeRay

Given the necessity of training numerous models, one per store, ```KubeRay```, a Kubernetes-based implementation of Ray, is utilized to parallelize the training process.

Install ```helm```: https://phoenixnap.com/kb/install-helm

```
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update

helm install kuberay-operator kuberay/kuberay-operator -n kuberay --create-namespace
```

### Mlflow   

For versioning of the models, we use ```MlFlow```. ```MlFlow``` needs a storage for saving the artifacts (models), we use Azure Storage. 

#### Creating Azure Storage Account
A storage account is an Azure Resource Manager resource.

```
az storage account create --name <name storage account> --resource-group <resource group> --location italynorth --sku Standard_LRS --kind Storage --min-tls-version TLS1_2 --allow-blob-public-access false
```

#### Create Storage Container

A container organizes a set of blobs, similar to a directory in a file system. A storage account can include an unlimited number of containers, and a container can store an unlimited number of blobs.

```
az ad signed-in-user show --query id -o tsv | az role assignment create --role "Storage Blob Data Contributor" --assignee @- --scope "/subscriptions/<subscriptionId>/resourceGroups/<resource group>/providers/Microsoft.Storage/storageAccounts/<name storage account>"


az ad signed-in-user show --query id -o tsv | az role assignment create --role "Storage Blob Data Contributor" --assignee @- --scope "/subscriptions/<subscriptionId>/resourceGroups/<resource group>/providers/Microsoft.Storage/storageAccounts/<name storage account>"


az storage container create --account-name <name storage account> --name <container name> --auth-mode login

```
#### Getting Access Credentials for the Storage

##### Access Key:

```
az storage account keys list --resource-group <resource group> --account-name <name storage account>

```

##### Connection string

```
az storage account show-connection-string --name <name storage account> --resource-group <resource group>
```

#### Deploying MlFlow
```
helm repo add community-charts https://community-charts.github.io/helm-charts
helm repo update

helm upgrade --install mlflow community-charts/mlflow --set artifactRoot.azureBlob.accessKey="<access key>" --set artifactRoot.azureBlob.connectionString="<connection string>" --set artifactRoot.azureBlob.container="<container name>" --set artifactRoot.azureBlob.enabled=true --set artifactRoot.azureBlob.storageAccount="<name storage account>" 

 ```

#### Forecaster

The Forecaster service operates as a front-end interface implemented using the FastAPI framework, which is responsible for forwarding requests to other backend services. Given that MLflow utilizes Azure Storage for model persistence, authentication of the Azure SDK Python Client is imperative. For the sake of expediency, credentials are defined as environment variables within the code, a practice that is generally discouraged in production environments.

### Client Authantication

First, we need to create the credential for the client 

```
az ad sp create-for-rbac --name {service-principal-name}

#OUTPUT:
#{
#  "appId": "00000000-0000-0000-0000-000000000000",
#  "displayName": "{service-principal-name}",
#  "password": "abcdefghijklmnopqrstuvwxyz",
#  "tenant": "33333333-3333-3333-3333-333333333333"
#}
```

Then, we assign a role
```
az role assignment create --assignee <appId> --scope /subscriptions/<subscriptionId>/resourceGroups/,resourceGroupName> --role "Storage Blob Data Contributor"
```

The necessary environment variables are as follows:

```
AZURE_CLIENT_ID = <appId>
AZURE_TENANT_ID = <tenant>
AZURE_CLIENT_SECRET = <password>
```

This environemnts variables must be set in the ```app/app.py```.
In addition, we defined two pipelines for training, the pipelines are compiled in yaml format through ```create_pipeline.py``` script. 
In this file, the environment variables must be set in two place: ``` save_model``` and ```train_save_all_models``` function. 


The required environment variables must be defined within the ```app/app.py``` file. These variables provide essential configuration details for the Forecaster service.

Two separate pipelines have been established for the training process. These pipelines are defined in YAML format using the ```create_pipeline.py``` script. It's crucial to note that within this script, the environment variables must be specified in two specific functions: ```save_model``` and ```train_save_all_models```


Once the environment variables have been set, proceed with the execution of the script to generate the YAML files.

### Build Docker Image and Pushing to Azure Container Repository

```
docker build -t forecaster .
docker tag forecaster <repository name>.azurecr.io/forecaster

az acr login --name <repository name>
docker push <repository name>.azurecr.io/forecaster
```

### Deploy Forecaster

Prior to deployment, the Azure Container Registry should be linked to the Azure Kubernetes Cluster.

```
az aks update --name AISEkc --resource-group <resource group> --attach-acr aisecr

```

At tthe end, deployment can proceed

```
kubectl create -f manifest.yml
```

