from os import listdir, path
import logging
import io
import chardet
import codecs
import json
from decouple import config

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from rdflib import Graph
from rdflib_endpoint import SparqlRouter
from SPARQLWrapper import SPARQLWrapper, JSON
import starlette.status as status
import uvicorn

# constants
DATA_DIR = 'data'
GRAPH = 'graph'
STATUS = 'status'
SIZE = 'number_of_triples'
EXTERNAL_ENDPOINT = 'endpoint'
INTERNAL_ENDPOINT = 'internal_endpoint'
META_DATA = 'meta'
DATA = 'data'
EXTERN_STATUS = 'extern_accessibility'
ENDPOINT_URL = 'url'
OK_MESSAGE = 'OK'
NOT_OK_MESSAGE = 'KO'

# the port on which this service is running (alternative names are allowed)
PORT = config('PORT', default=20000, cast=int) 
PORT = config('INTERNAL_PORT', default=PORT, cast=int) # alternative name

# the port on which the SPARQL endpoint is accessible from outside (it might be different from the internal port, e.g., when using Docker)
EXTERNAL_PORT = config('EXTERNAL_PORT', default=PORT, cast=int) 
# the server on which the SPARQL endpoint is accessible from outside (it might be different from the internal server, e.g., when using Docker)
EXTERNAL_SERVER = config('EXTERNAL_SERVER', default="http://127.0.0.1", cast=lambda v: v.strip('/')) 

BASE_EXTERNAL_ENDPOINT = f'{EXTERNAL_SERVER}:{EXTERNAL_PORT}/'
BASE_INTERNAL_ENDPOINT = f'http://127.0.0.1:{PORT}/'
logging.basicConfig(level=logging.INFO)

logging.info('Starting the service on port: ' + str(PORT))
logging.info('Base endpoint for external access: ' + BASE_EXTERNAL_ENDPOINT)
logging.info('Reading data from directory: ' + DATA_DIR)

# create the FastAPI app and add the CORS middleware to allow access from other domains (e.g., needed for Yasgui)
app = FastAPI()
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# the catalog of all stored data sets
data_catalog = {}


# read all directories 
for directory in listdir(DATA_DIR):
    logging.info('Reading element: ' + directory)
    if path.isdir(DATA_DIR + '/' + directory): # read only directories
        logging.info('Reading sub-directory: ' + directory)
        data_catalog[directory] = {}
        g = Graph()
        data_catalog[directory][GRAPH] = g
        meta_data = {}
        
        # read all files in the current directory
        for file in listdir(DATA_DIR + '/' + directory):
            full_filename = DATA_DIR + '/' + directory + '/' + file
            
            # read the data file
            if file.endswith('.ttl'):
                # read the file content
                logging.info('Reading file: ' + file)

                bytes = min(32, path.getsize(full_filename))
                raw = open(full_filename, 'rb').read(bytes)
                
                if raw.startswith(codecs.BOM_UTF8):
                    encoding = 'utf-8-sig'
                else:
                    result = chardet.detect(raw)
                    encoding = result['encoding']
                    
                infile = io.open(full_filename, "r", encoding=encoding)
                content = infile.read()
                infile.close()
                
                # add the file content to the graph
                g.parse(data=content, format='turtle')
            
            elif file.endswith('.json'): # read the meta data file
                data_catalog[directory][META_DATA] = json.load(open(full_filename))
        
        # add the graph to the SPARQL endpoint
        graph_endpoint_external = BASE_EXTERNAL_ENDPOINT + directory
        graph_endpoint_internal = BASE_INTERNAL_ENDPOINT + directory
        data_catalog[directory][EXTERNAL_ENDPOINT] = graph_endpoint_external
        data_catalog[directory][INTERNAL_ENDPOINT] = graph_endpoint_internal
        
        logging.info('Adding graph to SPARQL endpoint as ' + graph_endpoint_external)
        
        # define the router for the endpoint 
        sparql_router = SparqlRouter(
            graph=g,
            path="/" + directory,
            # Metadata used for the SPARQL service description and Swagger UI:
            title=data_catalog[directory][META_DATA]["title"] if META_DATA in data_catalog[directory] and 'title' in data_catalog[directory][META_DATA] else directory,
            description=data_catalog[directory][META_DATA]["description"] if META_DATA in data_catalog[directory] and 'description' in data_catalog[directory][META_DATA] else "",
            version=data_catalog[directory][META_DATA]["version"] if META_DATA in data_catalog[directory] and 'version' in data_catalog[directory][META_DATA] else "",
            example_query=data_catalog[directory][META_DATA]["example_query"] if META_DATA in data_catalog[directory] and 'example_query' in data_catalog[directory][META_DATA] else "",
            public_url=graph_endpoint_external,
            enable_update=False
        )
        app.include_router(sparql_router)
        logging.info('Graph added to SPARQL endpoint: ' + directory)

@app.get("/")
def root():
    return RedirectResponse(url="/health", status_code=status.HTTP_302_FOUND)

@app.get("/favicon.ico")
def favicon():
    return RedirectResponse(url="https://rdflib.readthedocs.io/en/stable/_static/RDFlib.png", status_code=status.HTTP_302_FOUND)

@app.get("/health/")
def healthcheck():
    health_status = {}
    
    for graph_name in data_catalog:
        if data_catalog[graph_name][GRAPH].query("SELECT * WHERE {?s ?p ?o} LIMIT 1"):
            data_status = OK_MESSAGE
        else:
            data_status = NOT_OK_MESSAGE
        
        try:
            sparql = SPARQLWrapper(data_catalog[graph_name][INTERNAL_ENDPOINT])
            sparql.setQuery("SELECT * WHERE {?s ?p ?o} LIMIT 1")
            sparql.setReturnFormat(JSON)
            data_json = sparql.query().convert()
            if 'results' in data_json and 'bindings' in data_json['results']:
                logging.info(f"SPARQL SELECT test on {graph_name} via {data_catalog[graph_name][INTERNAL_ENDPOINT]}: " + str(data_json['results']['bindings']))
                extern_status = OK_MESSAGE
            else:
                extern_status = NOT_OK_MESSAGE
        except Exception as e:
            logging.error(f"Access check of {graph_name} via {data_catalog[graph_name][INTERNAL_ENDPOINT]} failed:" + str(e))
            extern_status = NOT_OK_MESSAGE
        
        data_size = len(data_catalog[graph_name][GRAPH])
        meta = data_catalog[graph_name][META_DATA] if META_DATA in data_catalog[graph_name] else {}
    
        health_status[graph_name] = {
            EXTERNAL_ENDPOINT: {
                ENDPOINT_URL: data_catalog[graph_name][EXTERNAL_ENDPOINT],
                EXTERN_STATUS: extern_status
            },
            DATA: {
                STATUS: data_status,
                SIZE: data_size,
            },
            META_DATA: meta
        }

    return health_status

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)