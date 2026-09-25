FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY queue-processor.py instrumentation_helpers.py ./

CMD [ "python", "queue-processor.py" ]
