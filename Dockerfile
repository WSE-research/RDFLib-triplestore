FROM tiangolo/uvicorn-gunicorn-fastapi:python3.10

# parameters that might be provided at runtime by using the --env option

### define here the external server address and port, i.e., how to access the container from outside
# default server address to which the container will listen (don't add the port here)
ENV EXTERNAL_SERVER="http://localhost" 
# default port for the external server
ENV EXTERNAL_PORT=30000

# default port for the internal server
ENV INTERNAL_PORT=20000

WORKDIR /app
COPY . .
RUN pip install --upgrade pip && pip install -r ./requirements.txt 

HEALTHCHECK CMD curl --fail http://localhost:${INTERNAL_PORT}/health

EXPOSE $INTERNAL_PORT
ENTRYPOINT ["sh", "-c", "\
    export EXTERNAL_SERVER=$EXTERNAL_SERVER \
    export EXTERNAL_PORT=$EXTERNAL_PORT \
    export INTERNAL_PORT=$INTERNAL_PORT \
    && echo \"EXTERNAL_SERVER: $EXTERNAL_SERVER\" \
    && echo \"EXTERNAL_PORT: $EXTERNAL_PORT\" \
    && echo \"INTERNAL_PORT: $INTERNAL_PORT\" \
    && python app.py"]