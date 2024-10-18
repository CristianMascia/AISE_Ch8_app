
# Foreact Application on Azure

This example entails the development of an application designed to support the logistics operations of a large retail enterprise. The primary objective is to optimize the flow of goods by empowering regional logistics planners to proactively anticipate periods of heightened demand and mitigate the risk of product shortages

The user stories collected after the stakeholder interview are:

- User Story 1: As a local logistics planner, I want to log in to a dashboard in the morning at 09:00 and be able to see forecasts of item demand at the store level for the next few days so that I can understand transport demand ahead of time.

- User Story 2: As a local logistics planner, I want to be able to request an update of my forecast if I see it is out of date. I want the new forecast to be returned in under 5 minutes
so that I can make decisions on transport demand effectively.

- User Story 3: As a local logistics planner, I want to be able to filter for forecasts for specific stores so that I can understand what stores are driving demand and use this in de-
cision-making.

The application is developed according to a microservices architecture.

The best way to implement a microservices application is undoubtedly by leveraging containers. To simplify the containers management and deployment, we will utilize the orchestration tool Kubernetes. 
Yhe key features of Kubernetes are:

- Service Discovery and Load Balancing: Exposes containers using DNS names or IP addresses and balances network traffic.
- Storage Orchestration: Automatically mounts storage systems like local storage or public cloud providers.
- Automated Rollouts and Rollbacks: Manages container states and automates deployment changes.
- Self-Healing: Restarts, replaces, and manages containers based on health checks.
- Secret and Configuration Management: Manages sensitive information and configuration without exposing them.

To release an application in the cloud, we will utilize Azure Kubernetes Service (AKS). AKS is a managed Kubernetes service designed for the deployment and management of containerized applications. Leveraging AKS necessitates minimal expertise in container orchestration.

## Prerequisites
- Have Azure CLI
- Have a Resource Group
- Have a Private Container Registry
- Have Docker installed

## Create an Azure Kubernetes Cluster

Prior to initiating the deployment of the application, it is essential to establish a Kubernetes cluster for deployment purposes. A Kubernetes cluster comprises a control plane and a collection of worker machines, referred to as nodes, which execute containerized applications. Each cluster necessitates at least one worker node to operate Pods. The worker nodes host the Pods, which constitute the components of the application workload. The control plane oversees the worker nodes and Pods within the cluster.

This command creates a Cluster with a single node (a single worker machine)

```
  az aks create --resource-group <resource group> --name <cluster name> --node-count 1  --generate-ssh-keys
```

> 📝 To address resource constraints and ensure optimal deployment performance, consider configuring your cluster as an autoscaled cluster with an autoscaled node pool. This dynamic approach allows for automatic adjustment of node count based on fluctuating workload demands. The following command can be used to implement this configuration: ```az aks update --resource-group <rources group> --name <cluster name> --enable-cluster-autoscaler --min-count 1 --max-count 3```

### Connect kubectl to the cluster

To interact with the cluster, Kubernetes provides a command-line tool for communicating with a Kubernetes cluster’s control plane using the Kubernetes API. This tool is named ```kubectl```.

```kubectl``` must be configured to know which cluster to interact with. This configuration is typically found in ```$HOME/.kube/config```.

The following command adds the configuration for accessing an Azure cluster and configures ```kubectl``` to point to the selected cluster on Azure.

```
  az aks get-credentials --resource-group <resource group> --name <cluster name> --overwrite-existing 
```

Useful commands 

```
  kubectl config get-contexts
  #Returns the list of contexts (the clusters) that kubectl can interface to

  kubectl config use-context CONTEXT_NAME
  #selects the context
```

## Deploy Applications

Once the Kubernetes cluster has been obtained and kubectl configured, we can proceed with the deployment of the application. In this example, we have selected tool that employ different deployment techniques. For each deployment, we will provide an overview of the functions performed by the microservice and some commentary on the deployment method used.

### Kubeflow Pipeline

Kubeflow is an ecosystem of open-source projects designed to address each stage of the machine learning (ML) lifecycle, supporting top-tier open-source tools and frameworks. It simplifies, enhances portability, and scales AI/ML on Kubernetes. The Kubeflow ecosystem comprises various open-source projects that cater to different aspects of the ML lifecycle. These projects can be utilized both within the Kubeflow Platform and independently, with components installable as standalone entities on a Kubernetes cluster.

For the implementation of the application we are only interested in the Kubeflow Pieplines component. 
Kubeflow Pipelines (KFP) is a platform for building and deploying portable and scalable machine learning (ML) workflows using Docker containers. At runtime, **each component execution corresponds to a single container execution**, which may create ML artifacts..


```
  kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/cluster-scoped-resources?ref=2.2.0"
  kubectl wait --for condition=established --timeout=60s crd/applications.app.k8s.io
  kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/env/dev?ref=2.2.0"
```

Il comando kubectl apply, Apply a configuration to a resource by file name or stdin. The resource name must be specified. This resource will be created if it doesn't exist yet. To use 'apply', always create the resource initially with either 'apply' or 'create --save-config'. JSON and YAML formats are accepted. 
questo comando puo essere utilizzato in due modi. Il primo e quello di fornuire un manifest (flag -f), ovvero un file YAML/JSON che specifica quali oggetti devono essere deployati sul cluster kubernetes, oppure fornire il path di una directory dove sono contenuti dei Kustomication files (flag -k).  


The ```kubectl apply``` command applies a configuration to a resource by file name (JSON and YAML) or stdin.

This command can be utilized in two distinct ways. The first method involves providing a manifest (flag -f), which is a YAML/JSON file that specifies the objects to be deployed on the Kubernetes cluster. Alternatively, one can supply the path to a directory containing Kustomization files (flag -k).

For the installation of the Kubeflow Pipeline, we utilized the Kustomization method. This approach leverages the Kustomize tool, which is designed for customizing Kubernetes configurations. Kustomize offers the following features for managing application configuration files: generating resources from other sources, setting cross-cutting fields for resources, and composing and customizing collections of resources.

> 📝 Await the transition of all container pods to a running state, excluding the proxy-agent pod


### KubeRay

Considering the application’s requirements, we utilize Ray to parallelize model training. Additionally, since our application resides on Kubernetes, we need KubeRay, a Kubernetes operator that enables the use of Ray on Kubernetes. Kubernetes Operators are software extensions to Kubernetes that leverage custom resources to manage applications and their components.

The deployment of KubeRay requires the use of Helm, the package manager for Kubernetes.

For the installation of Helm, you can follow this guide: https://phoenixnap.com/kb/install-helm

Run the following commands to install the KubeRay operator. This is specifically a Kubernetes operator that allows for the management (creation, deletion, utilization) of a Ray Cluster on Kubernetes. We have decided to install it in a dedicated namespace using the -n flag.

```
  helm repo add kuberay https://ray-project.github.io/kuberay-helm/
  helm repo update

  helm install kuberay-operator kuberay/kuberay-operator -n kuberay --create-namespace
```

### Mlflow   

MLFlow is a model registry that we have chosen to use for versioning and saving models. MLFlow utilizes a database for artifact versioning and storage for their retention. Considering that we will also use a version of MLFlow for Kubernetes, it is necessary to manage the storage aspect. When using MLFlow locally, storage is managed by selecting a directory for saving artifacts. Both the client (the entity requesting model registration) and the MLFlow server can access this directory locally. In our case, the client and server reside in different containers and therefore cannot access the same directories (unless a Persistent Volume is used). Furthermore, the complexity increases when introducing the Kubeflow Pipeline, as model saving is managed by the pipeline, which resides in a container created and managed by Kubeflow.

To address this issue, we can leverage the Azure Blob Storage service for artifact storage.

Azure Blob Storage is Microsoft’s object storage solution for the cloud. Blob Storage is optimized for storing massive amounts of unstructured data. Unstructured data is data that does not adhere to a particular data model or definition, such as text or binary data.

![alt text](img/blob.png  "https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-introduction")


#### Creating Azure Storage Account
A storage account is an Azure Resource Manager resource.

```
  az storage account create --name <name storage account> --resource-group <resource group> --location italynorth --sku Standard_LRS --kind Storage --min-tls-version TLS1_2 --allow-blob-public-access false
```

#### Create Storage Container

A container organizes a set of blobs, similar to a directory in a file system. A storage account can include an unlimited number of containers, and a container can store an unlimited number of blobs.

```

  az storage container create --account-name <name storage account> --name <container name> --auth-mode login

```


#### Getting Access Credentials for the Storage

MLFlow requires credentials to authenticate with the defined Azure Storage. Specifically, we need two values: an access key (a token) for authentication and a connection string, which contains all the information necessary for establishing the connection. These two values can be obtained using the following commands:

##### Access Key

```
  az storage account keys list --resource-group <resource group> --account-name <name storage account>

```

##### Connection string

```
  az storage account show-connection-string --name <name storage account> --resource-group <resource group>
```

#### Deploying MlFlow

The Mlflow deployment is done through Helm, and we need to specify some parameters for the connection to the Azure Storage. 

```
  helm repo add community-charts https://community-charts.github.io/helm-charts
  helm repo update

  helm upgrade --install mlflow community-charts/mlflow --set artifactRoot.azureBlob.accessKey="<access key>" --set artifactRoot.azureBlob.connectionString="<connection string>" --set artifactRoot.azureBlob.container="<container name>" --set artifactRoot.azureBlob.enabled=true --set artifactRoot.azureBlob.storageAccount="<name storage account>" 

 ```

#### Forecaster

The Forecaster service operates as a front-end interface implemented using the FastAPI framework, which is responsible for forwarding requests to other backend services. Given that MLflow utilizes Azure Storage for model persistence, authentication of the Azure SDK Python Client is imperative. For the sake of expediency, credentials are defined as environment variables within the code, a practice that is **absolutely discouraged** in production environments.

### Client Authantication

Application that use Azure services should always have restricted permissions to ensure that Azure resources are secure. Therefore, instead of having applications sign in as a fully privileged user, Azure offers service principals. An Azure service principal is an identity created for use with applications, hosted services, and automated tools. This identity is used to access resources.

This command create a service principal and returns the relevant credentials.

```
  az ad sp create-for-rbac --name <service-principal-name>

  #OUTPUT:
  #{
  #  "appId": "00000000-0000-0000-0000-000000000000",
  #  "displayName": "{service-principal-name}",
  #  "password": "abcdefghijklmnopqrstuvwxyz",
  #  "tenant": "33333333-3333-3333-3333-333333333333"
  #}
```

After creating the service principal, we must specify the operations this identity can perform. Azure employs role-based access control (Azure RBAC) as the authorization system to manage access to Azure resources. To grant access, roles are assigned to users, groups, service principals, or managed identities at a particular scope. The role assigned to this identity is a pre-built role called *Storage Blob Data Contributor*. This role permits read, write, and delete access to Azure Storage containers and blobs.

```
  az role assignment create --assignee <appId> --scope /subscriptions/<subscriptionId>/resourceGroups/<resourceGroupName> --role "Storage Blob Data Contributor"
```

Authentication for the Azure Python SDK is managed by the azure-identity package. The DefaultAzureCredential object, contained within the azure-identity package, is undoubtedly the easiest way to get started with the Azure Identity client library. The DefaultAzureCredential object will search for the service principal information in a set of environment variables at runtime. Specifically, the environment variables required for authentication are: AZURE_CLIENT_ID, AZURE_TENANT_ID, and AZURE_CLIENT_SECRET.


!!Only during the developmental stage!!

The required environment variables must be defined within the ```app/app.py``` file. These variables provide essential configuration details for the Forecaster service.

Two separate pipelines have been established for the training process. These pipelines are defined in YAML format using the ```create_pipeline.py``` script. It's crucial to note that within this script, the environment variables must be specified in two specific functions: ```save_model``` and ```train_save_all_models```

For instance:
```
@asynccontextmanager
async def lifespan(app: FastAPI):
    
    import os
    os.environ["AZURE_CLIENT_ID"] = ""      #Set to appId
    os.environ["AZURE_TENANT_ID"] = ""      #Set to password
    os.environ["AZURE_CLIENT_SECRET"] = ""  #Set to tenant
```
Repeat in the same way for the file ```create_pipeline.py```.


Once the environment variables have been set, ***proceed with the execution of the script to generate the YAML files***. This script creates two YAML file in the ```app/train_pipelines``` directory, which are a portable representation of the pipeline. 

### Build Docker Image and Pushing to Azure Container Repository

Considering that Azure only supports the ```linux/amd64``` platform, we must specify it as the platform target.

```
  docker build --platform=linux/amd64 -t forecaster .
  docker tag forecaster <repository name>.azurecr.io/forecaster

  az acr login --name <repository name>
  docker push <repository name>.azurecr.io/forecaster
```

### Deploy Forecaster

Prior to deployment, the Azure Container Registry must be linked to the Azure Kubernetes Cluster.

```
  az aks update --name <kubernetes cluster name> --resource-group <resource group> --attach-acr <repository name>

```

The deploment is handled by defining manifest (YAML file). 
The following is a quick explanation.

In the first section, we select the API version and the type of object to create. In this case, we have chosen a Deployment type. A Deployment manages a set of Pods to run an application workload. For example, this allows us to replicate the frontend for load balancing.

```
apiVersion: apps/v1      
kind: Deployment
```

When the control plane creates new Pods for a Deployment, the .metadata.name of the Deployment is part of the basis for naming those Pods. 

```
metadata:
  name: forecaster
```

In the spec section, the number of replicas and the selector are defined. 

The selector defines how to identify the pods that belong to this Deployment. It uses a label selector to match pods with the label. matchLabel is a map of {key,value} pairs.

```
spec:
  replicas: 1
  selector:
    matchLabels:
      app: forecaster
  template:
    metadata:
      labels:
        app: forecaster
```    

This last section defines the Pod specification, in particular the image, the name and the port.

```
    spec:
      containers:
      - name: forecaster
        image: <YOUR REPOSITORY NAME>.azurecr.io/forecaster
        ports:
        - containerPort: 8080
          name: forecaster
```

For deploy the object, run this command. 

```
  kubectl create -f manifests/forecaster.yaml
```

Now the application is completely deployed but is not accessible from outside the cluster. To allow the application to be accessible externally, Kubernetes provides an object called a Service. A Kubernetes Service is an abstraction that defines a logical set of Pods running somewhere in your cluster, all providing the same functionality. When created, each Service is assigned a unique IP address (also called clusterIP). This address is tied to the lifespan of the Service and will not change while the Service is alive. Pods can be configured to communicate with the Service, knowing that communication will be automatically load-balanced to a Pod that is a member of the Service.

We define a manifest for the service: 

```
apiVersion: v1
kind: Service
metadata:
  name: forecaster
spec:
  ports:
  - port: 80
    targetPort: 3100
  selector:
    app: forecaster
```

We can see that the selector must be the same for sending the traffic to the Pods, and the target port must match the container port defined in the last manifest. The parameter “port” is the ingress port for the Service.

```
  kubectl apply -f manifests/ingress.yaml
```

```
  cristian-msi@cristian-msi-Vector-GP68HX-13VH:~/Documents/AISE_Ch8_app$ kubectl get services
  NAME         TYPE        CLUSTER-IP    EXTERNAL-IP   PORT(S)    AGE
  forecaster   ClusterIP   10.0.78.234   <none>        80/TCP     54s
  kubernetes   ClusterIP   10.0.0.1      <none>        443/TCP    136m
  mlflow       ClusterIP   10.0.227.14   <none>        5000/TCP   106m

```




Finally, Azure requires the definition of an Ingress object for cluster access.

Ingress in AKS is a Kubernetes resource that manages external HTTP-like traffic access to services within a cluster.

When you create an Ingress object that uses the application routing add-on NGINX Ingress classes, the add-on creates, configures, and manages one or more Ingress controllers in your AKS cluster.


### Ingress Deploy

```
az aks approuting enable --resource-group <ResourceGroupName> --name <ClusterName>

kubectl apply -f manifests/ingress.yaml
```

```
  cristian-msi@cristian-msi-Vector-GP68HX-13VH:~/Documents/AISE_Ch8_app$ kubectl get ingress
  NAME         CLASS                                HOSTS   ADDRESS           PORTS   AGE
  forecaster   webapprouting.kubernetes.azure.com   *       172.213.251.193   80      3m34s
```

```ADDRESS``` is the exposed IP for accessing to the application. 
