FROM python:latest
WORKDIR /bot/local/data

COPY . /bot/local/data/

RUN python -m pip install -r requirements.txt
CMD python main.py